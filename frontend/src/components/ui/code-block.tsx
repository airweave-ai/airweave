import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { materialOceanic, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from "@/lib/theme-provider";

interface CodeBlockProps {
  code: string;
  language: string;
  badgeText?: string;
  badgeColor?: string;
  title?: string;
  footerContent?: React.ReactNode;
  disabled?: boolean;
}

export function CodeBlock({
  code,
  language,
  badgeText,
  badgeColor = "bg-blue-600 hover:bg-blue-600",
  title,
  footerContent,
  disabled = false
}: CodeBlockProps) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);
  const { theme } = useTheme();
  const isDarkTheme = theme === "dark";

  // Choose base style based on theme
  const baseStyle = isDarkTheme ? materialOceanic : oneLight;

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

  return (
    <div className="rounded-md overflow-hidden border border-border/50 bg-muted/30 text-card-foreground">
      <div className="flex items-center px-3 py-1.5 justify-between border-b border-border/40">
        <div className="flex items-center gap-2">
          {badgeText && (
            <Badge className={`${badgeColor} text-white text-xs px-1.5 py-0 rounded h-5`}>
              {badgeText}
            </Badge>
          )}
          {title && <span className="text-xs font-medium">{title}</span>}
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
          onClick={handleCopyCode}
          disabled={disabled}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        </Button>
      </div>
      <div className="p-2 bg-muted/30">
        <SyntaxHighlighter
          language={language}
          style={customStyle}
          customStyle={{
            fontSize: '0.75rem',
            background: 'transparent',
            margin: 0,
            padding: 0,
          }}
          wrapLongLines={false}
          showLineNumbers={false}
          codeTagProps={{
            style: {
              fontSize: '0.75rem',
              fontFamily: 'monospace',
            }
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
      {footerContent && <div className="px-3 py-1 border-t border-border/40">{footerContent}</div>}
    </div>
  );
}
