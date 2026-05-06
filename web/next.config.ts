import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  images: {
    formats: ["image/webp"],
  },
  async rewrites() {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (!base) return [];
    return [{ source: "/api/:path*", destination: `${base}/api/:path*` }];
  },
};

export default config;
