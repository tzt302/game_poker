import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://tztgame.com/games/poker/"),
  title: {
    default: "德扑｜免费单机德州扑克 AI 游戏｜TZT GAME",
    template: "%s｜TZT GAME",
  },
  description: "免费在线单机德州扑克网页游戏，与四名 AI 对手完成翻牌前、翻牌、转牌和河牌对局，含牌力参考与下注历史。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "德扑｜免费单机德州扑克 AI 游戏",
    description: "与四名 AI 对手完成从翻牌前到河牌的完整德州扑克对局。",
    url: "https://tztgame.com/games/poker/",
    siteName: "TZT GAME",
    locale: "zh_CN",
    type: "website",
    images: ["https://tztgame.com/assets/poker-cartoon-v1.webp"],
  },
};

export const viewport: Viewport = { themeColor: "#20cec0" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN" suppressHydrationWarning><body suppressHydrationWarning>{children}<script defer src="/games/shared/game-i18n.js" data-game="poker" /></body></html>;
}
