import { useSyncExternalStore } from "react";

const MOBILE_BREAKPOINT = 768;

function subscribe(callback: () => void) {
  const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
  mql.addEventListener("change", callback);
  return () => mql.removeEventListener("change", callback);
}

function getSnapshot() {
  return window.innerWidth < MOBILE_BREAKPOINT;
}

function getServerSnapshot() {
  // Default to non-mobile on server (prevents hydration mismatch)
  return false;
}

export function useIsMobile() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
