export type Suit = "♠" | "♥" | "♣" | "♦";
export type Rank = "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "J" | "Q" | "K" | "A";
export type Card = { rank: Rank; suit: Suit };
export type Style = "tight" | "aggressive" | "balanced" | "loose";
export type Player = {
  id: number;
  name: string;
  stack: number;
  cards: Card[];
  folded: boolean;
  allIn: boolean;
  bet: number;
  lastAction: string;
  style: Style | "human";
};

const SUITS: Suit[] = ["♠", "♥", "♣", "♦"];
const RANKS: Rank[] = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];
const VALUE: Record<Rank, number> = Object.fromEntries(RANKS.map((r, i) => [r, i + 2])) as Record<Rank, number>;

export const PERSONALITIES: Record<Style, { label: string; motto: string; color: string }> = {
  tight: { label: "谨慎猎手", motto: "精选起手牌 · 小心追注", color: "#80aca0" },
  aggressive: { label: "强势施压", motto: "频繁加注 · 偶尔诈唬", color: "#d87661" },
  balanced: { label: "冷静计算", motto: "重视赔率 · 尺寸多变", color: "#d4ad5d" },
  loose: { label: "松凶玩家", motto: "爱看翻牌 · 敢追听牌", color: "#a68cc7" },
};

export function freshDeck(): Card[] {
  const deck = SUITS.flatMap((suit) => RANKS.map((rank) => ({ rank, suit })));
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
}

function fiveCardScore(cards: Card[]): number[] {
  const values = cards.map((c) => VALUE[c.rank]).sort((a, b) => b - a);
  const counts = new Map<number, number>();
  values.forEach((v) => counts.set(v, (counts.get(v) ?? 0) + 1));
  const groups = [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0]);
  const flush = cards.every((c) => c.suit === cards[0].suit);
  const unique = [...new Set(values)];
  if (unique[0] === 14) unique.push(1);
  let straight = 0;
  for (let i = 0; i <= unique.length - 5; i++) {
    if (unique[i] - unique[i + 4] === 4) { straight = unique[i]; break; }
  }
  if (flush && straight) return [8, straight];
  if (groups[0][1] === 4) return [7, groups[0][0], groups[1][0]];
  if (groups[0][1] === 3 && groups[1]?.[1] === 2) return [6, groups[0][0], groups[1][0]];
  if (flush) return [5, ...values];
  if (straight) return [4, straight];
  if (groups[0][1] === 3) return [3, groups[0][0], ...groups.slice(1).map((g) => g[0]).sort((a, b) => b - a)];
  if (groups[0][1] === 2 && groups[1]?.[1] === 2) {
    const pairs = [groups[0][0], groups[1][0]].sort((a, b) => b - a);
    return [2, ...pairs, groups.find((g) => g[1] === 1)?.[0] ?? 0];
  }
  if (groups[0][1] === 2) return [1, groups[0][0], ...groups.slice(1).map((g) => g[0]).sort((a, b) => b - a)];
  return [0, ...values];
}

export function handScore(cards: Card[]): number[] {
  let best: number[] = [];
  const compare = (a: number[], b: number[]) => {
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) - (b[i] ?? 0);
    }
    return 0;
  };
  for (let a = 0; a < cards.length - 4; a++)
    for (let b = a + 1; b < cards.length - 3; b++)
      for (let c = b + 1; c < cards.length - 2; c++)
        for (let d = c + 1; d < cards.length - 1; d++)
          for (let e = d + 1; e < cards.length; e++) {
            const score = fiveCardScore([cards[a], cards[b], cards[c], cards[d], cards[e]]);
            if (!best.length || compare(score, best) > 0) best = score;
          }
  return best;
}

export function handName(score: number[]) {
  return ["高牌", "一对", "两对", "三条", "顺子", "同花", "葫芦", "四条", "同花顺"][score[0] ?? 0];
}

export function preflopStrength(cards: Card[]) {
  if (cards.length < 2) return 0.35;
  const a = VALUE[cards[0].rank], b = VALUE[cards[1].rank];
  const high = Math.max(a, b), low = Math.min(a, b);
  let s = (high + low) / 32;
  if (a === b) s += 0.28 + high / 60;
  if (cards[0].suit === cards[1].suit) s += 0.07;
  if (Math.abs(a - b) <= 2) s += 0.07;
  if (high === 14) s += 0.08;
  return Math.min(1, s);
}

export function postflopStrength(cards: Card[], board: Card[]) {
  const score = handScore([...cards, ...board]);
  return Math.min(1, score[0] / 8 + (score[1] ?? 0) / 120 + Math.random() * 0.08);
}

export function aiDecision(style: Style, cards: Card[], board: Card[], toCall: number, pot: number, stack: number) {
  const base = board.length ? postflopStrength(cards, board) : preflopStrength(cards);
  const noise = (Math.random() - 0.5) * (style === "balanced" ? 0.12 : 0.2);
  const strength = base + noise;
  const pressure = toCall / Math.max(1, pot + toCall);
  const cfg = {
    tight: { fold: 0.25, raise: 0.78, bluff: 0.03 },
    aggressive: { fold: 0.10, raise: 0.55, bluff: 0.18 },
    balanced: { fold: 0.17, raise: 0.68, bluff: 0.08 },
    loose: { fold: 0.06, raise: 0.61, bluff: 0.13 },
  }[style];
  const foldThreshold = cfg.fold + pressure * 0.35;
  if (toCall > 0 && strength < foldThreshold && Math.random() > cfg.bluff) return { type: "fold" as const, amount: 0 };
  if ((strength > cfg.raise || Math.random() < cfg.bluff) && stack > toCall + 20) {
    const amount = Math.min(stack, toCall + Math.max(40, Math.round((pot * (0.35 + strength * 0.4)) / 10) * 10));
    return { type: "raise" as const, amount };
  }
  return { type: toCall ? "call" as const : "check" as const, amount: Math.min(stack, toCall) };
}
