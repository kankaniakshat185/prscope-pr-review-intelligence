"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";
import type { SavedReview, ReviewEvent } from "@/lib/types";
import { boxStyle, headerStyle, primaryButtonStyle, textSecondary, inputStyle, selectChevronStyle } from "@/lib/styles";

function LockIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export function SavedReviewsPanel({
  token,
  apiBase,
  onLogin,
}: {
  token: string | null;
  apiBase: string;
  onLogin: () => void;
}) {
  const [savedReviews, setSavedReviews] = useState<SavedReview[]>([]);
  const [filterStatus, setFilterStatus] = useState("All");
  const [sortOrder, setSortOrder] = useState("newest");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedReview, setSelectedReview] = useState<SavedReview | null>(null);
  const [reviewEvents, setReviewEvents] = useState<ReviewEvent[]>([]);

  useEffect(() => {
    if (!token) return;

    const fetchSavedReviews = async () => {
      try {
        const q = new URLSearchParams({
          status: filterStatus,
          sort: sortOrder,
          search: searchQuery
        });
        const response = await fetch(`${apiBase}/api/analysis/workspace/reviews?${q.toString()}`, {
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

    fetchSavedReviews();
  }, [token, apiBase, filterStatus, sortOrder, searchQuery]);

  const fetchReviewDetails = async (id: number) => {
    try {
      const response = await fetch(`${apiBase}/api/analysis/workspace/reviews/${id}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const eventsRes = await fetch(`${apiBase}/api/analysis/workspace/reviews/${id}/events`, {
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

  if (!token) {
    return (
      <div className="space-y-4">
        <div className="text-center p-8 border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))]">
          <LockIcon className="mx-auto h-8 w-8 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-3" />
          <p className="text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-4">Please login to view your personal Saved Reviews workspace.</p>
          <button onClick={onLogin} className={`${primaryButtonStyle}`}>Login via GitHub</button>
        </div>
      </div>
    );
  }

  if (selectedReview) {
    return (
      <div className="space-y-4">
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
                  <span>{selectedReview.last_reviewed_at ? new Date(selectedReview.last_reviewed_at).toLocaleDateString() : "N/A"}</span>
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
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
          style={selectChevronStyle}
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
          style={selectChevronStyle}
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
              <Badge variant="outline" className={`text-[10px] ${r.review_status === "APPROVED" ? "border-[#3fb950] text-[var(--color-success-fg,#3fb950)]" : "border-[var(--borderColor-default,var(--color-border-default,#30363d))] text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]"}`}>
                {r.review_status}
              </Badge>
            </div>
            <div className="flex items-center gap-4 text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">
              <span className={`font-semibold ${r.risk_category === "High Risk" ? "text-[#f85149]" : "text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]"}`}>
                Risk: {r.risk_score}
              </span>
              <span>Reviewed: {r.last_reviewed_at ? new Date(r.last_reviewed_at).toLocaleDateString() : "N/A"}</span>
            </div>
          </div>
        ))}
        {savedReviews.length === 0 && (
          <div className="text-center py-8 text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">No saved reviews found.</div>
        )}
      </div>
    </div>
  );
}
