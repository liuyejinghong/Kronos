import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const apiBase = process.env.KRONOS_API_PROXY_TARGET ?? "http://127.0.0.1:8000";
const rootDir = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: rootDir,
  },
  async rewrites() {
    return [
      {
        source: "/api/kronos/:path*",
        destination: `${apiBase}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
