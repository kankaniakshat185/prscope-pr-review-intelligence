"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { AlertCircle, CheckCircle, Search, GitPullRequest, GitMerge, ShieldAlert, Cpu, Activity, Layout, Code2, ClipboardCopy, History, Save, Send } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function MainDashboard() {
  const searchParams = useSearchParams();
  const owner = searchParams.get("owner");
  const repo = searchParams.get("repo");
  const pr = searchParams.get("pr");

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  
  const [noteStatus, setNoteStatus] = useState("IN_PROGRESS");
  const [noteText, setNoteText] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [postingComment, setPostingComment] = useState<string | null>(null);

  useEffect(() => {
    if (owner && repo && pr) {
      fetchAnalysis(owner, repo, pr);
      fetchNote(owner, repo, pr);
      fetchHistory(owner, repo);
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

      if (!response.ok) throw new Error("Failed to fetch analysis");
      const result = await response.json();
      setData(result);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const fetchNote = async (owner: string, repo: string, pr: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/analysis/note?repo_url=https://github.com/${owner}/${repo}&pr_number=${pr}`);
      if (response.ok) {
        const result = await response.json();
        setNoteStatus(result.status || "IN_PROGRESS");
        setNoteText(result.notes || "");
      }
    } catch (err) {
      // Ignored if not found
    }
  };

  const saveNote = async () => {
    setNoteSaving(true);
    try {
      await fetch("http://localhost:8000/api/analysis/note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: `https://github.com/${owner}/${repo}`,
          pr_number: parseInt(pr as string, 10),
          status: noteStatus,
          notes: noteText
        }),
      });
    } catch (err) {
      console.error(err);
    } finally {
      setNoteSaving(false);
    }
  };

  const fetchHistory = async (owner: string, repo: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/analysis/history?repo_url=https://github.com/${owner}/${repo}`);
      if (response.ok) {
        const result = await response.json();
        setHistory(result);
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
    const md = `# PRScope Review\n\n**Repository**: ${owner}/${repo}\n**PR**: #${pr}\n**Risk**: ${data.risk_score.score}/10 (${data.risk_score.category})\n\n**Functions Modified**:\n${data.changed_symbols?.functions_modified?.map((f:string)=>`- ${f}`).join('\n') || 'None'}\n\n**Review Notes**:\n${noteText || 'None'}\n\n**Summary**:\n${data.executive_summary}`;
    navigator.clipboard.writeText(md);
    alert("Review Snapshot copied to clipboard!");
  };

  if (!owner || !repo || !pr) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#0d1117] text-[#c9d1d9]" style={{ fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" }}>
        <div className="text-center p-6">
          <ShieldAlert className="mx-auto h-12 w-12 text-[#8b949e] mb-4" />
          <h2 className="text-lg font-semibold">PRScope Active</h2>
          <p className="text-sm text-[#8b949e] mt-2">Open a Pull Request on GitHub to see analysis.</p>
        </div>
      </div>
    );
  }

  // Common GitHub Native Styles
  const boxStyle = "bg-[#0d1117] border border-[#30363d] rounded-md overflow-hidden shadow-sm";
  const headerStyle = "bg-[#161b22] px-4 py-3 m-0";
  const buttonStyle = "bg-[#21262d] border border-[#363b42] text-[#c9d1d9] hover:bg-[#30363d] hover:border-[#8b949e] transition-colors rounded-md text-sm font-medium py-1.5 px-3";
  const primaryButtonStyle = "bg-[#1f7530] border border-[rgba(240,246,252,0.1)] text-white hover:bg-[#1a6825] transition-colors rounded-md text-sm font-medium py-1.5 px-3";
  const textPrimary = "text-[#c9d1d9]";
  const textSecondary = "text-[#8b949e]";
  const inputStyle = "bg-[#0d1117] border border-[#30363d] rounded-md p-2 text-sm text-[#c9d1d9] outline-none focus:border-[#58a6ff] focus:ring-1 focus:ring-[#58a6ff]";
  const containerFont = { fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" };

  return (
    <div className="min-h-screen bg-[#0d1117] text-[#c9d1d9] p-4 overflow-y-auto" style={containerFont}>
      <div className="flex items-center gap-2 mb-4 pb-4">
        <GitMerge className="h-5 w-5 text-[#8b949e]" />
        <h1 className="text-xl font-semibold tracking-tight text-[#c9d1d9]">PRScope</h1>
        <Badge variant="outline" className="ml-auto bg-[#161b22] border-[#30363d] text-[#8b949e] text-xs font-normal">
          {owner}/{repo} #{pr}
        </Badge>
      </div>

      {loading && (
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#58a6ff]"></div>
          <p className={`text-sm ${textSecondary} animate-pulse`}>Analyzing Pull Request...</p>
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
          <button onClick={copySnapshot} className={`w-full flex items-center justify-center gap-2 ${buttonStyle} py-2 mb-2`}>
            <ClipboardCopy className="h-4 w-4" />
            Copy Review Snapshot
          </button>

          {/* Risk Assessment (Not an accordion, keeping as a top-level summary box) */}
          <div className={boxStyle}>
            <div className={`${headerStyle} flex items-center justify-between`}>
              <h3 className={`text-sm font-semibold flex items-center gap-2 ${textPrimary} m-0`}>
                <Activity className="h-4 w-4" />
                Risk Assessment
              </h3>
              <Badge 
                variant="outline" 
                className={
                  data.risk_score.category === "High Risk" ? "text-[#f85149] border-[#f85149] bg-transparent" : 
                  data.risk_score.category === "Medium Risk" ? "text-[#d29922] border-[#d29922] bg-transparent" : 
                  "text-[#3fb950] border-[#3fb950] bg-transparent"
                }
              >
                {data.risk_score.category}
              </Badge>
            </div>
            <div className="p-4 bg-[#0d1117]">
              <div className="flex items-end gap-2 mb-3">
                <span className="text-2xl font-semibold text-[#c9d1d9] leading-none">{data.risk_score.score}</span>
                <span className={`text-sm ${textSecondary} leading-none mb-0.5`}>/ 10</span>
              </div>
              <Progress 
                value={data.risk_score.score * 10} 
                className={`h-1.5 mb-4 bg-[#21262d] ${
                  data.risk_score.category === "High Risk" ? "[&>div]:bg-[#da3633]" : 
                  data.risk_score.category === "Medium Risk" ? "[&>div]:bg-[#bf8700]" : 
                  "[&>div]:bg-[#1f7530]"
                }`}
              />
              <div className="space-y-2 mt-4 bg-[#161b22] p-3 rounded-md border border-[#30363d]">
                <div className={`text-xs font-semibold ${textSecondary} mb-2 uppercase tracking-wide`}>Risk Breakdown</div>
                {data.risk_score.factor_breakdown && data.risk_score.factor_breakdown.map((factor: any, i: number) => (
                  <div key={i} className="text-xs mb-2 last:mb-0">
                    <div className="flex justify-between font-medium text-[#c9d1d9]">
                      <span>{factor.name}</span>
                      <span className="text-[#d29922]">+{factor.weight}</span>
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

          {/* ALL OTHER SECTIONS AS COLLAPSIBLE ACCORDIONS */}
          <Accordion type="single" collapsible className="w-full space-y-3" defaultValue="executive_summary">
            
            {/* Executive Summary */}
            <AccordionItem value="executive_summary" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <Layout className="h-4 w-4" />
                  Executive Summary
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                <div className="text-sm text-[#c9d1d9] leading-relaxed prose prose-invert prose-sm max-w-none 
                                prose-h3:text-[16px] prose-h3:font-semibold prose-h3:mt-5 prose-h3:mb-2 prose-h3:text-[#c9d1d9] 
                                prose-p:my-2 prose-p:leading-6 prose-ul:my-2 prose-li:my-0.5">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {data.executive_summary}
                  </ReactMarkdown>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Review Notes Workspace */}
            <AccordionItem value="review_notes" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <Save className="h-4 w-4" />
                  Review Notes
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
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
                  placeholder="Add review notes here..."
                  className={`w-full h-24 mb-3 resize-y ${inputStyle}`}
                  style={{ fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" }}
                />
                <button 
                  onClick={saveNote}
                  disabled={noteSaving}
                  className={`w-full ${primaryButtonStyle} py-2`}
                >
                  {noteSaving ? "Saving..." : "Save Notes"}
                </button>
              </AccordionContent>
            </AccordionItem>

            {/* Changed Symbols Analysis */}
            <AccordionItem value="symbols" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <Code2 className="h-4 w-4" />
                  Changed Symbols
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                <div className="space-y-4">
                  {data.changed_symbols && data.changed_symbols.functions_modified.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold ${textSecondary} mb-2`}>Functions Modified:</div>
                      <div className="flex flex-wrap gap-2">
                        {data.changed_symbols.functions_modified.map((f:string, i:number) => (
                          <span key={i} className="text-[12px] bg-[#161b22] border border-[#30363d] px-2 py-1 rounded-md text-[#c9d1d9] font-mono">{f}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {data.changed_symbols && data.changed_symbols.functions_added.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold ${textSecondary} mb-2`}>Functions Added:</div>
                      <div className="flex flex-wrap gap-2">
                        {data.changed_symbols.functions_added.map((f:string, i:number) => (
                          <span key={i} className="text-[12px] bg-[#1f7530]/10 border border-[#1f7530]/30 px-2 py-1 rounded-md text-[#3fb950] font-mono">{f}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {data.changed_symbols && data.changed_symbols.classes_modified.length > 0 && (
                    <div>
                      <div className={`text-xs font-semibold ${textSecondary} mb-2`}>Classes Modified:</div>
                      <div className="flex flex-wrap gap-2">
                        {data.changed_symbols.classes_modified.map((f:string, i:number) => (
                          <span key={i} className="text-[12px] bg-[#58a6ff]/10 border border-[#58a6ff]/30 px-2 py-1 rounded-md text-[#58a6ff] font-mono">{f}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {(!data.changed_symbols || (data.changed_symbols.functions_modified.length === 0 && data.changed_symbols.functions_added.length === 0 && data.changed_symbols.classes_modified.length === 0)) && (
                    <div className={`text-xs ${textSecondary}`}>No significant symbols detected.</div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
            
            {/* Review Checklist */}
            <AccordionItem value="checklist" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <CheckCircle className="h-4 w-4" />
                  Review Checklist
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                <ul className={`space-y-2 text-sm ${textPrimary}`}>
                  {data.review_checklist && data.review_checklist.map((item: string, i: number) => (
                    <li key={i} className="flex items-start gap-2">
                      <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#58a6ff] flex-shrink-0" />
                      <span className="leading-snug">{item}</span>
                    </li>
                  ))}
                  {(!data.review_checklist || data.review_checklist.length === 0) && (
                    <div className={`text-xs ${textSecondary}`}>No specific checklist items needed.</div>
                  )}
                </ul>
              </AccordionContent>
            </AccordionItem>

            {/* Suggested Comments */}
            <AccordionItem value="comments" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <GitPullRequest className="h-4 w-4" />
                  Suggested Comments
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                {data.suggested_comments && data.suggested_comments.length > 0 ? (
                  <div className="space-y-3">
                    {data.suggested_comments.map((comment: any, i: number) => (
                      <div key={i} className="bg-[#161b22] rounded-md border border-[#30363d] p-3">
                        <div className="flex justify-between items-start mb-2">
                          <div className={`text-xs font-mono text-[#8b949e] truncate max-w-[70%]`} title={comment.file}>
                            {comment.file}
                          </div>
                          <Badge variant="outline" className="text-[10px] border-[#30363d] text-[#8b949e]">
                            {comment.confidence}% Confidence
                          </Badge>
                        </div>
                        <div className={`text-sm font-semibold ${textPrimary} mb-1 leading-snug`}>
                          {comment.issue}
                        </div>
                        <div className={`text-xs ${textSecondary} mb-3 leading-relaxed`}>
                          {comment.reasoning}
                        </div>
                        <div className="text-xs text-[#3fb950] bg-[#1f7530]/10 p-2.5 rounded-md mb-3 border border-[#1f7530]/20">
                          <span className="font-semibold block mb-1">Suggestion:</span>
                          <span className="leading-relaxed">{comment.suggestion}</span>
                        </div>
                        <div className="flex gap-2">
                          <button className={`flex-1 ${buttonStyle}`}>Copy</button>
                          <button 
                            onClick={() => postCommentToGithub(comment, i)}
                            disabled={postingComment === i.toString()}
                            className={`flex-1 flex items-center justify-center gap-1 ${primaryButtonStyle}`}
                          >
                            <Send className="h-3 w-3" />
                            {postingComment === i.toString() ? "Posting..." : "Post to GitHub"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={`text-xs ${textSecondary}`}>No high-confidence concerns found.</div>
                )}
              </AccordionContent>
            </AccordionItem>
            
            {/* Similar Incidents */}
            {data.similar_incidents && data.similar_incidents.length > 0 && (
              <AccordionItem value="incidents" className={boxStyle}>
                <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                  <div className="flex items-center gap-2 text-[#c9d1d9]">
                    <Search className="h-4 w-4" />
                    Similar Incidents
                  </div>
                </AccordionTrigger>
                <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                  <div className="space-y-3">
                    {data.similar_incidents.map((inc: any, i: number) => (
                      <div key={i} className="border border-[#30363d] rounded-md p-3 text-xs bg-[#161b22]">
                        <div className="flex items-center justify-between mb-2">
                          <Badge variant="outline" className="border-[#30363d] text-[#58a6ff]">
                            {inc.similarity_score}% Match
                          </Badge>
                        </div>
                        <div className={`text-[#c9d1d9] mb-1.5 font-medium leading-snug`}>{inc.matching_incident}</div>
                        <div className={`${textSecondary} leading-relaxed`}>{inc.explanation}</div>
                      </div>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>
            )}

            {/* Impact Graph */}
            <AccordionItem value="impact" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <Cpu className="h-4 w-4" />
                  Impact Graph
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                <div className="h-48 bg-[#0d1117] rounded-md overflow-hidden relative border border-[#30363d]">
                  <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center">
                    <p className={`text-xs ${textSecondary} mb-2`}>Impacted Services: {data.impact_analysis?.affected_services?.join(", ") || "None"}</p>
                    <p className={`text-xs ${textSecondary}`}>Impacted Modules: {data.impact_analysis?.affected_modules?.join(", ") || "None"}</p>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>

            {/* Analysis History */}
            <AccordionItem value="history" className={boxStyle}>
              <AccordionTrigger className={`text-sm font-semibold hover:no-underline px-4 py-3 ${headerStyle}`}>
                <div className="flex items-center gap-2 text-[#c9d1d9]">
                  <History className="h-4 w-4" />
                  Previous Analyses
                </div>
              </AccordionTrigger>
              <AccordionContent className="p-4 bg-[#0d1117] border-t border-[#30363d]">
                <div className="space-y-3">
                  {history.map((h, i) => (
                    <div key={i} className="text-xs border-l-2 border-[#30363d] pl-3 py-1">
                      <div className="flex justify-between text-[#8b949e] mb-1.5">
                        <span>PR #{h.pr_number}</span>
                        <span>{new Date(h.created_at).toLocaleDateString()}</span>
                      </div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-[#c9d1d9]">Risk: {h.risk_score}</span>
                        <span className="text-[#8b949e]">({h.risk_category})</span>
                      </div>
                      <div className={`text-[#8b949e] truncate`}>{h.executive_summary}</div>
                    </div>
                  ))}
                  {history.length === 0 && (
                    <div className={`text-xs ${textSecondary}`}>No previous analyses found.</div>
                  )}
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
    <Suspense fallback={<div className="p-4 text-[#8b949e] text-sm font-sans">Loading...</div>}>
      <MainDashboard />
    </Suspense>
  );
}
