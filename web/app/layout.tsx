import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://tzt302.github.io/game_poker/"),
  title: "德州扑克",
  description: "随机发牌，与四名 AI 对战。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "德州扑克",
    description: "随机发牌，与四名 AI 来一局。",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
