import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

const STALE = 30_000; // 30s
const SIGNAL_STALE = 60_000; // 60s for cross-source signals
const SYSTEM_STALE = 30_000; // 30s for agent monitoring

export function useOverview() {
  return useQuery({ queryKey: ["overview"], queryFn: api.overview, staleTime: STALE });
}

export function usePulse(params?: Record<string, string>) {
  return useQuery({ queryKey: ["pulse", params], queryFn: () => api.pulse(params), staleTime: STALE });
}

export function useDebates() {
  return useQuery({ queryKey: ["debates"], queryFn: api.debates, staleTime: STALE });
}

export function useLeaders(params?: Record<string, string>) {
  return useQuery({ queryKey: ["leaders", params], queryFn: () => api.leaders(params), staleTime: STALE });
}

export function useResearch() {
  return useQuery({ queryKey: ["research"], queryFn: api.research, staleTime: STALE });
}

export function useFunding() {
  return useQuery({ queryKey: ["funding"], queryFn: api.funding, staleTime: STALE });
}

export function useJobs() {
  return useQuery({ queryKey: ["jobs"], queryFn: api.jobs, staleTime: STALE });
}

export function useNewsImpact() {
  return useQuery({ queryKey: ["newsImpact"], queryFn: api.newsImpact, staleTime: STALE });
}

export function useGeo() {
  return useQuery({ queryKey: ["geo"], queryFn: api.geo, staleTime: STALE });
}

export function useTopics(params?: Record<string, string>) {
  return useQuery({ queryKey: ["topics", params], queryFn: () => api.topics(params), staleTime: STALE });
}

export function useTopic(id: number) {
  return useQuery({ queryKey: ["topic", id], queryFn: () => api.topic(id), staleTime: STALE, enabled: !!id });
}

export function useTopicTimeline(id: number) {
  return useQuery({ queryKey: ["topicTimeline", id], queryFn: () => api.topicTimeline(id), staleTime: STALE, enabled: !!id });
}

export function useTopicPosts(id: number, params?: Record<string, string>) {
  return useQuery({ queryKey: ["topicPosts", id, params], queryFn: () => api.topicPosts(id, params), staleTime: STALE, enabled: !!id });
}

export function usePersonas(params?: Record<string, string>) {
  return useQuery({ queryKey: ["personas", params], queryFn: () => api.personas(params), staleTime: STALE });
}

export function usePersona(id: number) {
  return useQuery({ queryKey: ["persona", id], queryFn: () => api.persona(id), staleTime: STALE, enabled: !!id });
}

export function usePersonaPosts(id: number, params?: Record<string, string>) {
  return useQuery({ queryKey: ["personaPosts", id, params], queryFn: () => api.personaPosts(id, params), staleTime: STALE, enabled: !!id });
}

export function usePersonaGraph(id: number) {
  return useQuery({ queryKey: ["personaGraph", id], queryFn: () => api.personaGraph(id), staleTime: STALE, enabled: !!id });
}

export function useNews(params?: Record<string, string>) {
  return useQuery({ queryKey: ["news", params], queryFn: () => api.news(params), staleTime: STALE });
}

export function useSearch(q: string) {
  return useQuery({ queryKey: ["search", q], queryFn: () => api.search(q), staleTime: STALE, enabled: q.length >= 2 });
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 10_000, refetchInterval: 30_000 });
}

// Intelligence hooks
export function useProducts(params?: Record<string, string>) {
  return useQuery({ queryKey: ["products", params], queryFn: () => api.products(params), staleTime: STALE });
}

export function useMigrations() {
  return useQuery({ queryKey: ["migrations"], queryFn: api.migrations, staleTime: STALE });
}

export function useUnmetNeeds() {
  return useQuery({ queryKey: ["unmetNeeds"], queryFn: api.unmetNeeds, staleTime: STALE });
}

export function useJobAnalysis() {
  return useQuery({ queryKey: ["jobAnalysis"], queryFn: api.jobAnalysis, staleTime: STALE });
}

// Job Intelligence hooks (LLM-extracted)
export function useJobIntelSummary() {
  return useQuery({ queryKey: ["jobIntelSummary"], queryFn: api.jobIntelSummary, staleTime: STALE });
}

export function useJobIntelTechStack(params?: Record<string, string>) {
  return useQuery({ queryKey: ["jobIntelTechStack", params], queryFn: () => api.jobIntelTechStack(params), staleTime: STALE });
}

export function useJobIntelSalary(params?: Record<string, string>) {
  return useQuery({ queryKey: ["jobIntelSalary", params], queryFn: () => api.jobIntelSalary(params), staleTime: STALE });
}

