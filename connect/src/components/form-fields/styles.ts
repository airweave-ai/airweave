export const inputBaseStyles = (error?: string) => ({
  backgroundColor: "var(--connect-surface)",
  color: "var(--connect-text)",
  borderColor: error ? "var(--connect-error)" : "var(--connect-border)",
});
