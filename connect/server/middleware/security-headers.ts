import { defineEventHandler } from "h3";

/**
 * Security headers middleware for the Connect widget.
 *
 * CRITICAL: Connect is designed to be embedded in iframes, so we MUST NOT
 * set X-Frame-Options: DENY or restrictive frame-ancestors.
 *
 * CSP directives are built from environment variables so they work across
 * Docker Compose, infra-core (Helm), and self-hosted (helm-charts) deployments.
 *
 * Environment variables:
 * - API_URL: Backend API URL (used in connect-src). Default: http://localhost:8001
 * - CSP_FRAME_ANCESTORS: Space-separated origins allowed to embed this widget.
 *   Default: * (all origins, since auth is session-token based, not origin based)
 * - CSP_ADDITIONAL_CONNECT_SRC: Space-separated extra origins for connect-src.
 */

// Build CSP directives once at startup (env vars don't change at runtime)
const apiUrl = process.env.API_URL || "http://localhost:8001";
const frameAncestors = process.env.CSP_FRAME_ANCESTORS || "*";
const additionalConnectSrc = process.env.CSP_ADDITIONAL_CONNECT_SRC || "";

const connectSrcParts = ["'self'", apiUrl];
if (additionalConnectSrc) {
  connectSrcParts.push(...additionalConnectSrc.split(" ").filter(Boolean));
}

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'`,
  `connect-src ${connectSrcParts.join(" ")}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self' data:",
  "base-uri 'self'",
  "form-action 'self'",
  `frame-ancestors ${frameAncestors}`,
].join("; ");

export default defineEventHandler((event) => {
  const headers = event.node.res;

  headers.setHeader("Content-Security-Policy", csp);

  // Do NOT set X-Frame-Options as it would conflict with frame-ancestors
  // and could prevent iframe embedding in some browsers

  // Other security headers
  headers.setHeader("X-Content-Type-Options", "nosniff");
  headers.setHeader("X-XSS-Protection", "1; mode=block");
  headers.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.setHeader(
    "Permissions-Policy",
    "geolocation=(), microphone=(), camera=()",
  );
});
