import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";

interface CodeBlockProps {
  code: string;
  language: string;
  badgeText?: string;
  badgeColor?: string;
  title?: string;
  footerContent?: React.ReactNode;
  disabled?: boolean;
  className?: string;
  style?: React.CSSProperties;
  height?: string | number;
  /** Compact mode for embedding in panels — smaller padding and font */
  compact?: boolean;
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
  compact = false,
}: CodeBlockProps) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Use theme-appropriate styling
  const baseStyle = isDark ? materialOceanic : oneLight;

  // Create a custom style that removes backgrounds but keeps text coloring
  const customStyle = {
    ...baseStyle,
    'pre[class*="language-"]': {
      ...baseStyle['pre[class*="language-"]'],
      background: 'transparent',
      margin: 0,
      padding: 0,
    },
    'code[class*="language-"]': {
      ...baseStyle['code[class*="language-"]'],
      background: 'transparent',
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);

    toast({
      title: "Copied to clipboard",
      description: "Code snippet copied to clipboard",
    });
  };

  const languageDisplay = {
    bash: "Shell",
    shell: "Shell",
    javascript: "JavaScript",
    typescript: "TypeScript",
    python: "Python",
    jsx: "React",
    tsx: "React",
  }[language] || language;

  // Combine styles including height if provided
  const containerStyle = {
    ...style,
    height: height || style?.height,
    display: 'flex',
    flexDirection: 'column' as const
  };

  return (
    <div
      className={cn(
        "rounded-md overflow-hidden border",
        isDark
          ? "border-gray-800 bg-black text-gray-100"
          : "border-gray-200 bg-white text-gray-900",
        className
      )}
      style={containerStyle}
    >
      <div className={cn(
        "flex items-center justify-between border-b",
        compact ? "px-3 py-1.5" : "px-4 py-2",
        isDark ? "border-gray-800" : "border-gray-200"
      )}>
        <div className="flex items-center gap-2">
          {badgeText && (
            <Badge className={`${badgeColor} text-white text-xs px-1.5 py-0 rounded h-5`}>
              {badgeText}
            </Badge>
          )}
          {title && <span className={cn(compact ? "text-[10px] uppercase tracking-wide text-muted-foreground" : "text-xs font-medium", !compact && (isDark ? "text-gray-200" : "text-gray-700"))}>{title}</span>}
        </div>
        <Button
          size="sm"
          variant="ghost"
          className={cn("h-6 w-6 p-0", isDark ? "text-gray-400 hover:text-white" : "text-gray-500 hover:text-gray-900")}
          onClick={handleCopyCode}
          disabled={disabled}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        </Button>
      </div>
      <div className={cn("flex-1 overflow-auto", compact ? "px-3 py-2" : "px-4 py-3", isDark ? "bg-black" : "bg-white")}>
        <SyntaxHighlighter
          language={language}
          style={customStyle}
          customStyle={{
            fontSize: compact ? '0.7rem' : '0.75rem',
            background: 'transparent',
            margin: 0,
            padding: 0,
            height: '100%'
          }}
          wrapLongLines={false}
          showLineNumbers={false}
          codeTagProps={{
            style: {
              fontSize: compact ? '0.7rem' : '0.75rem',
              fontFamily: 'monospace',
            }
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
      {footerContent && (
        <div className={cn(
          "px-4 py-2 border-t",
          isDark ? "border-gray-800 text-white" : "border-gray-200 text-gray-700"
        )}>
          {footerContent}
        </div>
      )}
    </div>
  );
}
