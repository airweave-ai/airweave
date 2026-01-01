/**
 * Shared date formatting utilities
 */

export type DateFormatStyle = "short" | "long" | "datetime";

/**
 * Format a date string for display.
 *
 * @param dateString - ISO date string to format
 * @param style - Format style: "short" (Jan 1, 2024), "long" (January 1, 2024), "datetime" (includes time)
 * @returns Formatted date string
 */
export function formatDate(
  dateString: string,
  style: DateFormatStyle = "short"
): string {
  try {
    const date = new Date(dateString);

    // Check for invalid date
    if (isNaN(date.getTime())) {
      return dateString;
    }

    const options: Intl.DateTimeFormatOptions =
      style === "datetime"
        ? {
            year: "numeric",
            month: "long",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          }
        : style === "long"
          ? {
              year: "numeric",
              month: "long",
              day: "numeric",
            }
          : {
              month: "short",
              day: "numeric",
              year: "numeric",
            };

    return date.toLocaleDateString("en-US", options);
  } catch {
    return dateString;
  }
}

/**
 * Calculate days until or since a date.
 * Positive values indicate days in the future, negative values indicate days in the past.
 *
 * @param dateString - ISO date string
 * @returns Number of days (positive = future, negative = past)
 */
export function getDaysFromNow(dateString: string): number {
  try {
    const date = new Date(dateString);

    // Check for invalid date
    if (isNaN(date.getTime())) {
      return 0;
    }

    const now = new Date();
    const diffTime = date.getTime() - now.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
}

/**
 * Format a date as a human-readable relative string (e.g., "3 days ago", "in 2 weeks").
 *
 * @param dateString - ISO date string
 * @returns Human-readable relative time string
 */
export function formatRelativeDate(dateString: string): string {
  const days = getDaysFromNow(dateString);
  const absDays = Math.abs(days);

  if (days === 0) return "today";

  const unit =
    absDays === 1
      ? "day"
      : absDays < 7
        ? "days"
        : absDays < 30
          ? "weeks"
          : "months";
  const value =
    unit === "weeks"
      ? Math.round(absDays / 7)
      : unit === "months"
        ? Math.round(absDays / 30)
        : absDays;

  return days > 0 ? `in ${value} ${unit}` : `${value} ${unit} ago`;
}
