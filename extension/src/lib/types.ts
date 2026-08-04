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
}

export interface DependencyGraphData {
  modified_functions: DependencyGraphFunction[];
  total_edges: number;
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

export interface PRAnalysisData {
  risk_score: RiskScore;
  impact_analysis: ImpactAnalysis;
  architecture_violations: ArchitectureViolation[];
  similar_incidents: SimilarIncident[];
  review_checklist: string[];
  suggested_comments: SuggestedComment[];
  jira_context: JiraContext | null;
  executive_summary: string;
  changed_symbols: ChangedSymbols;
  security_findings: SecurityFinding[];
  pr_type: string | null;
  reviewability: Reviewability | null;
  pr_title: string | null;
  has_tests: boolean;
}

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
