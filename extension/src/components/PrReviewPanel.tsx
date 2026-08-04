"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AlertCircle, CheckCircle, ShieldAlert, Layout, Code2, ClipboardCopy, GitPullRequest, GitCommit, Save, Send, Link as LinkIcon, Network } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DependencyGraph from "@/components/DependencyGraph";
import type { PRAnalysisData, ReviewDecision, SuggestedComment } from "@/lib/types";
import { boxStyle, headerStyle, buttonStyle, primaryButtonStyle, textPrimary, textSecondary, inputStyle, selectChevronStyle } from "@/lib/styles";

const markdownComponents = {
  p: ({ ...props }) => <p className="mb-2 last:mb-0" {...props} />,
  ul: ({ ...props }) => <ul className="list-disc pl-4 mb-2" {...props} />,
  ol: ({ ...props }) => <ol className="list-decimal pl-4 mb-2" {...props} />,
};

function EnrichmentPending({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-4">
      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#8b949e]" />
      <span className={`text-xs ${textSecondary} animate-pulse`}>{label}</span>
    </div>
  );
}

function RepoIndexStatus({
  status,
  updatedAt,
  building,
  onBuild,
}: {
  status: "not_indexed" | "pending" | "indexing" | "ready" | "failed" | undefined;
  updatedAt: string | null | undefined;
  building: boolean;
  onBuild: () => void;
}) {
  const effectiveStatus = building ? "indexing" : status || "not_indexed";

  return (
    <div className="flex items-center gap-2 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md p-3 text-xs">
      {effectiveStatus === "indexing" || effectiveStatus === "pending" ? (
        <>
          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-[#8b949e] flex-shrink-0" />
          <span className={textSecondary}>Building full-repo index… this can take a minute for large repos.</span>
        </>
      ) : effectiveStatus === "ready" ? (
        <>
          <span className="text-[var(--color-success-fg,#3fb950)]">●</span>
          <span className={textSecondary}>
            Full-repo index is up to date{updatedAt ? ` (as of ${new Date(updatedAt).toLocaleString()})` : ""}.
          </span>
          <button onClick={onBuild} className="ml-auto underline whitespace-nowrap">Refresh</button>
        </>
      ) : effectiveStatus === "failed" ? (
        <>
          <span className="text-[var(--color-danger-fg,#da3633)]">●</span>
          <span className={textSecondary}>Full-repo indexing failed.</span>
          <button onClick={onBuild} className="ml-auto underline whitespace-nowrap">Retry</button>
        </>
      ) : (
        <>
          <span className={textSecondary}>No full-repo index yet - callers outside this PR&apos;s changed files aren&apos;t visible.</span>
          <button onClick={onBuild} className="ml-auto underline whitespace-nowrap">Build Index</button>
        </>
      )}
    </div>
  );
}

function getReviewDecision(data: PRAnalysisData): ReviewDecision {
  const { risk_score, security_findings, architecture_violations, pr_type, has_tests } = data;
  const hasSec = security_findings && security_findings.length > 0;
  const hasArch = architecture_violations && architecture_violations.length > 0;
  const score = risk_score?.score || 0;
  const isCriticalSec = hasSec && security_findings.some((f) => f.severity === "Critical");

  let total_up = 0;
  let total_down = 0;
  data.impact_analysis?.dependency_graph?.modified_functions?.forEach((f) => {
    total_up += f.called_by?.length || 0;
    total_down += f.calls?.length || 0;
  });
  const highDep = total_up + total_down > 10;

  if (isCriticalSec || hasSec) {
    return { status: "REQUEST CHANGES", reason: "Security concerns detected. Approval is not recommended until issues are resolved.", color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
  }
  if (score >= 7) {
    return { status: "REQUEST CHANGES", reason: `High risk score (${score}/10). Significant codebase modifications require deep manual review.`, color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
  }
  if (hasArch) {
    return { status: "REQUEST CHANGES", reason: "Architecture violations detected. Resolving architectural constraints is required.", color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
  }
  if (score >= 7 && !has_tests && pr_type !== "DOCS" && pr_type !== "TEST") {
    return { status: "REQUEST CHANGES", reason: "High risk change with no test coverage updates. Tests are required.", color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
  }
  if (score >= 4 && score <= 6) {
    return { status: "NEEDS REVIEW", reason: `Moderate risk score (${score}/10). Manual verification recommended.`, color: "text-[var(--color-attention-fg,#d29922)]", bg: "bg-[var(--color-attention-fg,#d29922)]" };
  }
  if ((score >= 4 || score <= 6) && highDep) {
    return { status: "NEEDS REVIEW", reason: "Moderate dependency impact detected. Core components were modified. Manual verification is recommended.", color: "text-[var(--color-attention-fg,#d29922)]", bg: "bg-[var(--color-attention-fg,#d29922)]" };
  }
  if (score <= 3 && !hasSec && !hasArch) {
    return { status: "APPROVE", reason: "Low risk change. Tests are present (or NA). No security concerns detected. No architecture violations found.", color: "text-[var(--color-success-fg,#3fb950)]", bg: "bg-[var(--color-success-fg,#3fb950)]" };
  }

  return { status: "NEEDS REVIEW", reason: "Standard review recommended.", color: "text-[var(--color-attention-fg,#d29922)]", bg: "bg-[var(--color-attention-fg,#d29922)]" };
}

export function PrReviewPanel({
  owner,
  repo,
  pr,
  token,
  apiBase,
  data,
  loading,
  error,
  enriching,
  enrichError,
  onRetry,
  onRetryEnrichment,
}: {
  owner: string;
  repo: string;
  pr: string;
  token: string | null;
  apiBase: string;
  data: PRAnalysisData | null;
  loading: boolean;
  error: string;
  enriching: boolean;
  enrichError: string;
  onRetry: () => void;
  onRetryEnrichment: () => void;
}) {
  const [noteStatus, setNoteStatus] = useState("IN_PROGRESS");
  const [noteText, setNoteText] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [postingComment, setPostingComment] = useState<string | null>(null);
  const [postingStatus, setPostingStatus] = useState(false);
  const [indexBuilding, setIndexBuilding] = useState(false);
  const [indexBuildMessage, setIndexBuildMessage] = useState<string | null>(null);

  const saveReviewWorkspace = async () => {
    if (!token || !data) {
      alert("Please login via GitHub to save reviews.");
      return;
    }
    setNoteSaving(true);
    try {
      const response = await fetch(`${apiBase}/api/analysis/workspace/reviews`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          repository: `${owner}/${repo}`,
          repository_owner: owner,
          repository_name: repo,
          pr_number: parseInt(pr, 10),
          pr_title: data.pr_title || `${owner}/${repo} #${pr}`,
          pr_url: `https://github.com/${owner}/${repo}/pull/${pr}`,
          risk_score: data.risk_score.score,
          risk_category: data.risk_score.category,
          executive_summary: data.executive_summary,
          review_status: noteStatus,
          review_notes: noteText
        }),
      });
      if (response.ok) {
        alert("Review Saved Successfully!");
      }
    } catch (err) {
      console.error(err);
      alert("Failed to save review.");
    } finally {
      setNoteSaving(false);
    }
  };

  const postCommentToGithub = async (comment: SuggestedComment, index: number) => {
    if (!token) {
      alert("Please login via GitHub to post comments.");
      return;
    }
    const githubToken = localStorage.getItem("prscope_github_token");
    if (!githubToken) {
      alert("Please provide your GitHub Personal Access Token in Settings to post comments.");
      return;
    }
    setPostingComment(index.toString());
    try {
      const response = await fetch(`${apiBase}/api/analysis/post-comment`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          repo_url: `https://github.com/${owner}/${repo}`,
          pr_number: parseInt(pr, 10),
          comment_body: `**PRScope Suggestion (${comment.file})**\n\n**Issue**: ${comment.issue}\n**Reasoning**: ${comment.reasoning}\n\n**Suggestion**: ${comment.suggestion}`,
          github_token: githubToken
        }),
      });
      if (response.ok) {
        alert("Comment posted to GitHub!");
      } else {
        alert("Failed to post comment.");
      }
    } catch (err) {
      console.error(err);
      alert("Error posting comment.");
    } finally {
      setPostingComment(null);
    }
  };

  const buildRepoIndex = async () => {
    if (!token) {
      alert("Please login via GitHub to build the repo index.");
      return;
    }
    setIndexBuilding(true);
    setIndexBuildMessage(null);
    try {
      const response = await fetch(`${apiBase}/api/analysis/index/build`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ repo_url: `https://github.com/${owner}/${repo}` }),
      });
      const result = await response.json();
      if (response.ok) {
        // The build runs in the background on the server - there's no live
        // status feed here, so this deliberately doesn't claim it's done.
        setIndexBuildMessage(
          result.status === "already_in_progress"
            ? "Index build already in progress — re-run analysis in a bit to see repo-wide results."
            : "Index build started — re-run analysis in a bit to see repo-wide results."
        );
      } else {
        setIndexBuildMessage("Failed to start index build.");
      }
    } catch (err) {
      console.error(err);
      setIndexBuildMessage("Error starting index build.");
    } finally {
      setIndexBuilding(false);
    }
  };

  const publishStatusToGithub = async () => {
    if (!token) {
      alert("Please login via GitHub to publish a status.");
      return;
    }
    const githubToken = localStorage.getItem("prscope_github_token");
    if (!githubToken) {
      alert("Please provide your GitHub Personal Access Token in Settings to publish a status.");
      return;
    }
    if (!data) return;

    // Deterministic fields only, so this works before AI enrichment finishes -
    // it's the same verdict logic already shown in the Recommended Action card.
    const decision = getReviewDecision(data);
    const state = decision.status === "REQUEST CHANGES" ? "failure" : decision.status === "NEEDS REVIEW" ? "pending" : "success";

    setPostingStatus(true);
    try {
      const response = await fetch(`${apiBase}/api/analysis/post-status`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          repo_url: `https://github.com/${owner}/${repo}`,
          pr_number: parseInt(pr, 10),
          state,
          description: `PRScope: ${decision.status} - ${decision.reason}`,
          github_token: githubToken
        }),
      });
      if (response.ok) {
        alert("Status published to GitHub - check the PR's Checks section.");
      } else {
        alert("Failed to publish status.");
      }
    } catch (err) {
      console.error(err);
      alert("Error publishing status.");
    } finally {
      setPostingStatus(false);
    }
  };

  const copySnapshot = () => {
    if (!data || data.executive_summary === undefined) return; // AI content not ready yet
    const securityTxt = data.security_findings?.length > 0
      ? data.security_findings.map((f) => `- ${f.severity}: ${f.name}`).join("\n")
      : "None";

    let total_up = 0;
    let total_down = 0;
    data.impact_analysis?.dependency_graph?.modified_functions?.forEach((f) => {
      total_up += f.called_by?.length || 0;
      total_down += f.calls?.length || 0;
    });
    const depImpact = (total_up + total_down > 10) ? "High" : (total_up + total_down > 5) ? "Medium" : "Low";

    const ts = new Date().toLocaleString();

    const archTxt = data.architecture_violations?.length > 0
      ? data.architecture_violations.map((f) => `- ${f.rule}: ${f.explanation}`).join("\n")
      : "None";

    const jiraTxt = data.jira_context ? `Ticket: ${data.jira_context.Ticket}\nConfidence: ${data.jira_context.Confidence}\nCoverage: ${data.jira_context.Coverage}\nMissing Requirements: ${data.jira_context.Missing_Requirements}` : "None";

    const prType = data.pr_type || "Unknown";
    const decision = getReviewDecision(data);

    const md = `# PRScope Review Snapshot\n\n**Repository**: ${owner}/${repo}\n**PR Number**: #${pr}\n**PR URL**: https://github.com/${owner}/${repo}/pull/${pr}\n**Timestamp**: ${ts}\n\n**PR Type**: ${prType}\n**Risk Score**: ${data.risk_score.score}/10 (${data.risk_score.category})\n**Reviewability Score**: ${data.reviewability?.score ?? "N/A"}/10\n**Review Decision**: ${decision.status}\n**Decision Reason**: ${decision.reason}\n\n**Status**: ${noteStatus}\n\n**Security Findings**:\n${securityTxt}\n\n**Architecture Violations**:\n${archTxt}\n\n**Dependency Impact**: ${depImpact} (${total_up} upstream / ${total_down} downstream)\n\n**Jira Context**:\n${jiraTxt}\n\n**Review Notes**:\n${noteText || "None"}\n\n**Executive Summary**:\n${data.executive_summary}`;

    window.parent.postMessage({ type: "COPY_TO_CLIPBOARD", text: md }, "https://github.com");
    alert("Review Snapshot copied to clipboard!");
  };

  return (
    <>
      {loading && (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#8b949e]"></div>
          <p className={`text-sm ${textSecondary} animate-pulse`}>Analyzing Pull Request Workspace...</p>
        </div>
      )}

      {error && (
        <div className="bg-[#ffebe9] border border-[#ff8182] text-[#24292f] p-4 rounded-md mb-6 flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-[#cf222e]" />
          <p className="font-medium text-sm">{error}</p>
          <button onClick={onRetry} className="ml-auto underline">Retry</button>
        </div>
      )}

      {enrichError && (
        <div className="bg-[#ffebe9] border border-[#ff8182] text-[#24292f] p-3 rounded-md mb-4 flex items-center gap-2 text-sm">
          <AlertCircle className="h-4 w-4 text-[#cf222e] flex-shrink-0" />
          <p>{enrichError} (deterministic results below are unaffected)</p>
          <button onClick={onRetryEnrichment} className="ml-auto underline whitespace-nowrap">Retry</button>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <button
              onClick={copySnapshot}
              disabled={data.executive_summary === undefined}
              title={data.executive_summary === undefined ? "Waiting for AI-generated content to finish" : undefined}
              className={`flex-1 flex items-center justify-center gap-2 ${buttonStyle} whitespace-nowrap ${data.executive_summary === undefined ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <ClipboardCopy className="h-4 w-4" />
              Copy Snapshot
            </button>
            <button
              onClick={publishStatusToGithub}
              disabled={postingStatus}
              title="Publish the risk verdict as a commit status, visible in the PR's GitHub Checks section"
              className={`flex-1 flex items-center justify-center gap-2 ${buttonStyle} whitespace-nowrap ${postingStatus ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <GitCommit className="h-4 w-4" />
              {postingStatus ? "Publishing..." : "Publish Status"}
            </button>
            {data.pr_type && (
              <div className={`flex-1 flex items-center justify-center px-3 py-1.5 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] rounded-md text-sm whitespace-nowrap`}>
                <span className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mr-1.5 text-xs font-semibold uppercase tracking-wide">PR Type:</span>
                <span className="font-medium text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">{data.pr_type}</span>
              </div>
            )}
          </div>
          {/* 1. Risk Assessment */}
          <div className={boxStyle}>
            <div className={`${headerStyle} flex items-center justify-between`}>
              <h3 className={`text-sm font-semibold flex items-center gap-2 ${textPrimary} m-0`}>
                Risk Assessment
              </h3>
              <Badge
                variant="outline"
                className={
                  data.risk_score.category === "High Risk" ? "text-[#f85149] border-[#f85149] bg-transparent" :
                    data.risk_score.category === "Medium Risk" ? "text-[var(--color-attention-fg,#d29922)] border-[#d29922] bg-transparent" :
                      "text-[var(--color-success-fg,#3fb950)] border-[#3fb950] bg-transparent"
                }
              >
                {data.risk_score.category}
              </Badge>
            </div>
            <div className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))]">
              <div className="flex items-end gap-2 mb-3">
                <span className="text-2xl font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] leading-none">{data.risk_score.score}</span>
                <span className={`text-sm ${textSecondary} leading-none mb-0.5`}>/ 10</span>
              </div>
              <Progress
                value={data.risk_score.score * 10}
                className={`h-1.5 mb-4 bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] ${data.risk_score.category === "High Risk" ? "[&>div]:bg-[var(--color-danger-bg,var(--color-danger-emphasis,#da3633))]" :
                    data.risk_score.category === "Medium Risk" ? "[&>div]:bg-[#bf8700]" :
                      "[&>div]:bg-[#1f7530]"
                  }`}
              />
              <div className="space-y-2 mt-4 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] p-3 rounded-md border border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                <div className={`text-xs font-semibold ${textSecondary} mb-2 uppercase tracking-wide`}>Risk Breakdown</div>
                {data.risk_score.factor_breakdown && data.risk_score.factor_breakdown.map((factor, i) => (
                  <div key={i} className="text-xs mb-2 last:mb-0">
                    <div className="flex justify-between font-medium text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                      <span>{factor.name}</span>
                      <span className="text-[var(--color-attention-fg,#d29922)]">+{factor.weight}</span>
                    </div>
                    <div className={`${textSecondary} mt-0.5`}>{factor.reason}</div>
                  </div>
                ))}
                {(!data.risk_score.factor_breakdown || data.risk_score.factor_breakdown.length === 0) && (
                  <div className={`text-xs ${textSecondary}`}>No high risk factors detected.</div>
                )}
              </div>
            </div>
          </div>

          {/* 1.5. Reviewability Score */}
          {data.reviewability && (
            <div className={boxStyle}>
              <div className={`${headerStyle} flex items-center justify-between`}>
                <h3 className={`text-sm font-semibold flex items-center gap-2 ${textPrimary} m-0`}>
                  Reviewability
                </h3>
              </div>
              <div className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))]">
                <div className="flex items-end gap-2 mb-3">
                  <span className={`text-2xl font-semibold leading-none ${data.reviewability.score >= 8 ? "text-[var(--color-success-fg,#3fb950)]" : data.reviewability.score >= 4 ? "text-[var(--color-attention-fg,#d29922)]" : "text-[var(--color-danger-fg,#da3633)]"}`}>
                    {data.reviewability.score}
                  </span>
                  <span className={`text-sm ${textSecondary} leading-none mb-0.5`}>/ 10</span>
                  <span className={`text-sm font-semibold ml-2 ${data.reviewability.score >= 8 ? "text-[var(--color-success-fg,#3fb950)]" : data.reviewability.score >= 4 ? "text-[var(--color-attention-fg,#d29922)]" : "text-[var(--color-danger-fg,#da3633)]"}`}>
                    {data.reviewability.score >= 8 ? "High Reviewability" : data.reviewability.score >= 4 ? "Medium Reviewability" : "Low Reviewability"}
                  </span>
                </div>
                <Progress
                  value={data.reviewability.score * 10}
                  className={`h-1.5 mb-4 bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] ${data.reviewability.score >= 8 ? "[&>div]:bg-[var(--color-success-fg,#3fb950)]" :
                      data.reviewability.score >= 4 ? "[&>div]:bg-[var(--color-attention-fg,#d29922)]" :
                        "[&>div]:bg-[var(--color-danger-fg,#da3633)]"
                    }`}
                />
                <div className="space-y-2 mt-4 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] p-3 rounded-md border border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                  <div className={`text-xs font-semibold ${textSecondary} mb-2 uppercase tracking-wide`}>Factors</div>
                  {data.reviewability.factor_breakdown && data.reviewability.factor_breakdown.map((factor, i) => (
                    <div key={i} className="text-xs mb-2 last:mb-0">
                      <div className="flex justify-between font-medium text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                        <span>{factor.name}</span>
                        <span className={factor.weight > 0 ? "text-[var(--color-success-fg,#3fb950)]" : "text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]"}>+{factor.weight}</span>
                      </div>
                      <div className={`${textSecondary} mt-0.5`}>{factor.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Accordions Container */}
          <Accordion multiple className="w-full space-y-3" defaultValue={["executive_summary"]}>

            {/* 3. Security Findings */}
            <AccordionItem value="security" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <ShieldAlert className="h-4 w-4" />
                  Security Findings
                  {data.security_findings?.length > 0 && (
                    <Badge className="ml-2 bg-[var(--color-danger-bg,var(--color-danger-emphasis,#da3633))] text-white border-transparent text-[10px] py-0">{data.security_findings.length}</Badge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                {data.security_findings && data.security_findings.length > 0 ? (
                  <div className="space-y-4">
                    {data.security_findings.map((finding, i) => (
                      <div key={i} className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`h-2 w-2 rounded-full ${finding.severity === "Critical" ? "bg-[#f85149]" : finding.severity === "High" ? "bg-[#d29922]" : "bg-[#3fb950]"}`} />
                            <span className="text-sm font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">{finding.name}</span>
                          </div>
                          <Badge variant="outline" className="border-[var(--borderColor-default,var(--color-border-default,#30363d))] text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">{finding.confidence}% Confidence</Badge>
                        </div>
                        <div className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-2 font-mono truncate bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] p-1.5 rounded border border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                          {finding.file}
                        </div>
                        <div className="text-xs text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] mb-3">{finding.reason}</div>
                        {enriching && !finding.ai_explanation && (
                          <div className={`text-[11px] ${textSecondary} italic animate-pulse`}>Generating AI explanation…</div>
                        )}
                        {finding.ai_explanation && (
                          <div className="mt-3 p-3 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-xs space-y-3">
                            <div className="text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                              <div className="font-semibold mb-1">AI Explanation:</div>
                              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{finding.ai_explanation}</ReactMarkdown>
                            </div>
                            <div className="text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                              <div className="font-semibold text-[var(--color-success-fg,#3fb950)] mb-1">Recommendation:</div>
                              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{finding.ai_recommendation}</ReactMarkdown>
                            </div>
                            <div className="text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                              <div className="font-semibold text-[var(--color-attention-fg,#d29922)] mb-1">Impact:</div>
                              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{finding.ai_impact_summary}</ReactMarkdown>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={`text-xs ${textSecondary}`}>No deterministic security vulnerabilities detected.</div>
                )}
              </AccordionContent>
            </AccordionItem>

            {/* 6. Dependency Intelligence */}
            <AccordionItem value="dependency" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <Network className="h-4 w-4" />
                  Dependency Intelligence
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                <div className="space-y-4">
                  <p className={`text-[11px] ${textSecondary}`}>
                    Call graph is built from real file content for Python and JS/TS files. It&apos;s still scoped to this PR&apos;s own changed files by default — build a full-repo index below to also surface callers in files this PR never touched.
                  </p>

                  <RepoIndexStatus
                    status={data.impact_analysis?.dependency_graph?.repo_index_status}
                    updatedAt={data.impact_analysis?.dependency_graph?.repo_index_updated_at}
                    building={indexBuilding}
                    onBuild={buildRepoIndex}
                  />
                  {indexBuildMessage && (
                    <p className={`text-[11px] ${textSecondary} italic`}>{indexBuildMessage}</p>
                  )}
                  {(() => {
                    let total_up = 0;
                    let total_down = 0;
                    data.impact_analysis?.dependency_graph?.modified_functions?.forEach((f) => {
                      total_up += f.called_by?.length || 0;
                      total_down += f.calls?.length || 0;
                    });
                    const depImpact = (total_up + total_down > 10) ? "High" : (total_up + total_down > 5) ? "Medium" : "Low";
                    const impactColor = depImpact === "High" ? "text-[var(--color-danger-fg,#da3633)]" : depImpact === "Medium" ? "text-[var(--color-attention-fg,#d29922)]" : "text-[var(--color-success-fg,#3fb950)]";

                    return (
                      <div className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] p-3 rounded-md border border-[var(--borderColor-default,var(--color-border-default,#30363d))] mb-4">
                        <div className="text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase tracking-wide mb-1">Dependency Impact</div>
                        <div className="flex items-center justify-between">
                          <span className={`font-semibold ${impactColor}`}>{depImpact}</span>
                          <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">{total_up} upstream / {total_down} downstream</span>
                        </div>
                      </div>
                    );
                  })()}

                  <div className={`text-xs ${textSecondary}`}>
                    Impacted Services: {data.impact_analysis?.affected_services?.join(", ") || "None"} <br />
                    Impacted Modules: {data.impact_analysis?.affected_modules?.join(", ") || "None"}
                  </div>

                  {data.impact_analysis?.dependency_graph?.modified_functions?.map((dep, i) => (
                    <div key={i} className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md p-3">
                      <div className="text-sm font-mono font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] break-all mb-2">{dep.function}</div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase font-bold mb-1">Called By (Upstream)</div>
                          {dep.called_by?.length > 0 ? (
                            <ul className="text-xs text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] space-y-1">
                              {dep.called_by.map((c, idx) => <li key={idx} className="flex gap-1 break-all"><LinkIcon className="h-3 w-3 mt-0.5 flex-shrink-0 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" /><span>{c}</span></li>)}
                            </ul>
                          ) : <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">None detected</span>}
                          {dep.repo_wide_called_by && dep.repo_wide_called_by.length > 0 && (
                            <div className="mt-2">
                              <div className="text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase font-bold mb-1">+ Repo-Wide (outside this PR)</div>
                              <ul className="text-xs text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] space-y-1">
                                {dep.repo_wide_called_by.map((c, idx) => <li key={idx} className="flex gap-1 break-all"><Network className="h-3 w-3 mt-0.5 flex-shrink-0 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" /><span>{c}</span></li>)}
                              </ul>
                            </div>
                          )}
                        </div>
                        <div>
                          <div className="text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase font-bold mb-1">Calls (Downstream)</div>
                          {dep.calls?.length > 0 ? (
                            <ul className="text-xs text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] space-y-1">
                              {dep.calls.map((c, idx) => <li key={idx} className="flex gap-1 break-all"><LinkIcon className="h-3 w-3 mt-0.5 flex-shrink-0 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" /><span>{c}</span></li>)}
                            </ul>
                          ) : <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">None detected</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                  {(!data.impact_analysis?.dependency_graph?.modified_functions || data.impact_analysis?.dependency_graph?.modified_functions.length === 0) && (
                    <div className={`text-xs ${textSecondary}`}>No direct function dependencies extracted from patch.</div>
                  )}

                  {data.impact_analysis?.dependency_graph && (
                    <div className="mt-4">
                      <div className="text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase tracking-wide mb-2">Visual Graph</div>
                      <DependencyGraph graphData={data.impact_analysis.dependency_graph} />
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 7. Changed Symbols */}
            <AccordionItem value="symbols" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <Code2 className="h-4 w-4" />
                  Changed Symbols
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                <div className="space-y-4">
                  {data.changed_symbols && data.changed_symbols.functions_modified?.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold ${textSecondary} mb-2`}>Functions Modified:</div>
                      <div className="flex flex-wrap gap-2">
                        {data.changed_symbols.functions_modified.map((f, i) => (
                          <span key={i} className="text-[12px] bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] px-2 py-1 rounded-md text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] font-mono">{f}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {data.changed_symbols && data.changed_symbols.functions_added?.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold ${textSecondary} mb-2`}>Functions Added:</div>
                      <div className="flex flex-wrap gap-2">
                        {data.changed_symbols.functions_added.map((f, i) => (
                          <span key={i} className="text-[12px] bg-[#1f7530]/10 border border-[#1f7530]/30 px-2 py-1 rounded-md text-[var(--color-success-fg,#3fb950)] font-mono">{f}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Architecture Violations */}
            <AccordionItem value="architecture" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v4" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="m3 15 2 2 4-4" /></svg>
                  Architecture Violations
                  {data.architecture_violations?.length > 0 && (
                    <Badge className="ml-2 bg-[var(--color-danger-bg,var(--color-danger-emphasis,#da3633))] text-white border-transparent text-[10px] py-0">{data.architecture_violations.length}</Badge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                <div className="space-y-4">
                  {data.architecture_violations?.map((viol, i) => (
                    <div key={i} className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[#da3633]/30 rounded-md p-3">
                      <div className="text-sm font-semibold text-[var(--color-danger-fg,#da3633)] mb-1">{viol.rule}</div>
                      <div className={`text-xs ${textSecondary}`}>{viol.explanation}</div>
                    </div>
                  ))}
                  {(!data.architecture_violations || data.architecture_violations.length === 0) && (
                    <div className={`text-xs ${textSecondary}`}>No architecture violations detected.</div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 2. Executive Summary */}
            <AccordionItem value="executive_summary" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <Layout className="h-4 w-4" />
                  Executive Summary
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                {data.executive_summary === undefined ? (
                  <EnrichmentPending label="Generating executive summary…" />
                ) : (
                  <div className="text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] leading-relaxed max-w-none break-words">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h3: ({ ...props }) => <h3 className="text-base font-bold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] mt-6 mb-2" {...props} />,
                        p: ({ ...props }) => <p className="my-2 leading-6 whitespace-pre-wrap break-words" {...props} />,
                        ul: ({ ...props }) => <ul className="list-disc pl-5 my-2 break-words" {...props} />,
                        li: ({ ...props }) => <li className="my-1 break-words" {...props} />
                      }}
                    >
                      {data.executive_summary}
                    </ReactMarkdown>
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>

            {/* 4. Review Checklist */}
            <AccordionItem value="checklist" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <CheckCircle className="h-4 w-4" />
                  Review Checklist
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                {data.review_checklist === undefined ? (
                  <EnrichmentPending label="Generating review checklist…" />
                ) : (
                  <div className="space-y-3">
                    {data.review_checklist.map((item, i) => (
                      <div key={i} className="flex items-start gap-3 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] p-3 rounded-md shadow-sm break-words">
                        <CheckCircle className="h-4 w-4 mt-0.5 text-[var(--color-success-fg,#3fb950)] flex-shrink-0" />
                        <span className={`text-sm ${textPrimary} leading-snug whitespace-pre-wrap flex-1 min-w-0 break-words`}>{item}</span>
                      </div>
                    ))}
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>

            {/* 5. Suggested Comments */}
            <AccordionItem value="comments" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <GitPullRequest className="h-4 w-4" />
                  Suggested Comments
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                {data.suggested_comments === undefined ? (
                  <EnrichmentPending label="Generating suggested comments…" />
                ) : data.suggested_comments.length > 0 ? (
                  <div className="space-y-3">
                    {data.suggested_comments.map((comment, i) => (
                      <div key={i} className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] rounded-md border border-[var(--borderColor-default,var(--color-border-default,#30363d))] p-3">
                        <div className="flex justify-between items-start mb-2">
                          <div className={`text-xs font-mono text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] truncate max-w-[60%]`} title={comment.file}>
                            {comment.file}
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className={`text-[10px] border-[var(--borderColor-default,var(--color-border-default,#30363d))] ${comment.severity === "Critical" ? "text-[#f85149]" : comment.severity === "Warning" ? "text-[var(--color-attention-fg,#d29922)]" : "text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]"}`}>
                              {comment.severity || "Suggestion"}
                            </Badge>
                            <Badge variant="outline" className="text-[10px] border-[var(--borderColor-default,var(--color-border-default,#30363d))] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">
                              {comment.confidence}%
                            </Badge>
                          </div>
                        </div>
                        <div className={`text-sm font-semibold ${textPrimary} mb-1 leading-snug break-words whitespace-pre-wrap`}>{comment.issue}</div>
                        <div className={`text-xs ${textSecondary} mb-3 leading-relaxed break-words whitespace-pre-wrap`}>{comment.reasoning}</div>
                        <div className="text-xs text-[var(--color-success-fg,#3fb950)] bg-[#1f7530]/10 p-2.5 rounded-md mb-3 border border-[#1f7530]/20 break-words whitespace-pre-wrap">
                          <span className="font-semibold block mb-1">Suggestion:</span>
                          <span className="leading-relaxed">{comment.suggestion}</span>
                        </div>
                        <button
                          onClick={() => postCommentToGithub(comment, i)}
                          disabled={postingComment === i.toString()}
                          className={`w-full flex items-center justify-center gap-1 ${primaryButtonStyle}`}
                        >
                          <Send className="h-3 w-3" />
                          {postingComment === i.toString() ? "Posting..." : "Post to GitHub"}
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={`text-xs ${textSecondary}`}>No high-confidence comments generated.</div>
                )}
              </AccordionContent>
            </AccordionItem>
            {/* Review Decision */}
            <AccordionItem value="decision" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" /><path d="m9 12 2 2 4-4" /></svg>
                  Review Decision
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                {(() => {
                  const reviewDecision = getReviewDecision(data);
                  return (
                    <div className="flex flex-col gap-2">
                      <div className={`flex items-center gap-2 ${reviewDecision.color} font-semibold text-lg`}>
                        <div className={`w-3 h-3 rounded-full ${reviewDecision.bg}`} />
                        {reviewDecision.status}
                      </div>
                      <div className="text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">
                        {reviewDecision.reason}
                      </div>
                    </div>
                  );
                })()}
              </AccordionContent>
            </AccordionItem>


            {/* Jira Context */}
            <AccordionItem value="jira" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
                  Jira Context
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                <div className="space-y-4">
                  {data.jira_context === undefined ? (
                    <EnrichmentPending label="Checking for Jira context…" />
                  ) : data.jira_context ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase">Ticket Alignment</span>
                        <Badge variant="outline" className="border-[var(--borderColor-default,var(--color-border-default,#30363d))]">{data.jira_context.Ticket}</Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">Confidence</div>
                          <div className="text-sm font-semibold text-[var(--color-success-fg,#3fb950)]">{data.jira_context.Confidence}%</div>
                        </div>
                        <div>
                          <div className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">Coverage</div>
                          <div className="text-sm font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">{data.jira_context.Coverage}</div>
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-1">Missing Requirements</div>
                        <div className={`text-xs ${data.jira_context.Missing_Requirements !== "None detected" ? "text-[var(--color-attention-fg,#d29922)]" : "text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]"}`}>
                          {data.jira_context.Missing_Requirements}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className={`text-xs ${textSecondary}`}>No Jira ticket IDs detected in PR title or description.</div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* 8. Review Notes */}
            <AccordionItem value="review_notes" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                  <Save className="h-4 w-4" />
                  Review Notes
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                <select
                  value={noteStatus}
                  onChange={(e) => setNoteStatus(e.target.value)}
                  className={`w-full mb-3 ${inputStyle} appearance-none bg-no-repeat pr-8`}
                  style={selectChevronStyle}
                >
                  <option value="IN_PROGRESS">IN PROGRESS</option>
                  <option value="FOLLOW_UP_REQUIRED">FOLLOW UP REQUIRED</option>
                  <option value="NEEDS_CHANGES">NEEDS CHANGES</option>
                  <option value="APPROVED">APPROVED</option>
                </select>
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add personal review notes here..."
                  className={`w-full h-24 mb-3 resize-y ${inputStyle}`}
                  style={{ fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" }}
                />
                <button
                  onClick={saveReviewWorkspace}
                  disabled={noteSaving || !token}
                  className={`w-full ${primaryButtonStyle} py-2 ${!token ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  {noteSaving ? "Saving..." : "Save Review to Workspace"}
                </button>
                {!token && <p className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mt-2 text-center">Login via GitHub to save to Workspace.</p>}
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      )}
    </>
  );
}
