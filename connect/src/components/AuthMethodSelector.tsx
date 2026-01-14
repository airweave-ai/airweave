import { ExternalLink, Key } from "lucide-react";
import { useTheme } from "../lib/theme";
import type { AuthenticationMethod } from "../lib/types";

interface AuthMethodSelectorProps {
  methods: AuthenticationMethod[];
  selected: "direct" | "oauth_browser";
  onChange: (method: "direct" | "oauth_browser") => void;
  sourceName: string;
}

interface MethodOption {
  value: "direct" | "oauth_browser";
  label: string;
  description: string;
  icon: React.ReactNode;
}

export function AuthMethodSelector({
  methods,
  selected,
  onChange,
  sourceName,
}: AuthMethodSelectorProps) {
  const { labels } = useTheme();

  // Filter to only direct and oauth_browser (skip auth_provider per spec)
  const availableMethods = methods.filter(
    (m): m is "direct" | "oauth_browser" =>
      m === "direct" || m === "oauth_browser",
  );

  // Don't render if only one method available
  if (availableMethods.length <= 1) {
    return null;
  }

  const options: MethodOption[] = availableMethods.map((method) => {
    if (method === "direct") {
      return {
        value: "direct",
        label: labels.authMethodDirect,
        description: labels.authMethodDirectDescription,
        icon: <Key className="w-5 h-5" />,
      };
    }
    return {
      value: "oauth_browser",
      label: labels.authMethodOAuth.replace("{source}", sourceName),
      description: labels.authMethodOAuthDescription,
      icon: <ExternalLink className="w-5 h-5" />,
    };
  });

  return (
    <div className="mb-4">
      <label
        className="block text-sm font-medium mb-2"
        style={{ color: "var(--connect-text)" }}
      >
        {labels.authMethodLabel}
      </label>
      <div className="flex flex-col gap-2">
        {options.map((option) => {
          const isSelected = selected === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onChange(option.value)}
              role="radio"
              aria-checked={isSelected}
              className="flex items-center gap-3 p-3 rounded-lg w-full text-left transition-colors duration-150 cursor-pointer border"
              style={{
                backgroundColor: "var(--connect-surface)",
                borderColor: isSelected
                  ? "var(--connect-primary)"
                  : "var(--connect-border)",
                borderWidth: isSelected ? "2px" : "1px",
              }}
            >
              <div
                className="flex-shrink-0 p-2 rounded-md"
                style={{
                  backgroundColor: isSelected
                    ? "var(--connect-primary)"
                    : "var(--connect-border)",
                  color: isSelected ? "white" : "var(--connect-text-muted)",
                }}
              >
                {option.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className="font-medium text-sm"
                  style={{ color: "var(--connect-text)" }}
                >
                  {option.label}
                </p>
                <p
                  className="text-xs mt-0.5"
                  style={{ color: "var(--connect-text-muted)" }}
                >
                  {option.description}
                </p>
              </div>
              <div
                className="flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center"
                style={{
                  borderColor: isSelected
                    ? "var(--connect-primary)"
                    : "var(--connect-border)",
                }}
              >
                {isSelected && (
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: "var(--connect-primary)" }}
                  />
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
