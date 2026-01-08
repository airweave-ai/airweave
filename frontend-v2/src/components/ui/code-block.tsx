import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  materialOceanic,
  oneLight,
} from "react-syntax-highlighter/dist/esm/styles/prism";
import { toast } from "sonner";

import { useIsDark } from "@/hooks/use-is-dark";
import { cn } from "@/lib/utils";

import { Badge } from "./badge";
import { Button } from "./button";

interface CodeBlockProps {
  /** The code to display */
  code: string;
  /** The programming language for syntax highlighting */
  language: string;
  /** Optional badge text shown in the header */
  badgeText?: string;
  /** Badge color class (e.g., "bg-blue-600") */
  badgeColor?: string;
  /** Optional title shown in the header */
  title?: string;
  /** Optional content shown in the footer */
  footerContent?: React.ReactNode;
  /** Disable copy functionality */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Inline styles */
  style?: React.CSSProperties;
  /** Fixed height for the code block */
  height?: string | number;
  /** Show line numbers */
  showLineNumbers?: boolean;
  /** Wrap long lines instead of horizontal scroll */
  wrapLongLines?: boolean;
}

export function CodeBlock({
  code,
  language,
  badgeText,
  badgeColor = "bg-blue-600 hover:bg-blue-600",
  title,
  footerContent,
  disabled = false,
  className,
  style,
  height,
  showLineNumbers = false,
  wrapLongLines = false,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const isDark = useIsDark();

  // Use theme-appropriate styling
  const baseStyle = isDark ? materialOceanic : oneLight;

  // Create a custom style that removes backgrounds but keeps text coloring
  const customStyle = {
    ...baseStyle,
    'pre[class*="language-"]': {
      ...baseStyle['pre[class*="language-"]'],
      background: "transparent",
      margin: 0,
      padding: 0,
    },
    'code[class*="language-"]': {
      ...baseStyle['code[class*="language-"]'],
      background: "transparent",
    },
  };

  const handleCopyCode = async () => {
    if (disabled) return;

    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);

      toast.success("Copied to clipboard");
    } catch {
      toast.error("Failed to copy");
    }
  };

  // Combine styles including height if provided
  const containerStyle: React.CSSProperties = {
    ...style,
    height: height || style?.height,
    display: "flex",
    flexDirection: "column",
  };

  return (
    <div
      className={cn(
        "overflow-hidden rounded-md border",
        isDark
          ? "border-gray-800 bg-black text-gray-100"
          : "border-gray-200 bg-white text-gray-900",
        className
      )}
      style={containerStyle}
    >
      {/* Header */}
      <div
        className={cn(
          "flex items-center justify-between border-b px-4 py-2",
          isDark ? "border-gray-800" : "border-gray-200"
        )}
      >
        <div className="flex items-center gap-2">
          {badgeText && (
            <Badge
              className={cn(
                "h-5 rounded px-1.5 py-0 text-xs text-white",
                badgeColor
              )}
            >
              {badgeText}
            </Badge>
          )}
          {title && (
            <span
              className={cn(
                "text-xs font-medium",
                isDark ? "text-gray-200" : "text-gray-700"
              )}
            >
              {title}
            </span>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          className={cn(
            "size-6 p-0",
            isDark
              ? "text-gray-400 hover:text-white"
              : "text-gray-500 hover:text-gray-900"
          )}
          onClick={handleCopyCode}
          disabled={disabled}
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
        </Button>
      </div>

      {/* Code content */}
      <div
        className={cn(
          "flex-1 overflow-auto px-4 py-3",
          isDark ? "bg-black" : "bg-white"
        )}
      >
        <SyntaxHighlighter
          language={language}
          style={customStyle}
          customStyle={{
            fontSize: "0.75rem",
            background: "transparent",
            margin: 0,
            padding: 0,
            height: "100%",
          }}
          wrapLongLines={wrapLongLines}
          showLineNumbers={showLineNumbers}
          codeTagProps={{
            style: {
              fontSize: "0.75rem",
              fontFamily: '"Fira Code", monospace',
            },
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>

      {/* Footer */}
      {footerContent && (
        <div
          className={cn(
            "border-t px-4 py-2",
            isDark
              ? "border-gray-800 text-white"
              : "border-gray-200 text-gray-700"
          )}
        >
          {footerContent}
        </div>
      )}
    </div>
  );
}
