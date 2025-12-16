'use client'

import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useTheme } from 'next-themes'
import * as React from 'react'
import { createHighlighter, type Highlighter } from 'shiki'

interface CurlCommandBlockProps {
  collectionName: string
  onCollectionNameChange: (value: string) => void
  readableId: string
  className?: string
}

export function CurlCommandBlock({
  collectionName,
  onCollectionNameChange,
  readableId,
  className,
}: CurlCommandBlockProps) {
  const { theme, resolvedTheme } = useTheme()
  const [highlightedParts, setHighlightedParts] = React.useState<{
    before: string
    after: string
  }>({ before: '', after: '' })
  const [isLoading, setIsLoading] = React.useState(true)
  const highlighterRef = React.useRef<Highlighter | null>(null)

  React.useEffect(() => {
    let isMounted = true

    const initHighlighter = async () => {
      try {
        if (!highlighterRef.current) {
          highlighterRef.current = await createHighlighter({
            themes: ['github-dark', 'github-light'],
            langs: ['bash', 'shell'],
          })
        }

        if (!isMounted) return

        const currentTheme =
          resolvedTheme === 'dark' || theme === 'dark'
            ? 'github-dark'
            : 'github-light'

        // Split the cURL command into parts before and after the input
        const beforeInput = `curl -X POST https://api.airweave.ai/collections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "`

        const afterInput = `",
  "readable_id": "${readableId}"
}'`

        const beforeHtml = highlighterRef.current.codeToHtml(beforeInput, {
          lang: 'bash',
          theme: currentTheme,
        })

        const afterHtml = highlighterRef.current.codeToHtml(afterInput, {
          lang: 'bash',
          theme: currentTheme,
        })

        if (isMounted) {
          setHighlightedParts({ before: beforeHtml, after: afterHtml })
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error highlighting cURL command:', error)
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    initHighlighter()

    return () => {
      isMounted = false
    }
  }, [readableId, theme, resolvedTheme])

  if (isLoading) {
    return (
      <div
        className={cn(
          'rounded-lg border border-border/50 overflow-hidden bg-background shadow-xs',
          className,
        )}
      >
        <div className="bg-muted/50 px-3 py-1.5 border-b border-border/50">
          <span className="text-xs font-medium text-muted-foreground">
            Request
          </span>
        </div>
        <div className="p-4">
          <pre className="text-xs font-mono text-foreground/90 leading-relaxed">
            <code>Loading...</code>
          </pre>
        </div>
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
      <div className="bg-muted/50 px-3 py-1.5 border-b border-border/50">
        <span className="text-xs font-medium text-muted-foreground">
          Request
        </span>
      </div>
      <div className="p-4">
        <div className="text-xs font-mono leading-relaxed whitespace-pre-wrap">
          <span
            className="inline [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:!inline-block [&_pre]:text-xs [&_pre]:font-mono [&_pre]:leading-relaxed [&_code]:!bg-transparent [&_code]:inline [&_code]:text-xs [&_code]:font-mono"
            dangerouslySetInnerHTML={{ __html: highlightedParts.before }}
          />
          <Input
            value={collectionName}
            onChange={(e) => onCollectionNameChange(e.target.value)}
            placeholder="Finance Data"
            className="h-5 px-1.5 text-xs font-mono border border-border/50 bg-background focus-visible:ring-1 focus-visible:ring-ring inline-block w-32 align-middle mx-0.5"
            style={{ minWidth: '120px' }}
          />
          <span
            className="inline [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:!inline-block [&_pre]:text-xs [&_pre]:font-mono [&_pre]:leading-relaxed [&_code]:!bg-transparent [&_code]:inline [&_code]:text-xs [&_code]:font-mono"
            dangerouslySetInnerHTML={{ __html: highlightedParts.after }}
          />
        </div>
      </div>
    </div>
  )
}
