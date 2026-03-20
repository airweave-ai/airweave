import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { posthog } from "@/lib/posthog-provider";
import { useTheme } from "@/lib/theme-provider";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

export interface Tab {
  id: string;
  label: string;
  code: string;
  language?: string;
}

interface SnippetFrameProps {
  label: string;
  tabs: Tab[];
  stepNumber?: number;
  description?: string;
}

function makeStyle(base: Record<string, unknown>) {
  return {
    ...base,
    'pre[class*="language-"]': {
      ...(base['pre[class*="language-"]'] as Record<string, unknown>),
      background: "transparent",
      margin: 0,
      padding: 0,
    },
    'code[class*="language-"]': {
      ...(base['code[class*="language-"]'] as Record<string, unknown>),
      background: "transparent",
    },
  };
}

const darkStyle = makeStyle(oneDark as Record<string, unknown>);
const lightStyle = makeStyle(oneLight as Record<string, unknown>);

export function SnippetFrame({ label, tabs, stepNumber, description }: SnippetFrameProps) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.id ?? "");
  const [copied, setCopied] = useState(false);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  const active = tabs.find((t) => t.id === activeTab) ?? tabs[0];

  const handleCopy = () => {
    if (!active) return;
    navigator.clipboard.writeText(active.code);
    posthog.capture("connect_code_copied", {
      snippet_type: label.toLowerCase(),
      language: active.id,
    });
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const bg = isDark ? "bg-[#0d1117]" : "bg-background";
  const tabBarBg = isDark ? "bg-[#161b22]" : "bg-muted/60";
  const tabBarBorder = isDark ? "border-white/5" : "border-border/40";
  const labelColor = isDark ? "text-white/20" : "text-muted-foreground/40";
  const tabActive = isDark ? "bg-white/15 text-white/80" : "bg-muted text-foreground/70";
  const tabInactive = isDark ? "text-white/25 hover:text-white/45" : "text-muted-foreground/40 hover:text-muted-foreground/60";
  const copyColor = isDark ? "text-white/40 hover:text-white/70 hover:bg-white/10" : "text-muted-foreground/40 hover:text-foreground/60 hover:bg-muted";
  const descColor = isDark ? "text-white/30" : "text-muted-foreground/50";

  return (
    <div
      className={cn(
        "flex flex-col max-h-[480px] rounded-xl overflow-hidden",
        bg,
      )}
    >
      {/* Tab bar */}
      <div className={cn("flex items-center justify-between px-3 py-2 border-b shrink-0", tabBarBg, tabBarBorder)}>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {stepNumber !== undefined && (
              <span className="inline-flex items-center justify-center w-4.5 h-4.5 rounded text-[10px] font-bold bg-primary/20 text-primary">
                {stepNumber}
              </span>
            )}
            <span className={cn("text-[10px] font-medium uppercase tracking-wider", labelColor)}>
              {label}
            </span>
          </div>
          <div className="flex gap-0.5">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
                  activeTab === tab.id ? tabActive : tabInactive,
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={handleCopy}
          className={cn("transition-colors p-1.5 rounded-md shrink-0", copyColor)}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-400" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
      </div>

      {/* Description */}
      {description && (
        <div className="px-3 pt-2 pb-1 shrink-0">
          <p className={cn("text-[11px] leading-relaxed", descColor)}>{description}</p>
        </div>
      )}

      {/* Code */}
      <div className="flex-1 overflow-auto px-3 py-2">
        <SyntaxHighlighter
          language={active?.language ?? "javascript"}
          style={isDark ? darkStyle : lightStyle}
          customStyle={{
            fontSize: "0.625rem",
            lineHeight: "1.5",
            background: "transparent",
            margin: 0,
            padding: 0,
          }}
          codeTagProps={{
            style: {
              fontSize: "0.625rem",
              fontFamily:
                'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
            },
          }}
          wrapLongLines={false}
          showLineNumbers={false}
        >
          {active?.code ?? ""}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}
