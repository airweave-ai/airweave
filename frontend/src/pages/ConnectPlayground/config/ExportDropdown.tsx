import { useState } from "react";
import { FileDown, Check } from "lucide-react";
import { posthog } from "@/lib/posthog-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
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

function buildLlmsTxt(config: PlaygroundConfig): string {
  return `# Airweave Connect
> Embeddable widget for connecting data sources to Airweave.

## Quick Start
${generatePythonServer(config)}

## React Integration
${generateReactClient(config)}

## API Reference
- POST /connect/sessions — create a session token (server-side, API key auth)
- Session tokens are scoped to a single collection, expire in 10 minutes
- Modes: all, connect, manage, reauth
- Docs: https://docs.airweave.ai/connect
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
  { id: "markdown", label: "Markdown", build: buildMarkdown },
  { id: "llms", label: "llms.txt", build: buildLlmsTxt },
  { id: "cursor", label: "Cursor Rules", build: buildCursorRules },
  { id: "claude", label: "Claude", build: buildMarkdown },
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
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors">
          <FileDown className="h-3.5 w-3.5" />
          Copy as...
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        {FORMATS.map((fmt) => (
          <DropdownMenuItem
            key={fmt.id}
            onClick={() => handleCopy(fmt.id, fmt.build)}
            className="text-xs gap-2"
          >
            {copied === fmt.id ? (
              <Check className="h-3 w-3 text-emerald-500" />
            ) : (
              <div className="w-3" />
            )}
            {fmt.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
