import path from "node:path";
import type { NextConfig } from "next";

// Anchor the board's JSON store to this project, not the directory the
// server happened to be launched from. Set BOARD_DATA_DIR to override.
process.env.BOARD_DATA_DIR ??= path.join(import.meta.dirname, "data");

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
