"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AlertCircle, CheckCircle, GitMerge, ShieldAlert, Cpu, Layout, Code2, ClipboardCopy, History, Save, GitPullRequest, Search, Send, Link as LinkIcon, Network } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function MainDashboard() {
  const searchParams = useSearchParams();
  const owner = searchParams.get("owner");
  const repo = searchParams.get("repo");
  const pr = searchParams.get("pr");

    const [showSettings, setShowSettings] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [keySavedMessage, setKeySavedMessage] = useState(false);

  useEffect(() => {
    setApiKey(localStorage.getItem("prscope_gemini_key") || "");
  }, []);

  const handleSaveApiKey = () => {
    localStorage.setItem("prscope_gemini_key", apiKey);
    setKeySavedMessage(true);
    setTimeout(() => setKeySavedMessage(false), 2000);
  };
  const [activeTab, setActiveTab] = useState<"PR_REVIEW" | "SAVED_REVIEWS">("PR_REVIEW");
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  
  const [noteStatus, setNoteStatus] = useState("IN_PROGRESS");
  const [noteText, setNoteText] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [postingComment, setPostingComment] = useState<string | null>(null);

  const [savedReviews, setSavedReviews] = useState<any[]>([]);
  const [filterStatus, setFilterStatus] = useState("All");
  const [sortOrder, setSortOrder] = useState("newest");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedReview, setSelectedReview] = useState<any>(null);
  const [reviewEvents, setReviewEvents] = useState<any[]>([]);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === "SYNC_THEME") {
        let styleTag = document.getElementById("github-theme-vars");
        if (!styleTag) {
          styleTag = document.createElement("style");
          styleTag.id = "github-theme-vars";
          document.head.appendChild(styleTag);
        }
        styleTag.innerHTML = event.data.style;
      }
    };
    window.addEventListener("message", handleMessage);
    window.parent.postMessage({ type: "REQUEST_THEME" }, "*");
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  useEffect(() => {
    // Check local storage for token
    const storedToken = localStorage.getItem("prscope_token");
    const storedUser = localStorage.getItem("prscope_user");
    if (storedToken) {
      setToken(storedToken);
      if (storedUser) setUser(JSON.parse(storedUser));
    }

    if (owner && repo && pr) {
      fetchAnalysis(owner, repo, pr);
    }
  }, [owner, repo, pr]);

  useEffect(() => {
    if (activeTab === "SAVED_REVIEWS" && token) {
      fetchSavedReviews();
    }
  }, [activeTab, token, filterStatus, sortOrder, searchQuery]);

  const loginWithGitHub = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/analysis/auth/github/callback?code=mock");
      const data = await res.json();
      if (data.access_token) {
        setToken(data.access_token);
        setUser(data.user);
        localStorage.setItem("prscope_token", data.access_token);
        localStorage.setItem("prscope_user", JSON.stringify(data.user));
      }
    } catch (err) {
      console.error(err);
    }
  };

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
          gemini_api_key: localStorage.getItem("prscope_gemini_key") || undefined,
        }),
      });

      if (!response.ok) throw new Error("Failed to fetch analysis");
      const result = await response.json();
      setData(result);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const saveReviewWorkspace = async () => {
    if (!token) {
      alert("Please login via GitHub to save reviews.");
      return;
    }
    setNoteSaving(true);
    try {
      const response = await fetch("http://localhost:8000/api/analysis/workspace/reviews", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          repository: `${owner}/${repo}`,
          repository_owner: owner,
          repository_name: repo,
          pr_number: parseInt(pr as string, 10),
          pr_title: "PR Title", // Usually fetched from GitHub API in extension
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

  const fetchSavedReviews = async () => {
    try {
      const q = new URLSearchParams({
        status: filterStatus,
        sort: sortOrder,
        search: searchQuery
      });
      const response = await fetch(`http://localhost:8000/api/analysis/workspace/reviews?${q.toString()}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (response.ok) {
        const result = await response.json();
        setSavedReviews(result);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchReviewDetails = async (id: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/analysis/workspace/reviews/${id}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const eventsRes = await fetch(`http://localhost:8000/api/analysis/workspace/reviews/${id}/events`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      
      if (response.ok && eventsRes.ok) {
        setSelectedReview(await response.json());
        setReviewEvents(await eventsRes.json());
      }
    } catch (err) {
      console.error(err);
    }
  };

  const postCommentToGithub = async (comment: any, index: number) => {
    setPostingComment(index.toString());
    try {
      const response = await fetch("http://localhost:8000/api/analysis/post-comment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: `https://github.com/${owner}/${repo}`,
          pr_number: parseInt(pr as string, 10),
          comment_body: `**PRScope Suggestion (${comment.file})**\n\n**Issue**: ${comment.issue}\n**Reasoning**: ${comment.reasoning}\n\n**Suggestion**: ${comment.suggestion}`
        }),
      });
      if (response.ok) {
        alert("Comment posted to GitHub!");
      } else {
        alert("Failed to post comment.");
      }
    } catch (err) {
      alert("Error posting comment.");
    } finally {
      setPostingComment(null);
    }
  };

  const copySnapshot = () => {
    if (!data) return;
    const securityTxt = data.security_findings?.length > 0 
      ? data.security_findings.map((f:any)=> `- ${f.severity}: ${f.name}`).join('\n') 
      : 'None';
      
    let total_up = 0;
    let total_down = 0;
    data.impact_analysis?.dependency_graph?.modified_functions?.forEach((f: any) => {
      total_up += f.called_by?.length || 0;
      total_down += f.calls?.length || 0;
    });
    const depImpact = (total_up + total_down > 10) ? 'High' : (total_up + total_down > 5) ? 'Medium' : 'Low';
    
    const ts = new Date().toLocaleString();
    
    const archTxt = data.architecture_violations?.length > 0 
      ? data.architecture_violations.map((f:any)=> `- ${f}`).join('\n') 
      : 'None';
      
    const jiraTxt = data.jira_context ? `Ticket: ${data.jira_context.Ticket}\nConfidence: ${data.jira_context.Confidence}\nCoverage: ${data.jira_context.Coverage}\nMissing Requirements: ${data.jira_context.Missing_Requirements}` : 'None';
    
    const prType = data.pr_type || 'Unknown';

    const md = `# PRScope Review Snapshot\n\n**Repository**: ${owner}/${repo}\n**PR Number**: #${pr}\n**PR URL**: https://github.com/${owner}/${repo}/pull/${pr}\n**Timestamp**: ${ts}\n\n**PR Type**: ${prType}\n**Risk Score**: ${data.risk_score.score}/10 (${data.risk_score.category})\n**Reviewability Score**: ${data.reviewability?.score ?? 'N/A'}/10\n**Review Decision**: ${getReviewDecision()?.status || 'N/A'}\n**Decision Reason**: ${getReviewDecision()?.reason || 'N/A'}\n\n**Status**: ${noteStatus}\n\n**Security Findings**:\n${securityTxt}\n\n**Architecture Violations**:\n${archTxt}\n\n**Dependency Impact**: ${depImpact} (${total_up} upstream / ${total_down} downstream)\n\n**Jira Context**:\n${jiraTxt}\n\n**Review Notes**:\n${noteText || 'None'}\n\n**Executive Summary**:\n${data.executive_summary}`;
    
    window.parent.postMessage({ type: "COPY_TO_CLIPBOARD", text: md }, "*");
    alert("Review Snapshot copied to clipboard!");
  };

  
  const getReviewDecision = () => {
    if (!data) return null;
    const { risk_score, security_findings, architecture_violations, pr_type } = data;
    const hasSec = security_findings && security_findings.length > 0;
    const hasArch = architecture_violations && architecture_violations.length > 0;
    const score = risk_score?.score || 0;
    const isCriticalSec = hasSec && security_findings.some((f: any) => f.severity === 'Critical');
    
    let hasTests = false;
    data.files?.forEach((f: any) => {
      if (f.filename?.toLowerCase().includes("test") || f.filename?.startsWith("tests/")) hasTests = true;
    });

    let total_up = 0; let total_down = 0;
    data.impact_analysis?.dependency_graph?.modified_functions?.forEach((f: any) => {
      total_up += f.called_by?.length || 0;
      total_down += f.calls?.length || 0;
    });
    const highDep = (total_up + total_down > 10);
    
    if (isCriticalSec || hasSec) {
      return { status: "REQUEST CHANGES", reason: "Security concerns detected. Approval is not recommended until issues are resolved.", color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
    }
    if (score >= 7) {
      return { status: "REQUEST CHANGES", reason: `High risk score (${score}/10). Significant codebase modifications require deep manual review.`, color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
    }
    if (hasArch) {
      return { status: "REQUEST CHANGES", reason: "Architecture violations detected. Resolving architectural constraints is required.", color: "text-[var(--color-danger-fg,#da3633)]", bg: "bg-[var(--color-danger-fg,#da3633)]" };
    }
    if (score >= 7 && !hasTests && pr_type !== "DOCS" && pr_type !== "TEST") {
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
  };

  const reviewDecision = getReviewDecision();

  if (!owner || !repo || !pr) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]" style={{ fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" }}>
        <div className="text-center p-6 border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))]">
          <ShieldAlert className="mx-auto h-12 w-12 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-4" />
          <h2 className="text-lg font-semibold">PRScope Active</h2>
          <p className="text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mt-2">Open a Pull Request on GitHub to see analysis.</p>
          {!token && (
            <button onClick={loginWithGitHub} className="mt-4 bg-[#1f7530] text-white px-4 py-2 rounded-md text-sm font-medium border border-[rgba(240,246,252,0.1)] hover:bg-[#1a6825] flex items-center gap-2 mx-auto">
              Login with GitHub
            </button>
          )}
        </div>
      </div>
    );
  }

  // Common GitHub Native Styles
  const boxStyle = "bg-transparent border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]";
  const headerStyle = "bg-transparent px-0 py-3 m-0";
  const buttonStyle = "bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] border border-[#363b42] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:bg-[#30363d] hover:border-[#8b949e] transition-colors rounded-md text-sm font-medium py-1.5 px-3";
  const primaryButtonStyle = "bg-[#1f7530] border border-[rgba(240,246,252,0.1)] text-white hover:bg-[#1a6825] transition-colors rounded-md text-sm font-medium py-1.5 px-3";
  const textPrimary = "text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]";
  const textSecondary = "text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]";
  const inputStyle = "bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md p-2 text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] outline-none focus:border-[#8b949e] focus:ring-1 focus:ring-[#8b949e]";
  const containerFont = { fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" };

  return (
    <div className="min-h-screen bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] p-4 overflow-y-auto" style={containerFont}>
      <div className="flex items-center gap-2 mb-4 pb-4 border-b border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
        <GitMerge className="h-5 w-5 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" />
        <div className="flex flex-col">
          <h1 className="text-md font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] leading-none">PRScope</h1>
          <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">GitHub PR Intelligence</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <button onClick={() => window.parent.postMessage({ type: "TOGGLE_COLLAPSE" }, "*")} className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] hover:text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] transition-colors" title="Collapse Panel">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m13 17 5-5-5-5M6 17l5-5-5-5"/></svg>
          </button>
          <button onClick={() => setShowSettings(!showSettings)} className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] hover:text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] transition-colors" title="Settings">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
          </button>
        </div>
        {!token && (
          <button onClick={loginWithGitHub} className={`${primaryButtonStyle} ml-auto py-1 px-2 text-xs`}>
            Login via GitHub
          </button>
        )}
        {token && user && (
          <div className="flex items-center gap-2 text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">
            <img src={user.avatar_url} className="w-5 h-5 rounded-full" />
            {user.username}
          </div>
        )}

      </div>

      
      {/* Settings Modal Inline */}
      {showSettings && (
        <div className="mb-4 p-3 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-sm">
          <label className="block text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-1">Gemini API Key (BYOK)</label>
          <div className="flex gap-2">
            <input 
              type="password" 
              value={apiKey} 
              onChange={(e) => setApiKey(e.target.value)} 
              placeholder="AIzaSy..." 
              className={inputStyle + " flex-1"} 
            />
            <button onClick={handleSaveApiKey} className={buttonStyle}>{keySavedMessage ? "Saved!" : "Save"}</button>
          </div>
          <p className="text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mt-1">Leave blank to use the free global tier (Rate limits apply).</p>
        </div>
      )}
      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        <button 
          onClick={() => setActiveTab("PR_REVIEW")}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md border transition-colors ${activeTab === "PR_REVIEW" ? "bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] border-[#8b949e]" : "bg-transparent text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] border-transparent hover:bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))]"}`}
        >
          PR Review
        </button>
        <button 
          onClick={() => setActiveTab("SAVED_REVIEWS")}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md border transition-colors ${activeTab === "SAVED_REVIEWS" ? "bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] border-[#8b949e]" : "bg-transparent text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] border-transparent hover:bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))]"}`}
        >
          Saved Reviews
        </button>
      </div>

      {activeTab === "PR_REVIEW" && (
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
              <button onClick={() => fetchAnalysis(owner, repo, pr)} className="ml-auto underline">Retry</button>
            </div>
          )}

          {data && !loading && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <button onClick={copySnapshot} className={`flex-1 flex items-center justify-center gap-2 ${buttonStyle} whitespace-nowrap`}>
                  <ClipboardCopy className="h-4 w-4" />
                  Copy Snapshot
                </button>
                {data.pr_type && (
                  <div className={`flex-1 flex items-center justify-center px-3 py-1.5 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-sm whitespace-nowrap`}>
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
                    className={`h-1.5 mb-4 bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] ${
                      data.risk_score.category === "High Risk" ? "[&>div]:bg-[var(--color-danger-bg,var(--color-danger-emphasis,#da3633))]" : 
                      data.risk_score.category === "Medium Risk" ? "[&>div]:bg-[#bf8700]" : 
                      "[&>div]:bg-[#1f7530]"
                    }`}
                  />
                  <div className="space-y-2 mt-4 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] p-3 rounded-md border border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                    <div className={`text-xs font-semibold ${textSecondary} mb-2 uppercase tracking-wide`}>Risk Breakdown</div>
                    {data.risk_score.factor_breakdown && data.risk_score.factor_breakdown.map((factor: any, i: number) => (
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
                      <span className={`text-2xl font-semibold leading-none ${data.reviewability.score >= 8 ? 'text-[var(--color-success-fg,#3fb950)]' : data.reviewability.score >= 4 ? 'text-[var(--color-attention-fg,#d29922)]' : 'text-[var(--color-danger-fg,#da3633)]'}`}>
                        {data.reviewability.score}
                      </span>
                      <span className={`text-sm ${textSecondary} leading-none mb-0.5`}>/ 10</span>
                      <span className={`text-sm font-semibold ml-2 ${data.reviewability.score >= 8 ? 'text-[var(--color-success-fg,#3fb950)]' : data.reviewability.score >= 4 ? 'text-[var(--color-attention-fg,#d29922)]' : 'text-[var(--color-danger-fg,#da3633)]'}`}>
                        {data.reviewability.score >= 8 ? 'High Reviewability' : data.reviewability.score >= 4 ? 'Medium Reviewability' : 'Low Reviewability'}
                      </span>
                    </div>
                    <Progress 
                      value={data.reviewability.score * 10} 
                      className={`h-1.5 mb-4 bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] ${
                        data.reviewability.score >= 8 ? "[&>div]:bg-[var(--color-success-fg,#3fb950)]" : 
                        data.reviewability.score >= 4 ? "[&>div]:bg-[var(--color-attention-fg,#d29922)]" : 
                        "[&>div]:bg-[var(--color-danger-fg,#da3633)]"
                      }`}
                    />
                    <div className="space-y-2 mt-4 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] p-3 rounded-md border border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                      <div className={`text-xs font-semibold ${textSecondary} mb-2 uppercase tracking-wide`}>Factors</div>
                      {data.reviewability.factor_breakdown && data.reviewability.factor_breakdown.map((factor: any, i: number) => (
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
              <Accordion type="multiple" className="w-full space-y-3" defaultValue={["executive_summary"]}>
                
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
                        {data.security_findings.map((finding: any, i: number) => (
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
                            {finding.ai_explanation && (
                              <div className="mt-3 p-3 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-xs space-y-2">
                                <div><span className="font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">AI Explanation:</span> {finding.ai_explanation}</div>
                                <div><span className="font-semibold text-[var(--color-success-fg,#3fb950)]">Recommendation:</span> {finding.ai_recommendation}</div>
                                <div><span className="font-semibold text-[var(--color-attention-fg,#d29922)]">Impact:</span> {finding.ai_impact_summary}</div>
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
                      {(() => {
                        let total_up = 0;
                        let total_down = 0;
                        data.impact_analysis?.dependency_graph?.modified_functions?.forEach((f: any) => {
                          total_up += f.called_by?.length || 0;
                          total_down += f.calls?.length || 0;
                        });
                        const depImpact = (total_up + total_down > 10) ? 'High' : (total_up + total_down > 5) ? 'Medium' : 'Low';
                        const impactColor = depImpact === 'High' ? 'text-[var(--color-danger-fg,#da3633)]' : depImpact === 'Medium' ? 'text-[var(--color-attention-fg,#d29922)]' : 'text-[var(--color-success-fg,#3fb950)]';
                        
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
                        Impacted Services: {data.impact_analysis?.affected_services?.join(", ") || "None"} <br/>
                        Impacted Modules: {data.impact_analysis?.affected_modules?.join(", ") || "None"}
                      </div>
                      
                      {data.impact_analysis?.dependency_graph?.modified_functions?.map((dep: any, i: number) => (
                        <div key={i} className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md p-3">
                          <div className="text-sm font-mono font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] break-all mb-2">{dep.function}</div>
                          
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <div className="text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase font-bold mb-1">Called By (Upstream)</div>
                              {dep.called_by?.length > 0 ? (
                                <ul className="text-xs text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] space-y-1">
                                  {dep.called_by.map((c: string, idx: number) => <li key={idx} className="flex gap-1 break-all"><LinkIcon className="h-3 w-3 mt-0.5 flex-shrink-0 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" /><span>{c}</span></li>)}
                                </ul>
                              ) : <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">None detected</span>}
                            </div>
                            <div>
                              <div className="text-[10px] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] uppercase font-bold mb-1">Calls (Downstream)</div>
                              {dep.calls?.length > 0 ? (
                                <ul className="text-xs text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] space-y-1">
                                  {dep.calls.map((c: string, idx: number) => <li key={idx} className="flex gap-1 break-all"><LinkIcon className="h-3 w-3 mt-0.5 flex-shrink-0 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" /><span>{c}</span></li>)}
                                </ul>
                              ) : <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">None detected</span>}
                            </div>
                          </div>
                        </div>
                      ))}
                      {(!data.impact_analysis?.dependency_graph?.modified_functions || data.impact_analysis?.dependency_graph?.modified_functions.length === 0) && (
                        <div className={`text-xs ${textSecondary}`}>No direct function dependencies extracted from patch.</div>
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
                            {data.changed_symbols.functions_modified.map((f:string, i:number) => (
                              <span key={i} className="text-[12px] bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] px-2 py-1 rounded-md text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] font-mono">{f}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {data.changed_symbols && data.changed_symbols.functions_added?.length > 0 && (
                        <div>
                          <div className={`text-xs font-semibold ${textSecondary} mb-2`}>Functions Added:</div>
                          <div className="flex flex-wrap gap-2">
                            {data.changed_symbols.functions_added.map((f:string, i:number) => (
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
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v4"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m3 15 2 2 4-4"/></svg>
                      Architecture Violations
                      {data.architecture_violations?.length > 0 && (
                        <Badge className="ml-2 bg-[var(--color-danger-bg,var(--color-danger-emphasis,#da3633))] text-white border-transparent text-[10px] py-0">{data.architecture_violations.length}</Badge>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                    <div className="space-y-4">
                      {data.architecture_violations?.map((viol: any, i: number) => (
                        <div key={i} className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[#da3633]/30 rounded-md p-3">
                          <div className="text-sm font-semibold text-[var(--color-danger-fg,#da3633)] mb-1">{viol.rule}</div>
                          <div className={`text-xs ${textSecondary}`}>{viol.description}</div>
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
                    <div className="text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] leading-relaxed max-w-none break-words">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h3: ({node, ...props}) => <h3 className="text-base font-bold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] mt-6 mb-2" {...props} />,
                          p: ({node, ...props}) => <p className="my-2 leading-6 whitespace-pre-wrap break-words" {...props} />,
                          ul: ({node, ...props}) => <ul className="list-disc pl-5 my-2 break-words" {...props} />,
                          li: ({node, ...props}) => <li className="my-1 break-words" {...props} />
                        }}
                      >
                        {data.executive_summary}
                      </ReactMarkdown>
                    </div>
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
                    <div className="space-y-3">
                      {data.review_checklist && data.review_checklist.map((item: string, i: number) => (
                        <div key={i} className="flex items-start gap-3 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] p-3 rounded-md shadow-sm break-words">
                          <CheckCircle className="h-4 w-4 mt-0.5 text-[var(--color-success-fg,#3fb950)] flex-shrink-0" />
                          <span className={`text-sm ${textPrimary} leading-snug whitespace-pre-wrap`}>{item}</span>
                        </div>
                      ))}
                    </div>
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
                    {data.suggested_comments && data.suggested_comments.length > 0 ? (
                      <div className="space-y-3">
                        {data.suggested_comments.map((comment: any, i: number) => (
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
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
                      Review Decision
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                    {reviewDecision && (
                      <div className="flex flex-col gap-2">
                        <div className={`flex items-center gap-2 ${reviewDecision.color} font-semibold text-lg`}>
                          <div className={`w-3 h-3 rounded-full ${reviewDecision.bg}`} />
                          {reviewDecision.status}
                        </div>
                        <div className="text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">
                          {reviewDecision.reason}
                        </div>
                      </div>
                    )}
                  </AccordionContent>
                </AccordionItem>


                {/* Jira Context */}
                <AccordionItem value="jira" className={boxStyle}>
                  <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                    <div className="flex items-center gap-2 text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                      Jira Context
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="p-4 bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
                    <div className="space-y-4">
                      {data.jira_context ? (
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
                            <div className={`text-xs ${data.jira_context.Missing_Requirements !== 'None detected' ? 'text-[var(--color-attention-fg,#d29922)]' : 'text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]'}`}>
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
                      className={`w-full mb-3 ${inputStyle}`}
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
      )}

      {activeTab === "SAVED_REVIEWS" && (
        <div className="space-y-4">
          {!token ? (
            <div className="text-center p-8 border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))]">
              <LockIcon className="mx-auto h-8 w-8 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-3" />
              <p className="text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-4">Please login to view your personal Saved Reviews workspace.</p>
              <button onClick={loginWithGitHub} className={`${primaryButtonStyle}`}>Login via GitHub</button>
            </div>
          ) : selectedReview ? (
            // Detail View
            <div className="space-y-4 animate-in fade-in zoom-in-95 duration-200">
              <button onClick={() => setSelectedReview(null)} className={`text-xs flex items-center gap-1 ${textSecondary} hover:text-white transition-colors`}>
                ← Back to List
              </button>
              
              <div className={boxStyle}>
                <div className={`${headerStyle} flex justify-between items-center`}>
                  <div className="font-semibold">{selectedReview.repository} #{selectedReview.pr_number}</div>
                  <Badge variant="outline" className="border-[var(--borderColor-default,var(--color-border-default,#30363d))]">{selectedReview.review_status}</Badge>
                </div>
                <div className="p-4 space-y-4 text-sm bg-[var(--bgColor-default,var(--color-canvas-default,#010409))]">
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] block mb-1">Risk Score</span>
                      <span className={`font-semibold ${selectedReview.risk_category === "High Risk" ? "text-[#f85149]" : "text-[var(--color-success-fg,#3fb950)]"}`}>{selectedReview.risk_score} - {selectedReview.risk_category}</span>
                    </div>
                    <div>
                      <span className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] block mb-1">Last Reviewed</span>
                      <span>{new Date(selectedReview.last_reviewed_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] text-xs font-semibold uppercase block mb-2">Review Notes</span>
                    <div className="bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] p-3 rounded-md min-h-[60px] whitespace-pre-wrap">
                      {selectedReview.review_notes || "No notes provided."}
                    </div>
                  </div>

                  <div>
                    <span className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] text-xs font-semibold uppercase block mb-2">Timeline</span>
                    <div className="border-l-2 border-[var(--borderColor-default,var(--color-border-default,#30363d))] ml-2 pl-4 space-y-4 py-2">
                      {reviewEvents.map((evt, i) => (
                        <div key={i} className="relative">
                          <div className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-[#8b949e]"></div>
                          <div className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-0.5">{new Date(evt.timestamp).toLocaleString()}</div>
                          <div className="text-sm">{evt.event_type}: {evt.description}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <a href={selectedReview.pr_url} target="_blank" rel="noreferrer" className={`block text-center w-full ${primaryButtonStyle} py-2 mt-4`}>
                    Open Original GitHub PR
                  </a>
                </div>
              </div>
            </div>
          ) : (
            // List View
            <>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2 h-4 w-4 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" />
                  <input 
                    placeholder="Search repo, title, PR..." 
                    className={`${inputStyle} w-full pl-9 h-9`}
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <select 
                  className={`${inputStyle} flex-1 h-9 appearance-none bg-no-repeat pr-8`} 
                  style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238b949e' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`, backgroundPosition: "calc(100% - 12px) center" }}
                  value={filterStatus} 
                  onChange={e => setFilterStatus(e.target.value)}
                >
                  <option value="All">All Statuses</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="APPROVED">Approved</option>
                  <option value="NEEDS_CHANGES">Needs Changes</option>
                  <option value="FOLLOW_UP_REQUIRED">Follow Up Required</option>
                </select>
                <select 
                  className={`${inputStyle} flex-1 h-9 appearance-none bg-no-repeat pr-8`} 
                  style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238b949e' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`, backgroundPosition: "calc(100% - 12px) center" }}
                  value={sortOrder} 
                  onChange={e => setSortOrder(e.target.value)}
                >
                  <option value="newest">Most Recent</option>
                  <option value="oldest">Oldest</option>
                  <option value="highest_risk">Highest Risk</option>
                  <option value="lowest_risk">Lowest Risk</option>
                </select>
              </div>

              <div className="space-y-3 mt-4">
                {savedReviews.map(r => (
                  <div key={r.id} onClick={() => fetchReviewDetails(r.id)} className={`${boxStyle} cursor-pointer hover:border-[#8b949e] transition-colors p-3 flex flex-col gap-2`}>
                    <div className="flex justify-between items-start">
                      <div className="font-semibold text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:underline">
                        {r.repository} <span className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] font-normal">#{r.pr_number}</span>
                      </div>
                      <Badge variant="outline" className={`text-[10px] ${r.review_status === 'APPROVED' ? 'border-[#3fb950] text-[var(--color-success-fg,#3fb950)]' : 'border-[var(--borderColor-default,var(--color-border-default,#30363d))] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]'}`}>
                        {r.review_status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">
                      <span className={`font-semibold ${r.risk_category === "High Risk" ? "text-[#f85149]" : "text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]"}`}>
                        Risk: {r.risk_score}
                      </span>
                      <span>Reviewed: {new Date(r.last_reviewed_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
                {savedReviews.length === 0 && (
                  <div className="text-center py-8 text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">No saved reviews found.</div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function LockIcon(props: any) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
    </svg>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] text-sm font-sans">Loading Workspace...</div>}>
      <MainDashboard />
    </Suspense>
  );
}
