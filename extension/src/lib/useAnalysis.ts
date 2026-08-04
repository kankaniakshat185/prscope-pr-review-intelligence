import { useState } from "react";
import type { PRAnalysisData } from "@/lib/types";

export function useAnalysis(apiBase: string, token: string | null) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PRAnalysisData | null>(null);
  const [error, setError] = useState("");

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
    try {
      const response = await fetch(`${apiBase}/api/analysis/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          repo_url: `https://github.com/${owner}/${repo}`,
          pr_number: parseInt(pr, 10),
          gemini_api_key: localStorage.getItem("prscope_gemini_key") || undefined,
          openai_api_key: localStorage.getItem("prscope_openai_key") || undefined,
          ai_provider: localStorage.getItem("prscope_ai_provider") || "gemini",
          custom_rules_yaml: customRulesYaml || undefined,
        }),
      });

      if (!response.ok) throw new Error("Failed to fetch analysis");
      const result: PRAnalysisData = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return { data, loading, error, fetchAnalysis };
}
