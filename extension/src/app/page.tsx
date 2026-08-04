"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { GitMerge } from "lucide-react";
import { AuthBar, LoginPrompt } from "@/components/AuthBar";
import { SettingsPanel } from "@/components/SettingsPanel";
import { PrReviewPanel } from "@/components/PrReviewPanel";
import { SavedReviewsPanel } from "@/components/SavedReviewsPanel";
import { useAnalysis } from "@/lib/useAnalysis";
import type { AuthUser } from "@/lib/types";
import { containerFont } from "@/lib/styles";

// IN PRODUCTION: Change this to your deployed API URL via environment variables
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://prscope.onrender.com";

function MainDashboard() {
  const searchParams = useSearchParams();
  const owner = searchParams.get("owner");
  const repo = searchParams.get("repo");
  const pr = searchParams.get("pr");

  const [showSettings, setShowSettings] = useState(false);
  const [customRulesYaml, setCustomRulesYaml] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"PR_REVIEW" | "SAVED_REVIEWS">("PR_REVIEW");
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  const { data, loading, error, enriching, enrichError, fetchAnalysis, fetchEnrichment } = useAnalysis(API_BASE, token);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      setCustomRulesYaml(e.target?.result as string);
    };
    reader.readAsText(file);
  };

  // Theme sync with the GitHub page that embeds this iframe.
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Only accept messages from the parent GitHub page that embeds this
      // iframe (per manifest.json, that's the only page allowed to do so).
      if (event.source !== window.parent) return;
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
    window.parent.postMessage({ type: "REQUEST_THEME" }, "https://github.com");
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Same reasoning as SettingsPanel.tsx: this is a static export with no
  // per-request server (next.config.ts: output: "export"), so localStorage
  // can only be read safely after mount - reading it eagerly would both
  // crash Next's build-time prerender (no `localStorage` in Node) and
  // cause a hydration mismatch against the statically-generated markup.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    // Check local storage for token
    const storedToken = localStorage.getItem("prscope_token");
    const storedUser = localStorage.getItem("prscope_user");
    if (storedToken) {
      setToken(storedToken);
      if (storedUser) setUser(JSON.parse(storedUser));
    }
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    // Analysis requires a login (the backend requires a bearer token on /analyze).
    // Runs once the token from storage above is available, and again immediately
    // after a fresh login.
    if (owner && repo && pr && token) {
      fetchAnalysis(owner, repo, pr, customRulesYaml);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner, repo, pr, token]);

  const loginWithGitHub = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/analysis/auth/github/login`);
      const data = await res.json();

      if (data.url.includes("code=mock")) {
        const mockRes = await fetch(data.url);
        const mockData = await mockRes.json();
        setToken(mockData.access_token);
        setUser(mockData.user);
        localStorage.setItem("prscope_token", mockData.access_token);
        localStorage.setItem("prscope_user", JSON.stringify(mockData.user));
      } else {
        const popup = window.open(data.url, "github_oauth", "width=600,height=600");
        const messageListener = (event: MessageEvent) => {
          // Only accept the token from the popup window we just opened, not
          // from any other frame that might post a similarly-shaped message.
          if (event.source !== popup) return;
          if (event.data && event.data.access_token) {
            setToken(event.data.access_token);
            setUser(event.data.user);
            localStorage.setItem("prscope_token", event.data.access_token);
            localStorage.setItem("prscope_user", JSON.stringify(event.data.user));
            window.removeEventListener("message", messageListener);
          }
        };
        window.addEventListener("message", messageListener);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("prscope_token");
    localStorage.removeItem("prscope_user");
  };

  if (!owner || !repo || !pr) {
    return (
      <LoginPrompt
        title="PRScope Active"
        message="Open a Pull Request on GitHub to see analysis."
        onLogin={!token ? loginWithGitHub : undefined}
      />
    );
  }

  if (!token) {
    return (
      <LoginPrompt
        title="Login Required"
        message="Login with GitHub to analyze this pull request."
        onLogin={loginWithGitHub}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] p-4 overflow-y-auto" style={containerFont}>
      <div className="flex items-center gap-2 mb-4 pb-4 border-b border-[var(--borderColor-default,var(--color-border-default,#30363d))]">
        <GitMerge className="h-5 w-5 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" />
        <div className="flex flex-col">
          <h1 className="text-md font-semibold text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] leading-none">PRScope</h1>
          <span className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]">GitHub PR Intelligence</span>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <button onClick={() => window.parent.postMessage({ type: "TOGGLE_COLLAPSE" }, "https://github.com")} className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] hover:text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] transition-colors" title="Collapse Panel">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m13 17 5-5-5-5M6 17l5-5-5-5" /></svg>
          </button>
          <button onClick={() => setShowSettings(!showSettings)} className="text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] hover:text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] transition-colors" title="Settings">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" /></svg>
          </button>
        </div>
        <AuthBar token={token} user={user} onLogin={loginWithGitHub} onLogout={logout} />
      </div>

      <SettingsPanel visible={showSettings} customRulesYaml={customRulesYaml} onFileUpload={handleFileUpload} />

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setActiveTab("PR_REVIEW")}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md border transition-colors ${activeTab === "PR_REVIEW" ? "bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] border-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" : "bg-transparent text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] border-transparent hover:bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))]"}`}
        >
          PR Review
        </button>
        <button
          onClick={() => setActiveTab("SAVED_REVIEWS")}
          className={`flex-1 py-1.5 text-sm font-medium rounded-md border transition-colors ${activeTab === "SAVED_REVIEWS" ? "bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] border-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]" : "bg-transparent text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] border-transparent hover:bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))]"}`}
        >
          Saved Reviews
        </button>
      </div>

      {activeTab === "PR_REVIEW" && (
        <PrReviewPanel
          owner={owner}
          repo={repo}
          pr={pr}
          token={token}
          apiBase={API_BASE}
          data={data}
          loading={loading}
          error={error}
          enriching={enriching}
          enrichError={enrichError}
          onRetry={() => fetchAnalysis(owner, repo, pr, customRulesYaml)}
          onRetryEnrichment={() => fetchEnrichment(owner, repo, pr, customRulesYaml)}
        />
      )}

      {activeTab === "SAVED_REVIEWS" && (
        <SavedReviewsPanel token={token} apiBase={API_BASE} onLogin={loginWithGitHub} owner={owner} repo={repo} />
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-4 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] text-sm font-sans">Loading Workspace...</div>}>
      <MainDashboard />
    </Suspense>
  );
}
