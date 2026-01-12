export const env = {
  VITE_API_URL: import.meta.env.VITE_API_URL || "http://localhost:8001",
} as const;
