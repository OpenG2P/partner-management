import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output so the Docker runner ships a minimal server bundle.
  output: "standalone",
};

export default nextConfig;
