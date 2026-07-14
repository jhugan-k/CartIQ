import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Pin the workspace root so Next doesn't pick up a stray lockfile elsewhere.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
