/**
 * PostHog Analytics Provider
 *
 * SECURITY NOTE: Using npm package instead of CDN for CASA-6 compliance
 * (no untrusted external scripts).
 *
 * INITIALIZATION STRATEGY:
 * - Initializes outside React component to avoid race conditions
 * - Manual pageview capture to ensure session is created before API calls
 * - Session recording enabled for debugging (with input masking)
 *
 * USAGE:
 * - Wrap your app with <PostHogProvider> in main.tsx
 * - Import `posthog` instance directly for custom tracking
 * - Session ID is automatically available via posthog.get_session_id()
 */

import posthog from 'posthog-js';
import { PostHogProvider as PHProvider } from 'posthog-js/react';

// PostHog configuration
const POSTHOG_KEY = 'phc_Ytp26UB3WwGCdjHTpDBI9HQg2ZA38ITMDKI6fE6EPGS';
const POSTHOG_HOST = 'https://eu.posthog.com';

// Initialize PostHog outside of React component to avoid race conditions
if (typeof window !== 'undefined') {
    posthog.init(POSTHOG_KEY, {
        api_host: POSTHOG_HOST,
        person_profiles: 'always',
        capture_pageview: false, // We'll capture manually to ensure session is created
        // Enable session recording for better debugging
        session_recording: {
            maskAllInputs: true,
            maskTextSelector: '[data-sensitive]',
        },
        // Respect user privacy
        opt_out_capturing_by_default: false,
        loaded: (posthog) => {
            console.log('✅ PostHog initialized successfully');
            // Capture initial pageview to ensure session is created
            posthog.capture('$pageview');
        },
    });

    // Make posthog available on window for debugging purposes
    (window as any).posthog = posthog;
}

/**
 * PostHog Provider Component
 * Wraps the app to enable PostHog React hooks and automatic event tracking
 */
export function PostHogProvider({ children }: { children: React.ReactNode }) {
    return <PHProvider client={posthog}>{children}</PHProvider>;
}

/**
 * Export posthog instance for direct use in other parts of the app
 */
export { posthog };
