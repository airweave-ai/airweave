import * as React from 'react';
import { IconCheck, IconCopy } from '@tabler/icons-react';
import { useCopyToClipboard } from '@/shared/hooks/use-copy-to-clipboard';
import { Button } from '@/shared/ui/button';
import { CodeSnippet } from '@/shared/ui/code-snippet';

const RAW_RESPONSE_HIGHLIGHT_LINE_LIMIT = 500;
const RAW_RESPONSE_HIGHLIGHT_CHARACTER_LIMIT = 30_000;
const RAW_RESPONSE_PREVIEW_LINE_LIMIT = 1_000;
const RAW_RESPONSE_PREVIEW_CHARACTER_LIMIT = 80_000;

export function CollectionSearchRawTabContent({
  payload,
}: {
  payload: unknown;
}) {
  const { copied, copy } = useCopyToClipboard();
  const [showFullResponse, setShowFullResponse] = React.useState(false);
  const rawResponse = React.useMemo(
    () => JSON.stringify(payload, null, 2),
    [payload],
  );
  const rawResponseLines = React.useMemo(
    () => rawResponse.split('\n'),
    [rawResponse],
  );

  const isLineTruncated =
    rawResponseLines.length > RAW_RESPONSE_PREVIEW_LINE_LIMIT;
  const isCharacterTruncated =
    rawResponse.length > RAW_RESPONSE_PREVIEW_CHARACTER_LIMIT;
  const shouldTruncate =
    !showFullResponse && (isLineTruncated || isCharacterTruncated);
  const displayedResponse = React.useMemo(() => {
    if (showFullResponse) {
      return rawResponse;
    }

    if (isLineTruncated) {
      return `${rawResponseLines.slice(0, RAW_RESPONSE_PREVIEW_LINE_LIMIT).join('\n')}\n...`;
    }

    if (isCharacterTruncated) {
      return `${rawResponse.slice(0, RAW_RESPONSE_PREVIEW_CHARACTER_LIMIT)}\n...`;
    }

    return rawResponse;
  }, [
    isCharacterTruncated,
    isLineTruncated,
    rawResponse,
    rawResponseLines,
    showFullResponse,
  ]);
  const displayLineCount = React.useMemo(
    () => displayedResponse.split('\n').length,
    [displayedResponse],
  );
  const usePlainText =
    displayLineCount > RAW_RESPONSE_HIGHLIGHT_LINE_LIMIT ||
    displayedResponse.length > RAW_RESPONSE_HIGHLIGHT_CHARACTER_LIMIT;
  const remainingContentLabel = isLineTruncated
    ? `+${(rawResponseLines.length - RAW_RESPONSE_PREVIEW_LINE_LIMIT).toLocaleString()} lines`
    : `+${(rawResponse.length - RAW_RESPONSE_PREVIEW_CHARACTER_LIMIT).toLocaleString()} chars`;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex min-h-0 flex-1 items-start gap-6">
        <div className="min-h-0 flex-1 overflow-auto rounded-sm pr-1">
          {usePlainText ? (
            <pre className="font-mono text-xs leading-5 break-words whitespace-pre-wrap text-foreground">
              {displayedResponse}
            </pre>
          ) : (
            <CodeSnippet
              className="text-foreground"
              code={displayedResponse}
              language="json"
            />
          )}
        </div>

        <Button
          aria-label="Copy raw response"
          className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => void copy(rawResponse)}
          size="icon-xs"
          type="button"
          variant="ghost"
        >
          {copied ? (
            <IconCheck className="size-3.5" />
          ) : (
            <IconCopy className="size-3.5" />
          )}
        </Button>
      </div>

      {shouldTruncate ? (
        <div className="flex items-center justify-center gap-2 border-t border-border/60 pt-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowFullResponse(true)}
          >
            Load full response
          </Button>

          <span className="font-mono text-[11px] text-muted-foreground">
            {remainingContentLabel}
          </span>
        </div>
      ) : null}
    </div>
  );
}
