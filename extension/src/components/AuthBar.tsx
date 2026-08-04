import { ShieldAlert } from "lucide-react";
import type { AuthUser } from "@/lib/types";

const primaryButtonStyle = "bg-[#1f7530] border border-[rgba(240,246,252,0.1)] text-white hover:bg-[#1a6825] transition-colors rounded-md text-sm font-medium py-1.5 px-3";

export function AuthBar({
  token,
  user,
  onLogin,
  onLogout,
}: {
  token: string | null;
  user: AuthUser | null;
  onLogin: () => void;
  onLogout: () => void;
}) {
  if (!token) {
    return (
      <button onClick={onLogin} className={`${primaryButtonStyle} ml-auto py-1 px-2 text-xs`}>
        Login via GitHub
      </button>
    );
  }

  if (!user) return null;

  return (
    <div className="relative group ml-auto">
      <div className="flex items-center gap-2 text-xs text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] cursor-pointer py-1">
        {/* eslint-disable-next-line @next/next/no-img-element -- external GitHub avatar URL, next/image would need remote-pattern config */}
        <img src={user.avatar_url} alt={user.username} className="w-5 h-5 rounded-full border border-[var(--borderColor-default,var(--color-border-default,#30363d))]" />
        <span className="font-medium text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]">{user.username}</span>
      </div>
      {/* Hover Dropdown */}
      <div className="absolute right-0 top-full mt-1 w-28 bg-[#da3633]/5 border border-[#da3633]/20 backdrop-blur-sm rounded-md shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
        <button
          onClick={onLogout}
          className="w-full text-center px-3 py-2 text-xs font-semibold text-[var(--color-danger-fg,#da3633)] hover:bg-[#da3633]/20 rounded-md transition-colors"
        >
          Logout
        </button>
      </div>
    </div>
  );
}

export function LoginPrompt({
  title,
  message,
  onLogin,
  fullScreen = true,
}: {
  title: string;
  message: string;
  onLogin?: () => void;
  fullScreen?: boolean;
}) {
  const card = (
    <div className="text-center p-6 border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md bg-[var(--bgColor-muted,var(--color-canvas-subtle,#161b22))]">
      <ShieldAlert className="mx-auto h-12 w-12 text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mb-4" />
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="text-sm text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] mt-2">{message}</p>
      {onLogin && (
        <button onClick={onLogin} className="mt-4 bg-[#1f7530] text-white px-4 py-2 rounded-md text-sm font-medium border border-[rgba(240,246,252,0.1)] hover:bg-[#1a6825] flex items-center gap-2 mx-auto">
          Login with GitHub
        </button>
      )}
    </div>
  );

  if (!fullScreen) return card;

  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]" style={{ fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" }}>
      {card}
    </div>
  );
}
