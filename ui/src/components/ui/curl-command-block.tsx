'use client'

import { Input } from '@/components/ui/input'
import { useShikiHighlighter } from '@/hooks/use-shiki-highlighter'
import { cn } from '@/lib/utils'

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
  const beforeInput = `curl -X POST https://api.airweave.ai/collections \\
     -H "x-api-key: <apiKey>" \\
     -H "Content-Type: application/json" \\
     -d '{
  "name": "`

  const afterInput = `",
  "readable_id": "${readableId}"
}'`

  const { highlightedCode: beforeHtml, isLoading: beforeLoading } =
    useShikiHighlighter({ code: beforeInput, language: 'bash' })

  const { highlightedCode: afterHtml, isLoading: afterLoading } =
    useShikiHighlighter({ code: afterInput, language: 'bash' })

  const isLoading = beforeLoading || afterLoading

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
            dangerouslySetInnerHTML={{ __html: beforeHtml }}
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
            dangerouslySetInnerHTML={{ __html: afterHtml }}
          />
        </div>
      </div>
    </div>
  )
}
