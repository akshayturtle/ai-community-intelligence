"""Graph builder — constructs community interaction graph and runs NetworkX analysis."""

import structlog
import networkx as nx
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import async_session, Post, CommunityGraph, Persona, User
from scrapers.base_scraper import _utc_naive

logger = structlog.get_logger()

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False
    logger.warning("python-louvain not installed, community detection will be skipped")


class GraphBuilder:
    """Builds community graph from post reply chains and runs graph algorithms."""

    BATCH_SIZE = 1000

    def __init__(self):
        self.log = logger.bind(processor="graph_builder")
        self.edges_upserted = 0
        self.nodes_analyzed = 0

    async def run(self) -> dict:
        """Main entry: build edges, then run graph analysis."""
        self.log.info("graph_build_start")

        # Phase A: Build edges from reply chains
        await self._build_reply_edges()

        # Phase B: Build same-thread edges
        await self._build_same_thread_edges()

        # Phase C: Run graph algorithms and update influence scores
        await self._analyze_graph()

        self.log.info(
            "graph_build_complete",
            edges_upserted=self.edges_upserted,
            nodes_analyzed=self.nodes_analyzed,
        )
        return {
            "edges_upserted": self.edges_upserted,
            "nodes_analyzed": self.nodes_analyzed,
        }

    # ------------------------------------------------------------------
    # Phase A: Reply edges
    # ------------------------------------------------------------------

    async def _build_reply_edges(self) -> None:
        """Scan posts with parent_post_id and create 'reply' edges."""
        self.log.info("building_reply_edges")
        offset = 0

        while True:
            async with async_session() as session:
                pairs = await self._get_reply_pairs(session, offset, self.BATCH_SIZE)

            if not pairs:
                break

            async with async_session() as session:
                for source_uid, target_uid, posted_at, sentiment in pairs:
                    if source_uid == target_uid or source_uid is None or target_uid is None:
                        continue
                    await self._upsert_edge(
                        session, source_uid, target_uid, "reply", sentiment, posted_at
                    )
                await session.commit()

            offset += self.BATCH_SIZE

        self.log.info("reply_edges_done", edges=self.edges_upserted)

    async def _get_reply_pairs(self, session, offset: int, limit: int) -> list:
        """Get (source_user_id, target_user_id, posted_at, sentiment) for reply chains."""
        child = Post.__table__.alias("child")
        parent = Post.__table__.alias("parent")

        stmt = (
            select(
                child.c.user_id,
                parent.c.user_id,
                child.c.posted_at,
                child.c.raw_metadata["sentiment"]["compound"].as_float(),
            )
            .select_from(child.join(parent, child.c.parent_post_id == parent.c.id))
            .where(
                child.c.parent_post_id.isnot(None),
                child.c.user_id.isnot(None),
                parent.c.user_id.isnot(None),
                child.c.user_id != parent.c.user_id,
            )
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.all()

    # ------------------------------------------------------------------
    # Phase B: Same-thread edges (weaker)
    # ------------------------------------------------------------------

    async def _build_same_thread_edges(self) -> None:
        """Create 'same_thread' edges for users appearing in the same thread."""
        self.log.info("building_same_thread_edges")

        # Group posts by parent_post_id to find threads
        async with async_session() as session:
            # Get threads with multiple distinct users
            stmt = (
                select(Post.parent_post_id, func.array_agg(func.distinct(Post.user_id)))
                .where(
                    Post.parent_post_id.isnot(None),
                    Post.user_id.isnot(None),
                )
                .group_by(Post.parent_post_id)
                .having(func.count(func.distinct(Post.user_id)) > 1)
            )
            result = await session.execute(stmt)
            threads = result.all()

        if not threads:
            return

        async with async_session() as session:
            for parent_id, user_ids in threads:
                # Filter out None values
                uids = [uid for uid in user_ids if uid is not None]
                # Create edges between all pairs
                for i in range(len(uids)):
                    for j in range(i + 1, len(uids)):
                        await self._upsert_edge(
                            session, uids[i], uids[j], "same_thread", None, _utc_naive()
                        )
            await session.commit()

        self.log.info("same_thread_edges_done")

    # ------------------------------------------------------------------
    # Edge upsert
    # ------------------------------------------------------------------

    async def _upsert_edge(
        self,
        session,
        source_user_id: int,
        target_user_id: int,
        interaction_type: str,
        sentiment: float | None,
        interaction_at,
    ) -> None:
        """Insert or update an edge in the community graph."""
        now = _utc_naive()
        interaction_at_val = _utc_naive(interaction_at) if interaction_at else now

        stmt = pg_insert(CommunityGraph).values(
            source_user_id=source_user_id,
            target_user_id=target_user_id,
            interaction_type=interaction_type,
            interaction_count=1,
            avg_sentiment=sentiment,
            first_interaction_at=interaction_at_val,
            last_interaction_at=interaction_at_val,
            created_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="community_graph_source_user_id_target_user_id_interaction_key",
            set_={
                "interaction_count": CommunityGraph.interaction_count + 1,
                "avg_sentiment": (
                    # Running average: (old_avg * old_count + new) / (old_count + 1)
                    func.coalesce(CommunityGraph.avg_sentiment, 0)
                    * CommunityGraph.interaction_count
                    + func.coalesce(stmt.excluded.avg_sentiment, 0)
                ) / (CommunityGraph.interaction_count + 1)
                if sentiment is not None
                else CommunityGraph.avg_sentiment,
                "last_interaction_at": func.greatest(
                    CommunityGraph.last_interaction_at, stmt.excluded.last_interaction_at
                ),
            },
        )
        await session.execute(stmt)
        self.edges_upserted += 1

    # ------------------------------------------------------------------
    # Phase C: Graph analysis
    # ------------------------------------------------------------------

    async def _analyze_graph(self) -> None:
        """Load graph, run algorithms, update persona influence scores."""
        self.log.info("analyzing_graph")

        async with async_session() as session:
            G = await self._load_graph(session)

        if G.number_of_nodes() == 0:
            self.log.info("graph_empty_skipping_analysis")
            return

        self.log.info("graph_loaded", nodes=G.number_of_nodes(), edges=G.number_of_edges())

        metrics = self._compute_metrics(G)
        self.nodes_analyzed = len(metrics)

        async with async_session() as session:
            await self._update_influence_scores(session, metrics)
            await session.commit()

        self.log.info("graph_analysis_complete", nodes_analyzed=self.nodes_analyzed)

    async def _load_graph(self, session) -> nx.DiGraph:
        """Load all community_graph edges into a NetworkX DiGraph."""
        result = await session.execute(
            select(
                CommunityGraph.source_user_id,
                CommunityGraph.target_user_id,
                CommunityGraph.interaction_count,
                CommunityGraph.interaction_type,
            )
        )
        edges = result.all()

        G = nx.DiGraph()
        for source, target, count, itype in edges:
            # Weight: replies are stronger than same_thread
            weight_multiplier = 1.0 if itype == "reply" else 0.3
            weight = count * weight_multiplier

            if G.has_edge(source, target):
                G[source][target]["weight"] += weight
            else:
                G.add_edge(source, target, weight=weight)

        return G

    def _compute_metrics(self, G: nx.DiGraph) -> dict[int, dict]:
        """Compute PageRank, betweenness centrality, and Louvain communities."""
        metrics: dict[int, dict] = {}

        # PageRank
        try:
            pagerank = nx.pagerank(G, weight="weight")
        except Exception:
            pagerank = {n: 1.0 / G.number_of_nodes() for n in G.nodes()}

        # Betweenness centrality
        try:
            betweenness = nx.betweenness_centrality(G, weight="weight")
        except Exception:
            betweenness = {n: 0.0 for n in G.nodes()}

        # Louvain communities (needs undirected graph)
        communities = {}
        if HAS_LOUVAIN:
            try:
                G_undirected = G.to_undirected()
                communities = community_louvain.best_partition(G_undirected)
            except Exception:
                pass

        for node in G.nodes():
            metrics[node] = {
                "pagerank": pagerank.get(node, 0),
                "betweenness": betweenness.get(node, 0),
                "community": communities.get(node, 0),
            }

        return metrics

    async def _update_influence_scores(self, session, metrics: dict[int, dict]) -> None:
        """Update persona influence_score using graph metrics."""
        if not metrics:
            return

        # Normalize pagerank and betweenness
        max_pr = max(m["pagerank"] for m in metrics.values()) or 1
        max_bt = max(m["betweenness"] for m in metrics.values()) or 1

        for user_id, m in metrics.items():
            pr_norm = m["pagerank"] / max_pr
            bt_norm = m["betweenness"] / max_bt

            # Get existing persona
            result = await session.execute(
                select(Persona).where(Persona.user_id == user_id)
            )
            persona = result.scalar_one_or_none()
            if persona is None:
                continue

            # Blend: (existing * 0.5) + (pagerank * 0.3) + (betweenness * 0.2)
            existing = persona.influence_score or 0
            new_score = (existing * 0.5) + (pr_norm * 0.3) + (bt_norm * 0.2)
            persona.influence_score = round(new_score, 4)
            persona.updated_at = _utc_naive()

            # Store graph community in raw_metadata-style field
            # We can store it in the persona's active_topics or as part of influence data
            if persona.active_topics is None:
                persona.active_topics = []
