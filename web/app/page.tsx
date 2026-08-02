import type { Metadata } from "next";
import PokerGame from "./PokerGame";

export const metadata: Metadata = {
  title: "德州扑克",
  description: "随机发牌，与四种性格的 AI 对战。",
};

export default function Home() {
  return <PokerGame />;
}
