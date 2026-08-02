import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://tzt302.github.io/game_poker/"),
  title: "金陵牌局 · 德州扑克",
  description: "高清 2.5D 网页德州扑克，随机发牌并与四种性格的 AI 对战。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "金陵牌局 · 德州扑克",
    description: "随机发牌，与四种性格的 AI 来一局。",
    images: [{ url: "/game_poker/og-cover.png", width: 1734, height: 912 }],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
