/**
 * API Keys helper utilities
 */

interface ExpirationPreset {
  days: number;
  label: string;
  recommended?: boolean;
}

export const EXPIRATION_PRESETS: ExpirationPreset[] = [
  { days: 30, label: "30 days" },
  { days: 60, label: "60 days" },
  { days: 90, label: "90 days", recommended: true },
  { days: 180, label: "180 days" },
  { days: 365, label: "365 days" },
];

/**
 * Mask an API key for display, showing only first 8 characters
 */
export function maskKey(key: string): string {
  if (!key || key.length < 8) return key;
  return `${key.substring(0, 8)}${"•".repeat(32)}`;
}

/**
 * Calculate days remaining until expiration
 */
export function getDaysRemaining(expirationDate: string): number {
  try {
    const expDate = new Date(expirationDate);
    const now = new Date();
    const diffTime = expDate.getTime() - now.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
}

/**
 * Get status color class based on days remaining
 */
export function getStatusColor(daysRemaining: number): string {
  if (daysRemaining < 0) return "text-red-500";
  if (daysRemaining <= 7) return "text-amber-500";
  return "text-muted-foreground";
}

/**
 * Format a date string for display
 */
export function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

/**
 * Action definition for API key operations
 */
export interface ApiKeyAction {
  id: string;
  label: string;
  variant?: "destructive";
  onSelect: () => void;
}

/**
 * Get shared action definitions for an API key.
 * Used by both the dropdown menu and the command menu to keep actions in sync.
 */
export function getApiKeyActions(options: {
  apiKey: { id: string; decrypted_key: string };
  onCopyAsJson: () => void;
  onDelete: () => void;
}): ApiKeyAction[] {
  return [
    {
      id: "copy-json",
      label: "Copy as JSON",
      onSelect: options.onCopyAsJson,
    },
    {
      id: "delete-key",
      label: "Delete API key",
      variant: "destructive",
      onSelect: options.onDelete,
    },
  ];
}
