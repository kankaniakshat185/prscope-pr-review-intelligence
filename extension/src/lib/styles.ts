// Shared GitHub-native style tokens used across the extension's panels.
// Pulled out of the single-file page.tsx so every component references the
// same values instead of re-declaring them.

export const boxStyle = "bg-transparent border-t border-[var(--borderColor-default,var(--color-border-default,#30363d))]";
export const headerStyle = "bg-transparent px-0 py-3 m-0";
export const buttonStyle = "bg-[var(--bgColor-neutral-muted,var(--color-neutral-muted,#21262d))] border border-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))] text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] hover:opacity-80 transition-opacity rounded-md text-sm font-medium py-1.5 px-3";
export const primaryButtonStyle = "bg-[#1f7530] border border-[rgba(240,246,252,0.1)] text-white hover:bg-[#1a6825] transition-colors rounded-md text-sm font-medium py-1.5 px-3";
export const textPrimary = "text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))]";
export const textSecondary = "text-[var(--fgColor-muted,var(--color-fg-muted,#8b949e))]";
export const inputStyle = "bg-[var(--bgColor-default,var(--color-canvas-default,#010409))] border border-[var(--borderColor-default,var(--color-border-default,#30363d))] rounded-md p-2 text-sm text-[var(--fgColor-default,var(--color-fg-default,#c9d1d9))] outline-none focus:border-[#8b949e] focus:ring-1 focus:ring-[#8b949e]";
export const selectChevronStyle = { backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238b949e' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`, backgroundPosition: "calc(100% - 12px) center" };
export const containerFont = { fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" };
