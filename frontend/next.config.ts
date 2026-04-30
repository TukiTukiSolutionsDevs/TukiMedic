import type { NextConfig } from "next";

/**
 * Security headers applied to every response.
 *
 * Notes:
 * - CSP is intentionally pragmatic ('self' + necessary externals) so it is
 *   safe to enable in production without breaking the chat WebSocket. Tighten
 *   per route as the app evolves.
 * - HSTS is only emitted in production builds — locally it would brick HTTP.
 * - The connect-src directive must allow the API + WS endpoints (configured
 *   via NEXT_PUBLIC_API_URL / NEXT_PUBLIC_WS_URL).
 */
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // Next dev needs eval; tighten in prod build
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiUrl} ${wsUrl}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
];

if (process.env.NODE_ENV === "production") {
  securityHeaders.push({
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  });
}

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
