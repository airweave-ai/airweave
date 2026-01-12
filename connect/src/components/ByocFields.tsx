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
  return (
    <div className="mb-4">
      <p
        className="text-xs mb-3"
        style={{ color: "var(--connect-text-muted)" }}
      >
        This integration requires you to provide your own OAuth app credentials.
      </p>

      <div className="mb-3">
        <label
          htmlFor="byoc-client-id"
          className="block text-sm font-medium mb-1"
          style={{ color: "var(--connect-text)" }}
        >
          Client ID
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
          placeholder="Your OAuth app client ID"
          className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
          style={{
            backgroundColor: "var(--connect-surface)",
            color: "var(--connect-text)",
            borderColor: errors.byoc_client_id
              ? "var(--connect-error)"
              : "var(--connect-border)",
          }}
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
          Client Secret
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
          placeholder="Your OAuth app client secret"
          className="w-full px-3 py-2 text-sm rounded-md border outline-none transition-colors"
          style={{
            backgroundColor: "var(--connect-surface)",
            color: "var(--connect-text)",
            borderColor: errors.byoc_client_secret
              ? "var(--connect-error)"
              : "var(--connect-border)",
          }}
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
