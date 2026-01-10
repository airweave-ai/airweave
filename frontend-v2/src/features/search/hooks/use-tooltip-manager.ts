/**
 * useTooltipManager - Manages tooltip open/close state with delay for hover interactions
 */

import { useCallback, useEffect, useRef, useState } from "react";

const TOOLTIP_CLOSE_DELAY = 100;

export function useTooltipManager() {
  const [openTooltip, setOpenTooltip] = useState<string | null>(null);
  const [hoveredContent, setHoveredContent] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = useCallback((tooltipId: string) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setOpenTooltip(tooltipId);
  }, []);

  const handleMouseLeave = useCallback(
    (tooltipId: string) => {
      if (hoveredContent !== tooltipId) {
        timeoutRef.current = setTimeout(() => {
          setOpenTooltip((prev) => (prev === tooltipId ? null : prev));
        }, TOOLTIP_CLOSE_DELAY);
      }
    },
    [hoveredContent]
  );

  const handleContentMouseEnter = useCallback((tooltipId: string) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setHoveredContent(tooltipId);
    setOpenTooltip(tooltipId);
  }, []);

  const handleContentMouseLeave = useCallback((tooltipId: string) => {
    setHoveredContent(null);
    timeoutRef.current = setTimeout(() => {
      setOpenTooltip((prev) => (prev === tooltipId ? null : prev));
    }, TOOLTIP_CLOSE_DELAY);
  }, []);

  const forceOpen = useCallback((tooltipId: string) => {
    setOpenTooltip(tooltipId);
  }, []);

  return {
    openTooltip,
    handleMouseEnter,
    handleMouseLeave,
    handleContentMouseEnter,
    handleContentMouseLeave,
    forceOpen,
  };
}
