import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Korean Social Simulation",
  description: "한국 인구 페르소나에게 시나리오를 묻고 반응을 모은다.",
  icons: { icon: "/illustrations/favicon.png" },
};

export const viewport: Viewport = { themeColor: "#0a0a0c" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="min-h-dvh antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
