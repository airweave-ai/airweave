/**
 * RecencyBiasSlider - Slider for adjusting recency bias in search
 */

import { useCallback, useRef } from "react";

import { useDragInteraction } from "@/hooks/use-drag-interaction";
import { useSyncProp } from "@/hooks/use-sync-prop";
import { cn } from "@/lib/utils";

interface RecencyBiasSliderProps {
  value: number;
  onChange: (value: number) => void;
  className?: string;
}

export function RecencyBiasSlider({
  value,
  onChange,
  className,
}: RecencyBiasSliderProps) {
  const [localValue, setLocalValue] = useSyncProp(value);
  const sliderRef = useRef<HTMLDivElement>(null);

  // Calculate position from value (0-1)
  const getPositionFromValue = (val: number): number => {
    return Math.max(0, Math.min(100, val * 100));
  };

  // Calculate value from position
  const computeValue = useCallback(
    (event: MouseEvent | React.MouseEvent): number => {
      if (!sliderRef.current) return 0;

      const rect = sliderRef.current.getBoundingClientRect();
      const position = (event.clientX - rect.left) / rect.width;
      const clampedPosition = Math.max(0, Math.min(1, position));

      // Round to 1 decimal place
      return Math.round(clampedPosition * 10) / 10;
    },
    []
  );

  // Handle drag interaction
  const { isDragging, onMouseDown } = useDragInteraction({
    computeValue,
    onDrag: (_event, newValue) => {
      setLocalValue(newValue);
      onChange(newValue);
    },
  });

  const position = getPositionFromValue(localValue);

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-white/60">0</span>
        <div className="text-xs font-semibold text-white">
          {localValue.toFixed(1)}
        </div>
        <span className="text-[10px] text-white/60">1</span>
      </div>

      <div
        ref={sliderRef}
        className="relative h-1.5 cursor-pointer rounded-full bg-gray-700"
        onMouseDown={onMouseDown}
      >
        {/* Filled track */}
        <div
          className={cn(
            "absolute top-0 left-0 h-full rounded-full",
            localValue > 0 ? "bg-primary" : "bg-gray-600"
          )}
          style={{
            width: `${position}%`,
            transition: isDragging ? "none" : "width 0.1s ease-out",
          }}
        />

        {/* Thumb */}
        <div
          className={cn(
            "absolute top-1/2 size-4 -translate-y-1/2 cursor-grab rounded-full shadow-md",
            isDragging && "cursor-grabbing",
            localValue > 0
              ? "bg-primary border border-white"
              : "border border-gray-400 bg-white"
          )}
          style={{
            left: `${position}%`,
            transform: `translateX(-50%) translateY(-50%)`,
            transition: isDragging
              ? "none"
              : "left 0.1s ease-out, background-color 0.2s",
          }}
          onMouseDown={onMouseDown}
        />
      </div>
    </div>
  );
}
