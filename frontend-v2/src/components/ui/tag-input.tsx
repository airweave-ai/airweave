import { useState, KeyboardEvent } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  /** Transform input before adding (e.g., toUpperCase for Jira project keys) */
  transformInput?: (value: string) => string;
}

/**
 * TagInput - A component for entering multiple tags/items
 *
 * Features:
 * - Add tags by pressing Enter or comma
 * - Remove tags by clicking X or pressing Backspace on empty input
 * - Visual feedback for dark/light themes
 * - Keyboard accessible
 */
function TagInput({
  value = [],
  onChange,
  placeholder = "Type and press Enter...",
  className,
  disabled = false,
  transformInput,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState("");

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    // Add tag on Enter or comma
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag();
    }
    // Remove last tag on Backspace if input is empty
    else if (e.key === "Backspace" && !inputValue && value.length > 0) {
      removeTag(value.length - 1);
    }
  };

  const addTag = () => {
    let trimmedValue = inputValue.trim();
    if (trimmedValue) {
      // Apply transformation if provided (e.g., uppercase for Jira keys)
      if (transformInput) {
        trimmedValue = transformInput(trimmedValue);
      }
      // Check for duplicates after transformation
      if (!value.includes(trimmedValue)) {
        onChange([...value, trimmedValue]);
        setInputValue("");
      } else {
        // Still clear input if it's a duplicate
        setInputValue("");
      }
    }
  };

  const removeTag = (indexToRemove: number) => {
    onChange(value.filter((_, index) => index !== indexToRemove));
  };

  const handleInputBlur = () => {
    // Add tag on blur if there's content
    if (inputValue.trim()) {
      addTag();
    }
  };

  return (
    <div
      className={cn(
        "border-input flex min-h-[42px] w-full flex-wrap gap-2 rounded-md border bg-transparent p-2",
        "focus-within:border-ring focus-within:ring-ring/50 focus-within:outline-none focus-within:ring-[3px]",
        "transition-[color,box-shadow]",
        disabled && "pointer-events-none cursor-not-allowed opacity-50",
        className
      )}
    >
      {/* Render existing tags */}
      {value.map((tag, index) => (
        <div
          key={index}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm font-medium",
            "bg-secondary text-secondary-foreground",
            "border-secondary-foreground/20 border",
            "transition-colors"
          )}
        >
          <span>{tag}</span>
          {!disabled && (
            <button
              type="button"
              onClick={() => removeTag(index)}
              className={cn(
                "hover:bg-secondary-foreground/10 rounded-sm p-0.5",
                "focus-visible:ring-ring focus:outline-none focus-visible:ring-1",
                "transition-colors"
              )}
              aria-label={`Remove ${tag}`}
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      ))}

      {/* Input for new tags */}
      {!disabled && (
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleInputBlur}
          placeholder={value.length === 0 ? placeholder : ""}
          className={cn(
            "text-foreground placeholder:text-muted-foreground min-w-[120px] flex-1 bg-transparent text-sm outline-none"
          )}
        />
      )}
    </div>
  );
}

export { TagInput };
export type { TagInputProps };
