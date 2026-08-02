import type { NextConfig } from "next";

const isGitHubPages = process.env.GITHUB_PAGES === "1";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath: isGitHubPages ? "/game_poker" : "",
  assetPrefix: isGitHubPages ? "/game_poker/" : "",
  images: { unoptimized: true },
};

export default nextConfig;
