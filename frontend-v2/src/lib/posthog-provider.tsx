/**
 * PostHog Analytics Provider
 *
 * Uses npm package instead of CDN for CASA-6 compliance (no untrusted external scripts).
 * Initializes outside React to avoid race conditions and ensure session exists before API calls.
 */

import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";

// PostHog configuration
const POSTHOG_KEY = "phc_Ytp26UB3WwGCdjHTpDBI9HQg2ZA38ITMDKI6fE6EPGS";
const POSTHOG_HOST = "https://eu.posthog.com";

if (typeof window !== "undefined") {
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    person_profiles: "always",
    capture_pageview: false,
    session_recording: {
      maskAllInputs: true,
      maskTextSelector: "[data-sensitive]",
    },
    opt_out_capturing_by_default: false,
    loaded: () => {
      posthog.capture("$pageview");
    },
  });

  // Expose posthog on window for API client session tracking
  (window as unknown as { posthog: typeof posthog }).posthog = posthog;
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  return <PHProvider client={posthog}>{children}</PHProvider>;
}

export { posthog };
