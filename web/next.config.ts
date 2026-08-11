import type { NextConfig } from "next";

const isGitHubPages = process.env.GITHUB_PAGES === "1";
const isGameHub = process.env.GAME_HUB === "1";
const basePath = isGitHubPages
  ? "/game_poker"
  : isGameHub
    ? "/games/poker"
    : "";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  assetPrefix: basePath ? `${basePath}/` : "",
  images: { unoptimized: true },
};

export default nextConfig;
