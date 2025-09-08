import React, { useState, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';

interface RecencyBiasSliderProps {
    value: number;
    onChange: (value: number) => void;
    className?: string;
}

export const RecencyBiasSlider: React.FC<RecencyBiasSliderProps> = ({
    value,
    onChange,
    className
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const [localValue, setLocalValue] = useState(value);
    const [isDragging, setIsDragging] = useState(false);
    const sliderRef = useRef<HTMLDivElement>(null);
    const thumbRef = useRef<HTMLDivElement>(null);

    // Update local value when prop changes
    useEffect(() => {
        setLocalValue(value);
    }, [value]);

    // Calculate position from value (0-1)
    const getPositionFromValue = (val: number): number => {
        return Math.max(0, Math.min(100, val * 100));
    };

    // Calculate value from position
    const getValueFromPosition = (clientX: number): number => {
        if (!sliderRef.current) return 0;

        const rect = sliderRef.current.getBoundingClientRect();
        const position = (clientX - rect.left) / rect.width;
        const clampedPosition = Math.max(0, Math.min(1, position));

        // Round to 1 decimal place
        return Math.round(clampedPosition * 10) / 10;
    };

    // Handle mouse down on thumb or track
    const handleMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);

        // If clicking on track (not thumb), move thumb to click position
        const newValue = getValueFromPosition(e.clientX);
        setLocalValue(newValue);
        onChange(newValue);
    };

    // Handle mouse move
    useEffect(() => {
        if (!isDragging) return;

        const handleMouseMove = (e: MouseEvent) => {
            const newValue = getValueFromPosition(e.clientX);
            setLocalValue(newValue);
            onChange(newValue);
        };

        const handleMouseUp = () => {
            setIsDragging(false);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, onChange]);

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
                className={cn(
                    "relative h-1.5 rounded-full cursor-pointer",
                    isDark ? "bg-gray-700" : "bg-gray-300"
                )}
                onMouseDown={handleMouseDown}
            >
                {/* Filled track */}
                <div
                    className={cn(
                        "absolute left-0 top-0 h-full rounded-full",
                        localValue > 0
                            ? "bg-primary"
                            : isDark ? "bg-gray-600" : "bg-gray-400"
                    )}
                    style={{
                        width: `${position}%`,
                        transition: isDragging ? 'none' : 'width 0.1s ease-out'
                    }}
                />

                {/* Thumb */}
                <div
                    ref={thumbRef}
                    className={cn(
                        "absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full shadow-md cursor-grab",
                        isDragging && "cursor-grabbing",
                        localValue > 0
                            ? "bg-primary border border-white"
                            : "bg-white border border-gray-400"
                    )}
                    style={{
                        left: `${position}%`,
                        transform: `translateX(-50%) translateY(-50%)`,
                        transition: isDragging ? 'none' : 'left 0.1s ease-out, background-color 0.2s'
                    }}
                    onMouseDown={(e) => {
                        e.stopPropagation();
                        setIsDragging(true);
                    }}
                />
            </div>
        </div>
    );
};
