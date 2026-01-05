import { useCallback, useEffect, useState } from "react";

interface DragInteractionOptions<T> {
  /** Callback when dragging starts (on mousedown) */
  onDragStart?: (event: MouseEvent | React.MouseEvent) => void;
  /** Callback during drag (on mousemove) - receives the event and any computed value */
  onDrag: (event: MouseEvent, value: T) => void;
  /** Callback when dragging ends (on mouseup) */
  onDragEnd?: () => void;
  /** Function to compute a value from the mouse event (e.g., position to slider value) */
  computeValue: (event: MouseEvent | React.MouseEvent) => T;
}

interface DragInteractionResult<T> {
  /** Whether currently dragging */
  isDragging: boolean;
  /** Handler to attach to onMouseDown */
  onMouseDown: (event: React.MouseEvent) => void;
  /** Current computed value during drag */
  currentValue: T | null;
}

/**
 * Hook for handling mouse drag interactions (e.g., sliders, resize handles).
 * Manages document-level mousemove/mouseup listeners during drag.
 *
 * @example
 * ```tsx
 * const sliderRef = useRef<HTMLDivElement>(null);
 *
 * const { isDragging, onMouseDown } = useDragInteraction({
 *   computeValue: (e) => {
 *     if (!sliderRef.current) return 0;
 *     const rect = sliderRef.current.getBoundingClientRect();
 *     return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
 *   },
 *   onDrag: (e, value) => {
 *     setSliderValue(value);
 *     onChange(value);
 *   },
 * });
 *
 * return (
 *   <div ref={sliderRef} onMouseDown={onMouseDown}>
 *     <div className={isDragging ? "cursor-grabbing" : "cursor-grab"} />
 *   </div>
 * );
 * ```
 */
export function useDragInteraction<T>({
  onDragStart,
  onDrag,
  onDragEnd,
  computeValue,
}: DragInteractionOptions<T>): DragInteractionResult<T> {
  const [isDragging, setIsDragging] = useState(false);
  const [currentValue, setCurrentValue] = useState<T | null>(null);

  const handleMouseDown = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      setIsDragging(true);

      const value = computeValue(event);
      setCurrentValue(value);

      onDragStart?.(event);
      // Trigger initial drag callback with computed value
      onDrag(event.nativeEvent, value);
    },
    [computeValue, onDrag, onDragStart]
  );

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (event: MouseEvent) => {
      const value = computeValue(event);
      setCurrentValue(value);
      onDrag(event, value);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setCurrentValue(null);
      onDragEnd?.();
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, computeValue, onDrag, onDragEnd]);

  return {
    isDragging,
    onMouseDown: handleMouseDown,
    currentValue,
  };
}
