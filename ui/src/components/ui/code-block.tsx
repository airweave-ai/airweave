'use client'

import { useTheme } from 'next-themes'
import * as React from 'react'
import { createHighlighter, type Highlighter } from 'shiki'
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
  const { theme, resolvedTheme } = useTheme()
  const [highlightedCode, setHighlightedCode] = React.useState<string>('')
  const [isLoading, setIsLoading] = React.useState(true)
  const highlighterRef = React.useRef<Highlighter | null>(null)

  React.useEffect(() => {
    let isMounted = true

    const initHighlighter = async () => {
      try {
        if (!highlighterRef.current) {
          highlighterRef.current = await createHighlighter({
            themes: ['github-dark', 'github-light'],
            langs: [language, 'json', 'bash', 'shell'],
          })
        }

        if (!isMounted) return

        const currentTheme =
          resolvedTheme === 'dark' || theme === 'dark'
            ? 'github-dark'
            : 'github-light'

        const html = highlighterRef.current.codeToHtml(code, {
          lang: language,
          theme: currentTheme,
        })

        if (isMounted) {
          setHighlightedCode(html)
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error highlighting code:', error)
        if (isMounted) {
          setHighlightedCode(code)
          setIsLoading(false)
        }
      }
    }

    initHighlighter()

    return () => {
      isMounted = false
    }
  }, [code, language, theme, resolvedTheme])

  if (isLoading) {
    return (
      <div
        className={cn(
          'rounded-lg border border-border/50 overflow-hidden bg-muted/20',
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
        <pre className="p-4 overflow-x-auto bg-muted/20">
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
        'rounded-lg border border-border/50 overflow-hidden bg-muted/20',
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
        className="p-4 overflow-x-auto bg-muted/20 [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:text-xs [&_pre]:font-mono [&_pre]:leading-relaxed [&_code]:!bg-transparent"
        dangerouslySetInnerHTML={{ __html: highlightedCode }}
      />
    </div>
  )
}

