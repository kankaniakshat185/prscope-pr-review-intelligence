import { useState } from "react";
import type { PRAnalysisData, PRDeterministicData, PREnrichmentData } from "@/lib/types";

export function useAnalysis(apiBase: string, token: string | null) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PRAnalysisData | null>(null);
  const [error, setError] = useState("");
  const [enriching, setEnriching] = useState(false);
  const [enrichError, setEnrichError] = useState("");

  const requestBody = (owner: string, repo: string, pr: string, customRulesYaml: string | null) => JSON.stringify({
    repo_url: `https://github.com/${owner}/${repo}`,
    pr_number: parseInt(pr, 10),
    gemini_api_key: localStorage.getItem("prscope_gemini_key") || undefined,
    openai_api_key: localStorage.getItem("prscope_openai_key") || undefined,
    groq_api_key: localStorage.getItem("prscope_groq_key") || undefined,
    ai_provider: localStorage.getItem("prscope_ai_provider") || "gemini",
    custom_rules_yaml: customRulesYaml || undefined,
  });

  const fetchEnrichment = async (owner: string, repo: string, pr: string, customRulesYaml: string | null) => {
    setEnriching(true);
    setEnrichError("");
    try {
      const response = await fetch(`${apiBase}/api/analysis/analyze/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: requestBody(owner, repo, pr, customRulesYaml),
      });
      if (!response.ok) throw new Error("Failed to generate AI review content");
      const enrichment: PREnrichmentData = await response.json();
      // Merge in - deterministic fields (already rendered) are untouched,
      // enrichment fields fill in and the UI's "loading" checks disappear.
      setData(prev => (prev ? { ...prev, ...enrichment } : prev));
    } catch (err) {
      setEnrichError(err instanceof Error ? err.message : "Failed to generate AI review content");
    } finally {
      setEnriching(false);
    }
  };

  const fetchAnalysis = async (
    owner: string,
    repo: string,
    pr: string,
    customRulesYaml: string | null
  ) => {
    if (!token) {
      setError("Please login with GitHub to analyze this pull request.");
      return;
    }
    setLoading(true);
    setError("");
    setEnrichError("");
    setData(null);
    try {
      const response = await fetch(`${apiBase}/api/analysis/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: requestBody(owner, repo, pr, customRulesYaml),
      });

      if (!response.ok) throw new Error("Failed to fetch analysis");
      const result: PRDeterministicData = await response.json();
      setData(result);
      setLoading(false);

      // Deterministic results are already rendered at this point. Kick off
      // the slower AI-generated content separately rather than making the
      // user wait on it before seeing anything at all.
      fetchEnrichment(owner, repo, pr, customRulesYaml);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setLoading(false);
    }
  };

  return { data, loading, error, enriching, enrichError, fetchAnalysis, fetchEnrichment };
}
