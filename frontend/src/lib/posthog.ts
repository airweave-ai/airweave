/**
 * PostHog Analytics Initialization
 *
 * SECURITY NOTE: Previously loaded from CDN without integrity checks.
 * Now using npm package for CASA-6 compliance (no untrusted external scripts).
 */

import posthog from 'posthog-js';

// PostHog configuration
const POSTHOG_KEY = 'phc_pRMEx1bwjdogqrCL4xpfEoEwXds7eONicNSWhX45M8M';
const POSTHOG_HOST = 'https://eu.i.posthog.com';

let isInitialized = false;

/**
 * Initialize PostHog analytics
 * Should be called once at app startup
 */
export function initPostHog() {
  if (isInitialized) {
    console.warn('PostHog already initialized');
    return;
  }

  try {
    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      person_profiles: 'always',
      // Enable session recording for better debugging
      session_recording: {
        maskAllInputs: true,
        maskTextSelector: '[data-sensitive]',
      },
      // Respect user privacy
      opt_out_capturing_by_default: false,
      // Advanced options
      loaded: () => {
        console.log('✅ PostHog initialized successfully');
        isInitialized = true;
      },
    });
  } catch (error) {
    console.error('Failed to initialize PostHog:', error);
  }
}

/**
 * Get PostHog instance
 * Use this for custom tracking calls
 */
export function getPostHog() {
  return posthog;
}

/**
 * Check if PostHog is initialized
 */
export function isPostHogInitialized() {
  return isInitialized;
}

/**
 * Opt user out of tracking
 */
export function optOut() {
  posthog.opt_out_capturing();
}

/**
 * Opt user into tracking (enable analytics)
 */
export function optInToTracking() {
  posthog.opt_in_capturing();
}
