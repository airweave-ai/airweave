import { useState } from "react";
import { ClipboardCopy, Check, FileText, FileCode, BotMessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { posthog } from "@/lib/posthog-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { generatePythonServer, generateTypeScriptServer, generateReactClient, generateVanillaClient } from "../code/codeGen";
import type { PlaygroundConfig } from "../hooks/usePlaygroundState";

interface ExportDropdownProps {
  config: PlaygroundConfig;
}

function buildMarkdown(config: PlaygroundConfig): string {
  return `# Airweave Connect Integration

## Server-side (Python)

\`\`\`python
${generatePythonServer(config)}
\`\`\`

## Server-side (TypeScript)

\`\`\`typescript
${generateTypeScriptServer(config)}
\`\`\`

## Client-side (React)

\`\`\`tsx
${generateReactClient(config)}
\`\`\`

## Client-side (Vanilla JS)

\`\`\`javascript
${generateVanillaClient(config)}
\`\`\`
`;
}

function buildCursorRules(config: PlaygroundConfig): string {
  return `---
description: Airweave Connect integration guide
globs: "**/*.{ts,tsx,py}"
---

# Airweave Connect

Use the @airweave/connect-react SDK to embed the Connect widget.

## Server endpoint (creates session token)

\`\`\`python
${generatePythonServer(config)}
\`\`\`

## Client component

\`\`\`tsx
${generateReactClient(config)}
\`\`\`

## Key points
- Session tokens are created server-side with your API key
- Tokens expire in 10 minutes and are scoped to one collection
- The widget handles OAuth flows, connection management, and sync progress
- Modes: all (default), connect, manage, reauth
`;
}

const FORMATS = [
  { id: "markdown", label: "Markdown", description: "Formatted documentation", icon: FileText, build: buildMarkdown },
  { id: "cursor", label: "Cursor Rules", description: "Agent coding rules", icon: FileCode, build: buildCursorRules },
  { id: "claude", label: "Claude", description: "Markdown for Claude", icon: BotMessageSquare, build: buildMarkdown },
] as const;

export function ExportDropdown({ config }: ExportDropdownProps) {
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = (formatId: string, builder: (c: PlaygroundConfig) => string) => {
    navigator.clipboard.writeText(builder(config));
    posthog.capture("connect_export_copied", { format: formatId });
    setCopied(formatId);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1.5 h-8 px-3.5 rounded-full text-xs font-medium bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <ClipboardCopy className="h-3 w-3" />
          Export
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56 p-1.5">
        {FORMATS.map((fmt) => {
          const Icon = fmt.icon;
          const isCopied = copied === fmt.id;
          return (
            <button
              key={fmt.id}
              onClick={() => handleCopy(fmt.id, fmt.build)}
              className={cn(
                "w-full flex items-center gap-3 px-2.5 py-2 rounded-lg text-left transition-colors",
                isCopied
                  ? "bg-emerald-500/10"
                  : "hover:bg-muted/80",
              )}
            >
              <div
                className={cn(
                  "shrink-0 w-7 h-7 rounded-md flex items-center justify-center",
                  isCopied
                    ? "bg-emerald-500/15 text-emerald-500"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {isCopied ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
              </div>
              <div className="min-w-0">
                <div className={cn(
                  "text-xs font-medium",
                  isCopied ? "text-emerald-500" : "text-foreground",
                )}>
                  {isCopied ? "Copied!" : fmt.label}
                </div>
                <div className="text-[10px] text-muted-foreground/70 leading-tight">
                  {fmt.description}
                </div>
              </div>
            </button>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
