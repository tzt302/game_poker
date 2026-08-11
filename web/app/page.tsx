import type { Metadata } from "next";
import PokerGame from "./PokerGame";

export const metadata: Metadata = {
  title: "德扑｜免费单机德州扑克 AI 游戏",
  description: "免费在线单机德州扑克网页游戏，与四名 AI 对手完成翻牌前、翻牌、转牌和河牌对局，含牌力参考与下注历史。",
  keywords: "德州扑克,在线扑克,AI德州扑克,网页扑克,德州扑克游戏,免费扑克,Texas Holdem,poker online,free poker game,AI poker,web poker游戏",
  openGraph: {
    title: "德扑｜免费单机德州扑克 AI 游戏",
    description: "与四名 AI 对手完成从翻牌前到河牌的完整德州扑克对局。浏览器即玩。",
    url: "https://tztgame.com/games/poker/",
    siteName: "TZT GAME",
    locale: "zh_CN",
    type: "website",
    images: ["https://tztgame.com/assets/poker-cartoon-v1.webp"],
  },
  twitter: {
    card: "summary_large_image",
    title: "德扑｜免费单机德州扑克 AI 游戏",
    description: "四名 AI 对手，完整德州扑克对局。浏览器即玩。",
    images: ["https://tztgame.com/assets/poker-cartoon-v1.webp"],
  },
};

export default function Home() {
  return <PokerGame />;
}
