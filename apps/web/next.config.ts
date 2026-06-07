import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  eslint: {
    // We use a monorepo-shared eslint config
    ignoreDuringBuilds: false,
  },
  typescript: {
    // Type checking is done via turbo type-check
    ignoreBuildErrors: false,
  },
  transpilePackages: ["@mcpforge/eslint-config", "@mcpforge/tsconfig"],
};

export default nextConfig;
