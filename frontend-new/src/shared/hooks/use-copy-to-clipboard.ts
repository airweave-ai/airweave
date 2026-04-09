import * as React from 'react';

export function useCopyToClipboard({ resetDelayMs = 1500 } = {}) {
  const [copied, setCopied] = React.useState(false);
  const resetTimeoutRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    return () => {
      if (resetTimeoutRef.current !== null) {
        window.clearTimeout(resetTimeoutRef.current);
      }
    };
  }, []);

  const copy = React.useCallback(
    async (value: string) => {
      await navigator.clipboard.writeText(value);
      setCopied(true);

      if (resetTimeoutRef.current !== null) {
        window.clearTimeout(resetTimeoutRef.current);
      }

      resetTimeoutRef.current = window.setTimeout(() => {
        setCopied(false);
        resetTimeoutRef.current = null;
      }, resetDelayMs);
    },
    [resetDelayMs],
  );

  return { copied, copy };
}
