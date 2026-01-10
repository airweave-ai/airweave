export function utcNow(): number {
  return Date.now();
}

// Backend sends naive UTC timestamps like "2024-01-15T10:00:00" without timezone suffix
export function parseBackendTimestamp(
  timestamp: string | null | undefined
): number | null {
  if (!timestamp) return null;

  const hasTimezoneInfo =
    timestamp.includes("Z") || /[+-]\d{2}:?\d{2}$/.test(timestamp);

  const utcTimestamp = hasTimezoneInfo ? timestamp : timestamp + "Z";
  const parsed = Date.parse(utcTimestamp);

  return isNaN(parsed) ? null : parsed;
}

const MAX_RUNTIME_MS = 24 * 60 * 60 * 1000;

export function calculateRuntime(startTime: number, endTime?: number): number {
  const end = endTime ?? utcNow();
  const runtime = end - startTime;

  if (runtime < 0 || runtime > MAX_RUNTIME_MS) {
    console.warn("Unreasonable runtime detected:", runtime, "ms");
    return 0;
  }

  return runtime;
}

export function formatRuntime(milliseconds: number): string {
  if (milliseconds === 0) return "N/A";

  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
}
