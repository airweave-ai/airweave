import { useTheme } from "../lib/theme";
import { inputBaseStyles } from "./form-fields/styles";

interface ByocFieldsProps {
  values: { client_id: string; client_secret: string };
  onChange: (values: { client_id: string; client_secret: string }) => void;
  errors: Record<string, string>;
  onClearError: (key: string) => void;
}

export function ByocFields({
  values,
  onChange,
  errors,
  onClearError,
}: ByocFieldsProps) {
  const { labels } = useTheme();

  return (
    <div className="mb-4">
      <p
        className="text-xs mb-3"
        style={{ color: "var(--connect-text-muted)" }}
      >
        {labels.byocDescription}
      </p>

      <div className="mb-3">
        <label
          htmlFor="byoc-client-id"
          className="block text-sm font-medium mb-1"
          style={{ color: "var(--connect-text)" }}
        >
          {labels.byocClientIdLabel}
          <span style={{ color: "var(--connect-error)" }}> *</span>
        </label>
        <input
          id="byoc-client-id"
          type="text"
          value={values.client_id}
          onChange={(e) => {
            onChange({ ...values, client_id: e.target.value });
            if (errors.byoc_client_id) {
              onClearError("byoc_client_id");
            }
          }}
          placeholder={labels.byocClientIdPlaceholder}
          className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
          style={inputBaseStyles(errors.byoc_client_id)}
        />
        {errors.byoc_client_id && (
          <p
            className="text-xs mt-1"
            style={{ color: "var(--connect-error)" }}
          >
            {errors.byoc_client_id}
          </p>
        )}
      </div>

      <div className="mb-3">
        <label
          htmlFor="byoc-client-secret"
          className="block text-sm font-medium mb-1"
          style={{ color: "var(--connect-text)" }}
        >
          {labels.byocClientSecretLabel}
          <span style={{ color: "var(--connect-error)" }}> *</span>
        </label>
        <input
          id="byoc-client-secret"
          type="password"
          value={values.client_secret}
          onChange={(e) => {
            onChange({ ...values, client_secret: e.target.value });
            if (errors.byoc_client_secret) {
              onClearError("byoc_client_secret");
            }
          }}
          placeholder={labels.byocClientSecretPlaceholder}
          className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
          style={inputBaseStyles(errors.byoc_client_secret)}
        />
        {errors.byoc_client_secret && (
          <p
            className="text-xs mt-1"
            style={{ color: "var(--connect-error)" }}
          >
            {errors.byoc_client_secret}
          </p>
        )}
      </div>
    </div>
  );
}
