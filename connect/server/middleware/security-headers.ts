import { defineEventHandler } from "h3";

/**
 * Security headers middleware for the Connect widget.
 *
 * CRITICAL: Connect is designed to be embedded in iframes, so we MUST NOT
 * set X-Frame-Options: DENY or restrictive frame-ancestors.
 *
 * The frame-ancestors directive allows embedding from:
 * - Airweave frontend apps (dev, staging, production)
 * - localhost for development
 */
export default defineEventHandler((event) => {
  const headers = event.node.res;

  // Content Security Policy
  // - frame-ancestors: Allow iframe embedding from Airweave apps and localhost
  // - connect-src: Allow API calls to backend endpoints
  const csp = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "connect-src 'self' http://localhost:8001 https://api.dev-airweave.com https://api.stg-airweave.com https://api.airweave.ai",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "font-src 'self' data:",
    "base-uri 'self'",
    "form-action 'self'",
    // CRITICAL: Allow iframe embedding from Airweave frontend apps
    "frame-ancestors https://app.dev-airweave.com https://app.stg-airweave.com https://app.airweave.ai https://localhost:* http://localhost:*",
  ].join("; ");

  headers.setHeader("Content-Security-Policy", csp);

  // Do NOT set X-Frame-Options as it would conflict with frame-ancestors
  // and could prevent iframe embedding in some browsers

  // Other security headers
  headers.setHeader("X-Content-Type-Options", "nosniff");
  headers.setHeader("X-XSS-Protection", "1; mode=block");
  headers.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.setHeader(
    "Permissions-Policy",
    "geolocation=(), microphone=(), camera=()"
  );
});
