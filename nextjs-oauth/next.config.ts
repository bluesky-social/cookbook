import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["better-sqlite3"],
  allowedDevOrigins: ["127.0.0.1"],
  turbopack: {
    // Pin the workspace root to this app so Next doesn't infer it from a
    // lockfile in a parent directory.
    root: __dirname,
  },
};

export default nextConfig;
