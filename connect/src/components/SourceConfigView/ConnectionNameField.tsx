import type { ConnectLabels } from "../../lib/types";
import { inputBaseStyles } from "../form-fields/styles";

interface ConnectionNameFieldProps {
  value: string;
  onChange: (value: string) => void;
  sourceName: string;
  labels: Required<ConnectLabels>;
}

export function ConnectionNameField({
  value,
  onChange,
  sourceName,
  labels,
}: ConnectionNameFieldProps) {
  return (
    <div className="mb-4">
      <label
        htmlFor="connection-name"
        className="block text-sm font-medium mb-1"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.configureNameLabel}
      </label>
      <p
        className="text-xs mt-1 mb-2"
        style={{ color: "var(--connect-text-muted)" }}
      >
        {labels.configureNameDescription}
      </p>
      <input
        id="connection-name"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={labels.configureNamePlaceholder.replace(
          "{source}",
          sourceName,
        )}
        className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
        style={inputBaseStyles()}
      />
    </div>
  );
}
