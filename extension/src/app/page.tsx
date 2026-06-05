"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Separator } from "@/components/ui/separator";
import { AlertCircle, CheckCircle, Search, GitPullRequest, GitMerge, ShieldAlert, Cpu, Activity, Layout, ActivityIcon } from "lucide-react";
import ForceGraph2D from 'react-force-graph-2d';

function MainDashboard() {
  const searchParams = useSearchParams();
  const owner = searchParams.get("owner");
  const repo = searchParams.get("repo");
  const pr = searchParams.get("pr");

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (owner && repo && pr) {
      fetchAnalysis(owner, repo, pr);
    }
  }, [owner, repo, pr]);

  const fetchAnalysis = async (owner: string, repo: string, pr: string) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("http://localhost:8000/api/analysis/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: `https://github.com/${owner}/${repo}`,
          pr_number: parseInt(pr, 10),
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch analysis");
      }

      const result = await response.json();
      setData(result);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  if (!owner || !repo || !pr) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-200">
        <div className="text-center p-6">
          <ShieldAlert className="mx-auto h-12 w-12 text-zinc-500 mb-4" />
          <h2 className="text-lg font-semibold">PR Copilot Active</h2>
          <p className="text-sm text-zinc-400 mt-2">Open a Pull Request on GitHub to see analysis.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200 p-4 font-sans overflow-y-auto">
      <div className="flex items-center gap-2 mb-6 border-b border-zinc-800 pb-4">
        <GitMerge className="h-6 w-6 text-indigo-500" />
        <h1 className="text-xl font-bold tracking-tight">PR Copilot</h1>
        <Badge variant="outline" className="ml-auto bg-zinc-900 border-zinc-800 text-xs">
          {owner}/{repo} #{pr}
        </Badge>
      </div>

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
          <p className="text-sm text-zinc-400 animate-pulse">Analyzing Pull Request...</p>
        </div>
      )}

      {error && (
        <Card className="bg-red-950/20 border-red-900 mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-500">
              <AlertCircle className="h-5 w-5" />
              <p className="font-medium text-sm">{error}</p>
            </div>
            <button 
              onClick={() => fetchAnalysis(owner, repo, pr)}
              className="mt-4 px-3 py-1.5 bg-red-900/50 hover:bg-red-900/80 text-red-200 text-xs rounded transition-colors"
            >
              Retry
            </button>
          </CardContent>
        </Card>
      )}

      {data && !loading && (
        <div className="space-y-6">
          {/* Executive Summary */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 font-medium flex items-center gap-2">
                <Layout className="h-4 w-4" />
                Executive Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {data.executive_summary}
              </p>
            </CardContent>
          </Card>

          {/* Risk Assessment */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm text-zinc-400 font-medium flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  Risk Assessment
                </CardTitle>
                <Badge 
                  variant="outline" 
                  className={
                    data.risk_score.category === "High Risk" ? "text-red-400 border-red-900 bg-red-950/30" : 
                    data.risk_score.category === "Medium Risk" ? "text-amber-400 border-amber-900 bg-amber-950/30" : 
                    "text-green-400 border-green-900 bg-green-950/30"
                  }
                >
                  {data.risk_score.category}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-2 mb-4">
                <span className="text-3xl font-bold text-zinc-100">{data.risk_score.score}</span>
                <span className="text-sm text-zinc-500 mb-1">/ 10</span>
              </div>
              <Progress 
                value={data.risk_score.score * 10} 
                className={`h-2 mb-4 ${
                  data.risk_score.category === "High Risk" ? "[&>div]:bg-red-500" : 
                  data.risk_score.category === "Medium Risk" ? "[&>div]:bg-amber-500" : 
                  "[&>div]:bg-green-500"
                }`}
              />
              <div className="space-y-2 mt-4">
                {data.risk_score.factor_breakdown.map((factor: any, i: number) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-zinc-400">{factor.factor}</span>
                    <span className="text-zinc-300 font-medium">{factor.value}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Architecture Validation */}
          {data.architecture_violations.length > 0 && (
            <Card className="bg-zinc-900 border-amber-900/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-zinc-400 font-medium flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-amber-500" />
                  Architecture Violations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {data.architecture_violations.map((v: any, i: number) => (
                    <div key={i} className="bg-amber-950/20 border border-amber-900/30 rounded p-3 text-xs">
                      <div className="font-mono text-amber-200/80 mb-1">{v.file}</div>
                      <div className="font-semibold text-amber-500">{v.rule}</div>
                      <div className="text-amber-200/60 mt-1">{v.explanation}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <Accordion type="single" collapsible className="w-full space-y-4">
            
            {/* Review Checklist */}
            <AccordionItem value="checklist" className="border border-zinc-800 rounded-lg bg-zinc-900 px-4">
              <AccordionTrigger className="text-sm font-medium hover:no-underline py-4">
                <div className="flex items-center gap-2 text-zinc-300">
                  <CheckCircle className="h-4 w-4" />
                  Review Checklist
                </div>
              </AccordionTrigger>
              <AccordionContent className="pt-0 pb-4">
                <ul className="space-y-2 text-sm text-zinc-400">
                  {data.review_checklist.map((item: string, i: number) => (
                    <li key={i} className="flex items-start gap-2">
                      <div className="mt-1 h-1.5 w-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </AccordionItem>

            {/* Suggested Comments */}
            <AccordionItem value="comments" className="border border-zinc-800 rounded-lg bg-zinc-900 px-4">
              <AccordionTrigger className="text-sm font-medium hover:no-underline py-4">
                <div className="flex items-center gap-2 text-zinc-300">
                  <GitPullRequest className="h-4 w-4" />
                  Suggested Comments
                </div>
              </AccordionTrigger>
              <AccordionContent className="pt-0 pb-4">
                <div className="space-y-3">
                  {data.suggested_comments.map((comment: any, i: number) => (
                    <div key={i} className="bg-zinc-950/50 rounded-md border border-zinc-800 p-3">
                      <div className="text-xs font-mono text-indigo-400 mb-2 truncate" title={comment.file}>
                        {comment.file}
                      </div>
                      <div className="text-sm font-semibold text-zinc-200 mb-1">
                        {comment.issue}
                      </div>
                      <div className="text-xs text-zinc-400 mb-2">
                        {comment.reasoning}
                      </div>
                      <div className="text-xs text-green-400 bg-green-950/20 p-2 rounded">
                        <span className="font-semibold block mb-1">Suggestion:</span>
                        {comment.suggestion}
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Similar Incidents */}
            {data.similar_incidents.length > 0 && (
              <AccordionItem value="incidents" className="border border-zinc-800 rounded-lg bg-zinc-900 px-4">
                <AccordionTrigger className="text-sm font-medium hover:no-underline py-4">
                  <div className="flex items-center gap-2 text-zinc-300">
                    <Search className="h-4 w-4" />
                    Similar Incidents
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-0 pb-4">
                  <div className="space-y-3">
                    {data.similar_incidents.map((inc: any, i: number) => (
                      <div key={i} className="border border-zinc-800 rounded p-3 text-xs bg-zinc-950/30">
                        <div className="flex items-center justify-between mb-2">
                          <Badge variant="outline" className="border-indigo-900 text-indigo-400 bg-indigo-950/30">
                            {inc.similarity_score}% Match
                          </Badge>
                        </div>
                        <div className="text-zinc-300 mb-2">{inc.matching_incident}</div>
                        <div className="text-zinc-500 italic">{inc.explanation}</div>
                      </div>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>
            )}
            
            {/* Impact Analysis Graph */}
            <AccordionItem value="impact" className="border border-zinc-800 rounded-lg bg-zinc-900 px-4">
              <AccordionTrigger className="text-sm font-medium hover:no-underline py-4">
                <div className="flex items-center gap-2 text-zinc-300">
                  <Cpu className="h-4 w-4" />
                  Impact Graph
                </div>
              </AccordionTrigger>
              <AccordionContent className="pt-0 pb-4">
                <div className="h-48 bg-zinc-950 rounded-md overflow-hidden relative border border-zinc-800">
                  {/* Note: ForceGraph2D requires actual window dimensions, using static placeholder for demo extension to avoid iframe bugs or lazy load it */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center">
                    <p className="text-xs text-zinc-400 mb-2">Impacted Services: {data.impact_analysis.affected_services.join(", ") || "None"}</p>
                    <p className="text-xs text-zinc-400">Impacted Modules: {data.impact_analysis.affected_modules.join(", ") || "None"}</p>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

          </Accordion>
        </div>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4 text-zinc-400 text-sm">Loading...</div>}>
      <MainDashboard />
    </Suspense>
  );
}
