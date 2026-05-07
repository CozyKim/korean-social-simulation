import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  images: {
    formats: ["image/webp"],
  },
  async rewrites() {
    // Production: Vercel ↔ Fly 가 별개 도메인이라 백엔드의 Set-Cookie 가 Fly origin
    // 에 저장되면 Vercel SSR 의 cookies() 가 못 읽는다 (cross-origin). 모든 /api/*
    // 호출을 Vercel server 로 보내고 여기서 rewrites 가 Fly 백엔드로 forward 하면
    // Set-Cookie 응답이 Vercel proxy 를 거치므로 쿠키가 Vercel origin 에 저장됨.
    //
    // 이 때 클라이언트는 NEXT_PUBLIC_API_BASE_URL="" (상대 경로) 로 두고,
    // 서버 전용 변수 API_BASE_URL=https://kss-api.fly.dev 를 통해 forwarding.
    // dev 에서는 NEXT_PUBLIC_API_BASE_URL 이 그대로 채워져 있어도 무방.
    const base = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
    if (!base) return [];
    return [{ source: "/api/:path*", destination: `${base}/api/:path*` }];
  },
};

export default config;
