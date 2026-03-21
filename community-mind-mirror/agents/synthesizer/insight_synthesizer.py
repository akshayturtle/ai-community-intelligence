"""Insight Synthesizer — Master agent that reads ALL signal results and produces insight cards."""

from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.tools.sql_tool import SQLReadTool
from agents.tools.calculate_tool import CalculateTool
from agents.config import (
    DATABASE_URL, AGENT_TABLE_PERMISSIONS, AGENT_MODELS,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
    get_deployment_for_model,
)

INSTRUCTIONS = """\
You are the Chief Intelligence Officer. You read ALL cross-source analysis results
and produce the final actionable insight cards.

STEP 1: Read all result tables (run queries on each)

a) Latest agent outputs:
   SELECT agent_name, output, ran_at FROM agent_runs
   ORDER BY ran_at DESC LIMIT 20

b) Research pipeline results:
   SELECT * FROM research_pipeline ORDER BY id DESC LIMIT 20

c) Traction scores:
   SELECT * FROM traction_scores ORDER BY traction_score DESC LIMIT 20

d) Market gaps:
   SELECT * FROM market_gaps ORDER BY opportunity_score DESC LIMIT 10

e) Competitive threats:
   SELECT * FROM competitive_threats ORDER BY threat_score DESC LIMIT 10

f) Platform divergence:
   SELECT * FROM platform_divergence ORDER BY divergence_score DESC LIMIT 10

g) Technology lifecycle:
   SELECT * FROM technology_lifecycle ORDER BY id DESC LIMIT 20

h) Context from raw tables:
   SELECT name, status, velocity, total_mentions FROM topics
   WHERE status IN ('emerging', 'active', 'peaking') ORDER BY velocity DESC LIMIT 10

   SELECT canonical_name, total_mentions FROM discovered_products
   WHERE status = 'active' ORDER BY total_mentions DESC LIMIT 10

STEP 2: Look for CONNECTIONS between signals.
The most valuable insight combines 2-3 signals that individually seem unremarkable
but together tell a compelling story.

Examples of high-value connections:
- Research pipeline shows paper at "experimentation" + traction_scorer shows low score + market_gap shows high pain = "This research could fill an unmet need but nobody's building it yet"
- YC batch heavy in sector X + community divergence shows HN negative = "Smart money disagrees with builders — watch this space"
- Technology in "growth" stage + competitive threat rising + narrative shifting = "Market leader under pressure, window for challengers"

STEP 3: Generate 4-6 insight cards, each with:
- category: opportunity_alert / bubble_warning / thesis_forming / competitive_threat / talent_signal / early_warning
- insight: specific, numbered, actionable sentence
- signals_used: which cross-source tables informed this
- confidence: high / medium / low
- color: green (opportunity) / red (warning) / blue (informational) / yellow (watch)

QUALITY RULES:
- Never state the obvious
- Every insight must have a specific number
- Every insight must be actionable — reader knows what to DO
- If combining 2 signals produces a surprising conclusion, that's the best insight
- 3 real insights beat 6 generic ones
- Reference specific products, technologies, or sectors by name

OUTPUT FORMAT: JSON array of insight cards:
[
  {
    "category": "opportunity_alert",
    "color": "green",
    "insight": "RAG evaluation tools: 142 complaints (intensity 94), zero products, 23 job listings, 52% of YC W25 builds agents needing evaluation. 3-6 month window before crowded.",
    "signals_used": ["market_gaps", "traction_scores", "technology_lifecycle"],
    "confidence": "high",
    "recommended_action": "Build or invest in RAG evaluation tooling immediately"
  },
  {
    "category": "bubble_warning",
    "color": "red",
    "insight": "ProductX has 872 PH votes but traction score of 31. 0 non-founder GitHub contributors, 0 job listings. Classic hype-only pattern.",
    "signals_used": ["traction_scores", "platform_divergence"],
    "confidence": "high",
    "recommended_action": "Avoid investing time/money. Wait for real traction signals."
  }
]"""


def create_insight_synthesizer_agent() -> Agent:
    model_name = AGENT_MODELS["insight_synthesizer"]
    sql_tool = SQLReadTool(
        db_url=DATABASE_URL,
        allowed_tables=AGENT_TABLE_PERMISSIONS["insight_synthesizer"],
    )
    calc_tool = CalculateTool()

    return Agent(
        name="Insight Synthesizer",
        model=AzureOpenAI(
            id=get_deployment_for_model(model_name),
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        ),
        tools=[sql_tool, calc_tool],
        instructions=INSTRUCTIONS,
        markdown=False,
    )
