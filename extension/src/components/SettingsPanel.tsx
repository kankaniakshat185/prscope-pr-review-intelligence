import { useEffect, useState } from "react";
import { CheckCircle } from "lucide-react";
import { textSecondary, selectChevronStyle } from "@/lib/styles";

export function SettingsPanel({
  visible,
  customRulesYaml,
  onFileUpload,
}: {
  visible: boolean;
  customRulesYaml: string | null;
  onFileUpload: (event: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  const [apiKey, setApiKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [aiProvider, setAiProvider] = useState("gemini");
  const [keySavedMessage, setKeySavedMessage] = useState(false);

  // This app is a Next.js static export (next.config.ts: output: "export")
  // rendered into a fixed index.html with no per-request server, so
  // localStorage is never available while that HTML is generated - it can
  // only be read once the client has mounted. Reading it via a lazy
  // useState initializer instead of this effect would run during Next's
  // build-time prerender (throwing, since `localStorage` doesn't exist in
  // Node) and would also produce a first-client-render value that doesn't
  // match the statically-generated markup, triggering a hydration
  // mismatch. The effect intentionally defers the read to after mount.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setApiKey(localStorage.getItem("prscope_gemini_key") || "");
    setOpenaiKey(localStorage.getItem("prscope_openai_key") || "");
    setGithubToken(localStorage.getItem("prscope_github_token") || "");
    setAiProvider(localStorage.getItem("prscope_ai_provider") || "gemini");
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSaveApiKey = () => {
    localStorage.setItem("prscope_gemini_key", apiKey);
    localStorage.setItem("prscope_openai_key", openaiKey);
    localStorage.setItem("prscope_github_token", githubToken);
    localStorage.setItem("prscope_ai_provider", aiProvider);
    setKeySavedMessage(true);
    setTimeout(() => setKeySavedMessage(false), 2000);
  };

  if (!visible) return null;

  return (
    <div className="mb-4 flex flex-col gap-3">
      <p className={`text-[11px] ${textSecondary} px-1 -mb-1`}>
        Keys below are stored locally in this browser (not encrypted, not sent anywhere except with your own analysis requests). Anyone with access to this device and browser profile could read them from local storage. Use a fine-grained, minimally-scoped GitHub token if possible.
      </p>
      <div className="p-3 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-sm shadow-sm transition-all hover:shadow-md">
        <label className="block text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-2">
          AI Provider
        </label>
        <select
          value={aiProvider}
          onChange={(e) => setAiProvider(e.target.value)}
          className="bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md px-2 py-1 w-full text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] mb-3 outline-none focus:border-[#8b949e] appearance-none bg-no-repeat pr-8"
          style={selectChevronStyle}
        >
          <option value="gemini">Google Gemini</option>
          <option value="openai">OpenAI</option>
        </select>

        {aiProvider === "gemini" ? (
          <>
            <label className="block text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-2">
              Gemini API Key (BYOK)
              <span className="font-normal text-[10px] ml-2 opacity-70">(Leave blank for free global tier)</span>
            </label>
            <div className="flex gap-2 items-center">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="AIzaSy..."
                className="bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md px-2 py-1 flex-1 text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] outline-none focus:border-[#8b949e] focus:ring-1 focus:ring-[#8b949e]"
              />
              <button onClick={handleSaveApiKey} className="bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] border border-[#363b42] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:bg-[#30363d] hover:border-[#8b949e] transition-colors rounded-md text-sm font-medium py-1 px-3">
                {keySavedMessage ? "Saved!" : "Save"}
              </button>
            </div>
          </>
        ) : (
          <>
            <label className="block text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-2">
              OpenAI API Key
            </label>
            <div className="flex gap-2 items-center">
              <input
                type="password"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                placeholder="sk-..."
                className="bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md px-2 py-1 flex-1 text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] outline-none focus:border-[#8b949e] focus:ring-1 focus:ring-[#8b949e]"
              />
              <button onClick={handleSaveApiKey} className="bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] border border-[#363b42] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:bg-[#30363d] hover:border-[#8b949e] transition-colors rounded-md text-sm font-medium py-1 px-3">
                {keySavedMessage ? "Saved!" : "Save"}
              </button>
            </div>
          </>
        )}
      </div>

      <div className="p-3 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-sm shadow-sm transition-all hover:shadow-md">
        <label className="block text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-2">
          GitHub Access Token
          <span className="font-normal text-[10px] ml-2 opacity-70">(Required to post comments)</span>
        </label>
        <div className="flex gap-2 items-center">
          <input
            type="password"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
            placeholder="ghp_..."
            className="bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md px-2 py-1 flex-1 text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] outline-none focus:border-[#8b949e] focus:ring-1 focus:ring-[#8b949e]"
          />
          <button onClick={handleSaveApiKey} className="bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] border border-[#363b42] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:bg-[#30363d] hover:border-[#8b949e] transition-colors rounded-md text-sm font-medium py-1 px-3">
            {keySavedMessage ? "Saved!" : "Save"}
          </button>
        </div>
      </div>

      <div className="p-3 bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md text-sm shadow-sm transition-all hover:shadow-md">
        <label className="block text-xs font-semibold text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-2">Custom Architecture Rules (.yml)</label>
        <div className="flex gap-2 items-center">
          <input
            type="file"
            accept=".yml,.yaml"
            onChange={onFileUpload}
            className="text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] file:mr-2 file:py-1 file:px-2 file:rounded file:border border-[var(--borderColor-default,var(--color-border-default,#30363d))] file:text-xs file:font-semibold file:bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] file:text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:file:bg-[#30363d] cursor-pointer"
          />
          {customRulesYaml && <CheckCircle className="h-4 w-4 text-[var(--color-success-fg,#3fb950)]" />}
        </div>
      </div>
    </div>
  );
}
