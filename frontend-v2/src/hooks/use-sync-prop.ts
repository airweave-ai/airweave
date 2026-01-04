import { useEffect, useState } from "react";

/**
 * Hook that keeps local state in sync with a prop value.
 * Updates local state whenever the prop changes.
 *
 * Useful when you need controlled component behavior with local optimistic updates.
 *
 * @param propValue - The prop value to sync with
 * @returns Tuple of [localValue, setLocalValue]
 *
 * @example
 * ```tsx
 * function Slider({ value, onChange }: { value: number; onChange: (v: number) => void }) {
 *   const [localValue, setLocalValue] = useSyncProp(value);
 *
 *   const handleDrag = (newValue: number) => {
 *     setLocalValue(newValue); // Immediate UI update
 *     onChange(newValue);      // Notify parent
 *   };
 *
 *   return <div>{localValue}</div>;
 * }
 * ```
 */
export function useSyncProp<T>(propValue: T): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [localValue, setLocalValue] = useState<T>(propValue);

  useEffect(() => {
    setLocalValue(propValue);
  }, [propValue]);

  return [localValue, setLocalValue];
}

