import { getAppIconUrl } from "@/lib/utils/icons";
import type { ThemeColors, ModalAppearance } from "../hooks/usePlaygroundState";

interface WidgetPreviewProps {
  colors: ThemeColors;
  modal: ModalAppearance;
}

const PREVIEW_SOURCES = [
  { shortName: "notion", name: "Notion" },
  { shortName: "gmail", name: "Gmail" },
  { shortName: "asana", name: "Asana" },
];

function isDarkBackground(hex: string): boolean {
  const c = hex.replace("#", "");
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 < 128;
}

export function WidgetPreview({ colors, modal }: WidgetPreviewProps) {
  const radius = `${modal.borderRadius}px`;
  const border = modal.borderWidth > 0
    ? `${modal.borderWidth}px solid ${modal.borderColor}`
    : "none";
  const iconTheme = isDarkBackground(colors.background) ? "dark" : "light";

  return (
    <div className="h-full flex items-center justify-center">
      <div
        className="w-full max-w-[220px] overflow-hidden"
        style={{
          background: colors.background,
          borderRadius: radius,
          border,
        }}
      >
        {/* Header */}
        <div className="px-4 pt-4 pb-3">
          <div
            className="text-[11px] font-semibold"
            style={{ color: colors.text }}
          >
            Connect a source
          </div>
          <div
            className="text-[9px] mt-0.5"
            style={{ color: colors.textMuted }}
          >
            Choose an app to connect
          </div>
        </div>

        {/* Search bar mock */}
        <div className="px-3 pb-2.5">
          <div
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[9px]"
            style={{
              background: colors.surface,
              color: colors.textMuted,
              border: `1px solid ${colors.border}`,
            }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            Search...
          </div>
        </div>

        {/* Source items */}
        <div className="px-3 pb-3 flex flex-col gap-1">
          {PREVIEW_SOURCES.map((source) => (
            <div
              key={source.shortName}
              className="flex items-center gap-2 px-2.5 py-2 rounded-md"
              style={{ background: colors.surface }}
            >
              <img
                src={getAppIconUrl(source.shortName, iconTheme)}
                alt=""
                className="w-[18px] h-[18px] rounded shrink-0"
              />
              <span className="text-[10px] font-medium" style={{ color: colors.text }}>
                {source.name}
              </span>
            </div>
          ))}
        </div>

        {/* Footer / button */}
        <div className="px-3 pb-3">
          <div
            className="w-full py-1.5 rounded-md text-center text-[9px] font-medium"
            style={{
              background: colors.primary,
              color: colors.background,
            }}
          >
            Continue
          </div>
        </div>
      </div>
    </div>
  );
}
