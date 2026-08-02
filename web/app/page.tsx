import type { Metadata } from "next";
import PokerGame from "./PokerGame";

export const metadata: Metadata = {
  title: "金陵牌局 · 德州扑克",
  description: "一款拥有四种 AI 性格、随机发牌与细腻桌面动画的网页版德州扑克。",
};

export default function Home() {
  return <PokerGame />;
}
