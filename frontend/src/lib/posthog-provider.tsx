import posthog from 'posthog-js';
import { PostHogProvider as PHProvider } from 'posthog-js/react';

// Initialize PostHog outside of React component to avoid race conditions
if (typeof window !== 'undefined') {
    posthog.init('phc_Ytp26UB3WwGCdjHTpDBI9HQg2ZA38ITMDKI6fE6EPGS', {
        api_host: 'https://eu.posthog.com',
        person_profiles: 'always',
        capture_pageview: false, // We'll capture manually to ensure session is created
        loaded: (posthog) => {
            console.log('[PostHog] Loaded successfully');
            // Capture initial pageview to ensure session is created
            posthog.capture('$pageview');
        },
    });

    // Make posthog available on window for backward compatibility
    (window as any).posthog = posthog;
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
    return <PHProvider client={posthog}>{children}</PHProvider>;
}

// Export posthog instance for use in other parts of the app
export { posthog };

