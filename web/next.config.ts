import type { NextConfig } from "next";

/**
 * Where the browser-facing /api/* proxy points.
 *
 * Next.js compiles rewrites into routes-manifest.json at **build** time, so
 * this must be set when the image is built -- reading it at request time does
 * not work. The Dockerfile takes it as a build arg defaulting to the compose
 * service name; `npm run dev` uses the localhost default.
 *
 * In the production stack this is moot: Caddy routes /api/* straight to the API
 * container, so the request never reaches Next.js. It matters for local
 * development and for running the web image on its own.
 */
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Keeps the session cookie same-origin, so there is no CORS credentials
  // handling anywhere in the app.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  output: "standalone",
};

export default nextConfig;