export function useJobIntelHiring(params?: Record<string, string>) {
  return useQuery({ queryKey: ["jobIntelHiring", params], queryFn: () => api.jobIntelHiring(params), staleTime: STALE });
}

export function useJobIntelGeo() {
  return useQuery({ queryKey: ["jobIntelGeo"], queryFn: api.jobIntelGeo, staleTime: STALE });
}

export function useJobIntelAI() {
  return useQuery({ queryKey: ["jobIntelAI"], queryFn: api.jobIntelAI, staleTime: STALE });
}

export function useJobIntelStages() {
  return useQuery({ queryKey: ["jobIntelStages"], queryFn: api.jobIntelStages, staleTime: STALE });
}

export function useJobIntelBenefits() {
  return useQuery({ queryKey: ["jobIntelBenefits"], queryFn: api.jobIntelBenefits, staleTime: STALE });
}

export function useJobIntelSkills(params?: Record<string, string>) {
  return useQuery({ queryKey: ["jobIntelSkills", params], queryFn: () => api.jobIntelSkills(params), staleTime: STALE });
}

export function useHypeIndex(params?: Record<string, string>) {
  return useQuery({ queryKey: ["hypeIndex", params], queryFn: () => api.hypeIndex(params), staleTime: STALE });
}

export function usePainPoints(params?: Record<string, string>) {
  return useQuery({ queryKey: ["painPoints", params], queryFn: () => api.painPoints(params), staleTime: STALE });
}

export function useLeaderShifts() {
  return useQuery({ queryKey: ["leaderShifts"], queryFn: api.leaderShifts, staleTime: STALE });
}

export function useFundingRounds(params?: Record<string, string>) {
  return useQuery({ queryKey: ["fundingRounds", params], queryFn: () => api.fundingRounds(params), staleTime: STALE });
}

export function useTopicPlatformTones(id: number) {
  return useQuery({ queryKey: ["topicPlatformTones", id], queryFn: () => api.topicPlatformTones(id), staleTime: STALE, enabled: !!id });
}

// ── Cross-Source Signal Hooks ─────────────────────────────────

