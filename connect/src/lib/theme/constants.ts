import type { ThemeColors } from "../types";

export const SYSTEM_FONT_STACK = `-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif`;

// Transparent colors for pending state (no flash)
export const PENDING_COLORS: Required<ThemeColors> = {
  background: "transparent",
  surface: "transparent",
  text: "transparent",
  textMuted: "transparent",
  primary: "transparent",
  primaryForeground: "transparent",
  primaryHover: "transparent",
  secondary: "transparent",
  secondaryHover: "transparent",
  border: "transparent",
  success: "transparent",
  error: "transparent",
};
