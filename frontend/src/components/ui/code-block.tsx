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
    <div className="rounded-md overflow-hidden border bg-card text-card-foreground">
      <div className="flex items-center bg-muted px-4 py-2 justify-between border-b">
        <div className="flex items-center gap-3">
          {badgeText && (
            <Badge className={`${badgeColor} text-white text-xs font-bold px-2 rounded`}>
              {badgeText}
            </Badge>
          )}
          {title && <span className="text-sm font-medium">{title}</span>}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs border rounded px-2 py-1">
            <span className="font-medium">{languageDisplay}</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
            onClick={handleCopyCode}
            disabled={disabled}
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </div>
      <div className="p-4 bg-card">
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
          showLineNumbers={true}
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
      {footerContent && <div className="px-4 py-2 border-t">{footerContent}</div>}
    </div>
  );
}
