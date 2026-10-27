import path from "node:path";

import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8100";

const nextConfig: NextConfig = {
  output: "standalone",
  // The repo root has its own package.json (Neon config); this app is self-contained.
  outputFileTracingRoot: path.join(__dirname),
  // Compression buffers responses, which would hold back streamed chat answers.
  compress: false,
  // The browser talks to the API through this origin, so the session cookie is first-party
  // and httpOnly, and no CORS is needed.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