export function useResearchPipeline(params?: Record<string, string>) {
  return useQuery({ queryKey: ["researchPipeline", params], queryFn: () => api.researchPipeline(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useTractionScores(params?: Record<string, string>) {
  return useQuery({ queryKey: ["tractionScores", params], queryFn: () => api.tractionScores(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useTechnologyLifecycle(params?: Record<string, string>) {
  return useQuery({ queryKey: ["technologyLifecycle", params], queryFn: () => api.technologyLifecycle(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useMarketGaps(params?: Record<string, string>) {
  return useQuery({ queryKey: ["marketGaps", params], queryFn: () => api.marketGaps(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useCompetitiveThreats(params?: Record<string, string>) {
  return useQuery({ queryKey: ["competitiveThreats", params], queryFn: () => api.competitiveThreats(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function usePlatformDivergence(params?: Record<string, string>) {
  return useQuery({ queryKey: ["platformDivergence", params], queryFn: () => api.platformDivergence(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useSmartMoney(params?: Record<string, string>) {
  return useQuery({ queryKey: ["smartMoney", params], queryFn: () => api.smartMoney(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useTalentFlow(params?: Record<string, string>) {
  return useQuery({ queryKey: ["talentFlow", params], queryFn: () => api.talentFlow(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useNarrativeShifts(params?: Record<string, string>) {
  return useQuery({ queryKey: ["narrativeShifts", params], queryFn: () => api.narrativeShifts(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useSignalSummary() {
  return useQuery({ queryKey: ["signalSummary"], queryFn: api.signalSummary, staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useInsights(params?: Record<string, string>) {
  return useQuery({ queryKey: ["insights", params], queryFn: () => api.insights(params), staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

export function useCrossSourceHighlights() {
  return useQuery({ queryKey: ["crossSourceHighlights"], queryFn: api.crossSourceHighlights, staleTime: SIGNAL_STALE, refetchInterval: SIGNAL_STALE });
}

// ── Agent Management Hooks ────────────────────────────────────

export function useAgentStatus() {
  return useQuery({ queryKey: ["agentStatus"], queryFn: api.agentStatus, staleTime: SYSTEM_STALE, refetchInterval: SYSTEM_STALE });
}

export function useAgentRuns(params?: Record<string, string>) {
  return useQuery({ queryKey: ["agentRuns", params], queryFn: () => api.agentRuns(params), staleTime: SYSTEM_STALE, refetchInterval: SYSTEM_STALE });
}

export function useAgentRunDetail(id: number) {
  return useQuery({ queryKey: ["agentRunDetail", id], queryFn: () => api.agentRunDetail(id), staleTime: SYSTEM_STALE, enabled: !!id });
}

export function useAgentCosts(params?: Record<string, string>) {
  return useQuery({ queryKey: ["agentCosts", params], queryFn: () => api.agentCosts(params), staleTime: SYSTEM_STALE });
}

export function useTriggerAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.triggerAgent(name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agentStatus"] }); qc.invalidateQueries({ queryKey: ["agentRuns"] }); },
  });
}

export function useTriggerAllAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerAllAgents(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agentStatus"] }); qc.invalidateQueries({ queryKey: ["agentRuns"] }); },
  });
}

export function useAgentOutput(name: string) {
  return useQuery({ queryKey: ["agentOutput", name], queryFn: () => api.agentOutput(name), staleTime: SIGNAL_STALE, enabled: !!name });
}

// ── Source Data Hooks ─────────────────────────────────────────

export function useGithubTrending(params?: Record<string, string>) {
  return useQuery({ queryKey: ["githubTrending", params], queryFn: () => api.githubTrending(params), staleTime: SIGNAL_STALE });
}

export function useHfTrending(params?: Record<string, string>) {
  return useQuery({ queryKey: ["hfTrending", params], queryFn: () => api.hfTrending(params), staleTime: SIGNAL_STALE });
}

export function usePackageTrends(params?: Record<string, string>) {
  return useQuery({ queryKey: ["packageTrends", params], queryFn: () => api.packageTrends(params), staleTime: SIGNAL_STALE });
}

export function useYcBatches(params?: Record<string, string>) {
  return useQuery({ queryKey: ["ycBatches", params], queryFn: () => api.ycBatches(params), staleTime: SIGNAL_STALE });
}

export function useSoTrends(params?: Record<string, string>) {
  return useQuery({ queryKey: ["soTrends", params], queryFn: () => api.soTrends(params), staleTime: SIGNAL_STALE });
}

export function usePhRecent(params?: Record<string, string>) {
  return useQuery({ queryKey: ["phRecent", params], queryFn: () => api.phRecent(params), staleTime: SIGNAL_STALE });
}

// ── Product Reviews Hooks ────────────────────────────────────

export function useProductReviews(params?: Record<string, string>) {
  return useQuery({ queryKey: ["productReviews", params], queryFn: () => api.productReviews(params), staleTime: STALE });
}

export function useProductReviewSummary() {
  return useQuery({ queryKey: ["productReviewSummary"], queryFn: api.productReviewSummary, staleTime: STALE });
}

// ── Gig Board Hooks ──────────────────────────────────────────

export function useGigBoard(params?: Record<string, string>) {
  return useQuery({ queryKey: ["gigBoard", params], queryFn: () => api.gigBoard(params), staleTime: STALE });
}

export function useGigSummary() {
  return useQuery({ queryKey: ["gigSummary"], queryFn: api.gigSummary, staleTime: STALE });
}

export function useGigTrends() {
  return useQuery({ queryKey: ["gigTrends"], queryFn: api.gigTrends, staleTime: STALE });
}

// ── Custom Market Research Hooks ────────────────────────────

export function useResearchProjects(params?: Record<string, string>) {
  return useQuery({ queryKey: ["researchProjects", params], queryFn: () => api.researchProjects(params), staleTime: STALE });
}

export function useResearchProject(id: number) {
  return useQuery({ queryKey: ["researchProject", id], queryFn: () => api.researchProject(id), staleTime: 5_000, enabled: !!id, refetchInterval: 5_000 });
}

export function useResearchInsights(id: number) {
  return useQuery({ queryKey: ["researchInsights", id], queryFn: () => api.researchInsights(id), staleTime: STALE, enabled: !!id });
}

export function useResearchContacts(id: number, params?: Record<string, string>) {
  return useQuery({ queryKey: ["researchContacts", id, params], queryFn: () => api.researchContacts(id, params), staleTime: STALE, enabled: !!id });
}

export function useResearchPosts(id: number, params?: Record<string, string>) {
  return useQuery({ queryKey: ["researchPosts", id, params], queryFn: () => api.researchPosts(id, params), staleTime: STALE, enabled: !!id });
}

export function useCreateResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string; initial_terms: string[] }) => api.createResearchProject(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["researchProjects"] }); },
  });
}

export function useRunResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.runResearch(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["researchProjects"] }); },
  });
}

export function useDeleteResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteResearch(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["researchProjects"] }); },
  });
}
