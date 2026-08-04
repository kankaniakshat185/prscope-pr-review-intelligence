// Shapes returned by the FastAPI backend. Kept in sync by hand with
// backend/app/schemas/pr.py — there's no shared codegen between the two.

export interface ScoreFactor {
  name: string;
  weight: number;
  reason: string;
}

export interface RiskScore {
  score: number;
  category: "Low Risk" | "Medium Risk" | "High Risk";
  factor_breakdown: ScoreFactor[];
}

export interface Reviewability {
  score: number;
  factor_breakdown: ScoreFactor[];
}

export interface SecurityFinding {
  name: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  file: string;
  confidence: number;
  reason: string;
  recommendation: string;
  snippet: string;
  ai_explanation?: string;
  ai_recommendation?: string;
  ai_impact_summary?: string;
}

export interface ArchitectureViolation {
  file: string;
  rule: string;
  explanation: string;
}

export interface DependencyGraphFunction {
  function: string;
  calls: string[];
  called_by: string[];
  // "file:name" pairs - callers found anywhere in the repo via the
  // persisted index (see repo_index_engine.py), not just this PR's own
  // changed files. Present only when there's at least one such caller.
  repo_wide_called_by?: string[];
}

export interface DependencyGraphData {
  modified_functions: DependencyGraphFunction[];
  total_edges: number;
  // Whether a repo-wide index exists for this repo yet, and how fresh it
  // is - drives whether/how the UI surfaces repo_wide_called_by and the
  // "build index" affordance.
  repo_index_status?: "not_indexed" | "pending" | "indexing" | "ready" | "failed";
  repo_index_updated_at?: string | null;
}

export interface ImpactAnalysis {
  affected_modules: string[];
  affected_services: string[];
  graph_data: { nodes: { id: string }[]; links: { source: string; target: string }[] };
  dependency_graph: DependencyGraphData;
}

export interface ChangedSymbols {
  functions_modified: string[];
  functions_added: string[];
  functions_removed: string[];
  classes_modified: string[];
}

export interface SuggestedComment {
  file: string;
  issue: string;
  suggestion: string;
  reasoning: string;
  confidence: number;
  severity: "Critical" | "Warning" | "Suggestion";
}

export interface JiraContext {
  Ticket: string;
  Confidence: number;
  Coverage: string;
  Missing_Requirements: string;
}

export interface SimilarIncident {
  similarity_score: number;
  matching_incident: string;
  explanation: string;
}

// Matches backend PRDeterministicResponse: returned by POST /analyze, no LLM
// call involved, so this arrives fast and the UI can render it immediately.
export interface PRDeterministicData {
  risk_score: RiskScore;
  impact_analysis: ImpactAnalysis;
  architecture_violations: ArchitectureViolation[];
  similar_incidents: SimilarIncident[];
  changed_symbols: ChangedSymbols;
  security_findings: SecurityFinding[]; // deterministic detection only - no ai_* fields yet
  pr_type: string | null;
  reviewability: Reviewability | null;
  pr_title: string | null;
  has_tests: boolean;
}

// Matches backend PREnrichmentResponse: returned by POST /analyze/enrich,
// fetched separately (and later) since it involves several LLM calls and
// can legitimately take a minute or more.
export interface PREnrichmentData {
  review_checklist: string[];
  suggested_comments: SuggestedComment[];
  jira_context: JiraContext | null;
  executive_summary: string;
  security_findings: SecurityFinding[]; // same findings, now with ai_* fields populated
}

// The shape the UI actually works with: deterministic fields are always
// present once /analyze resolves; enrichment fields are absent (undefined)
// until /analyze/enrich resolves too - components need to render a loading
// state for those fields rather than assume they're always there.
export type PRAnalysisData = PRDeterministicData & Partial<PREnrichmentData>;

export interface AuthUser {
  username: string;
  avatar_url: string;
}

export interface SavedReview {
  id: number;
  user_id: number;
  repository: string;
  repository_owner: string;
  repository_name: string;
  pr_number: number;
  pr_title: string;
  pr_url: string;
  risk_score: number;
  risk_category: string;
  executive_summary: string;
  review_status: string;
  review_notes: string;
  created_at: string;
  updated_at: string;
  last_reviewed_at: string | null;
}

export interface ReviewEvent {
  id: number;
  review_id: number;
  event_type: string;
  description: string;
  timestamp: string;
}

export interface ReviewDecision {
  status: "REQUEST CHANGES" | "NEEDS REVIEW" | "APPROVE";
  reason: string;
  color: string;
  bg: string;
}
