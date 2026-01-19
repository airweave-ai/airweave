import { useEffect, useRef, type RefObject } from "react";

interface AutoScrollOptions {
  /** Whether auto-scrolling is enabled (default: true) */
  enabled?: boolean;
}

/**
 * Hook that automatically scrolls a container to the bottom when dependencies change.
 * Useful for chat interfaces, logs, and streaming content.
 *
 * @param deps - Dependencies that trigger auto-scroll when changed
 * @param options - Configuration options
 * @returns Ref to attach to the scrollable container
 *
 * @example
 * ```tsx
 * // Auto-scroll when messages change
 * const scrollRef = useAutoScroll([messages]);
 *
 * // Only scroll when actively receiving
 * const scrollRef = useAutoScroll([events], { enabled: isSearching });
 *
 * return (
 *   <div ref={scrollRef} className="overflow-auto">
 *     {messages.map(...)}
 *   </div>
 * );
 * ```
 */
export function useAutoScroll<T extends HTMLElement = HTMLDivElement>(
  deps: unknown[],
  options: AutoScrollOptions = {}
): RefObject<T | null> {
  const { enabled = true } = options;
  const scrollRef = useRef<T>(null);

  useEffect(() => {
    if (!enabled || !scrollRef.current) return;

    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  return scrollRef;
}
