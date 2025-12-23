'use client'

import { useShikiHighlighter } from '@/hooks/use-shiki-highlighter'
import { cn } from '@/lib/utils'

interface CodeBlockProps {
  code: string
  language: string
  title?: string
  className?: string
}

export function CodeBlock({
  code,
  language,
  title,
  className,
}: CodeBlockProps) {
  const { highlightedCode, isLoading } = useShikiHighlighter({ code, language })

  if (isLoading) {
    return (
      <div
        className={cn(
          'rounded-lg border border-border/50 overflow-hidden bg-background shadow-xs',
          className,
        )}
      >
        {title && (
          <div className="bg-muted/50 px-3 py-1.5 border-b border-border/50">
            <span className="text-xs font-medium text-muted-foreground">
              {title}
            </span>
          </div>
        )}
        <pre className="p-4 overflow-x-auto bg-background shadow-xs">
          <code className="text-xs font-mono text-foreground/90 leading-relaxed">
            {code}
          </code>
        </pre>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-border/50 overflow-hidden bg-background shadow-xs',
        className,
      )}
    >
      {title && (
        <div className="bg-muted/50 px-3 py-1.5 border-b border-border/50">
          <span className="text-xs font-medium text-muted-foreground">
            {title}
          </span>
        </div>
      )}
      <div
        className="p-4 overflow-x-auto bg-background shadow-xs [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:text-xs [&_pre]:font-mono [&_pre]:leading-relaxed [&_code]:!bg-transparent"
        dangerouslySetInnerHTML={{ __html: highlightedCode }}
      />
    </div>
  )
}
