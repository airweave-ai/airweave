import { X } from "lucide-react";
import { useState } from "react";
import type { ConfigField } from "../../lib/types";
import { FieldWrapper } from "./FieldWrapper";
import { inputBaseStyles } from "./styles";

interface ArrayFieldProps {
  field: ConfigField;
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
}

export function ArrayField({ field, value, onChange, error }: ArrayFieldProps) {
  const [inputValue, setInputValue] = useState("");
  const arrayValue = value ?? [];
  const inputId = `input-${field.name}`;
  const errorId = `error-${field.name}`;

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !arrayValue.includes(trimmed)) {
      onChange([...arrayValue, trimmed]);
    }
    setInputValue("");
  };

  const removeTag = (index: number) => {
    const newArray = [...arrayValue];
    newArray.splice(index, 1);
    onChange(newArray);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(inputValue);
    } else if (
      e.key === "Backspace" &&
      inputValue === "" &&
      arrayValue.length > 0
    ) {
      removeTag(arrayValue.length - 1);
    }
  };

  return (
    <FieldWrapper field={field} error={error}>
      <div
        className="flex flex-wrap gap-1 p-2 rounded-md border min-h-[42px]"
        style={inputBaseStyles(error)}
      >
        {arrayValue.map((tag, index) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded"
            style={{
              backgroundColor: "var(--connect-primary)",
              color: "var(--connect-primary-foreground)",
            }}
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(index)}
              className="hover:opacity-80"
              aria-label={`Remove ${tag}`}
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
        <input
          id={inputId}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => inputValue && addTag(inputValue)}
          placeholder={arrayValue.length === 0 ? "Type and press Enter" : ""}
          className="flex-1 min-w-[100px] text-sm bg-transparent border-none outline-none"
          style={{ color: "var(--connect-text)" }}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : undefined}
        />
      </div>
    </FieldWrapper>
  );
}
