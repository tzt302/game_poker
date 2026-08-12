export type Suit = "♠" | "♥" | "♣" | "♦";
export type Rank = "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "J" | "Q" | "K" | "A";
export type Card = { rank: Rank; suit: Suit };
export type Player = {
  id: number;
  name: string;
  stack: number;
  cards: Card[];
  folded: boolean;
  allIn: boolean;
  bet: number;
  lastAction: string;
};

const SUITS: Suit[] = ["♠", "♥", "♣", "♦"];
const RANKS: Rank[] = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];
const VALUE: Record<Rank, number> = Object.fromEntries(RANKS.map((r, i) => [r, i + 2])) as Record<Rank, number>;

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
  return Math.min(1, score[0] / 8 + (score[1] ?? 0) / 120);
}

function compareScores(a: number[], b: number[]) {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) - (b[i] ?? 0);
  }
  return 0;
}

function shuffledCopy(cards: Card[], random: () => number) {
  const copy = [...cards];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

export function estimateEquity(cards: Card[], board: Card[], opponents = 1, trials = 90, random = Math.random) {
  if (cards.length < 2) return 0;
  const known = new Set([...cards, ...board].map((card) => `${card.rank}${card.suit}`));
  const unseen = SUITS.flatMap((suit) => RANKS.map((rank) => ({ rank, suit }))).filter((card) => !known.has(`${card.rank}${card.suit}`));
  const opponentCount = Math.max(1, Math.min(4, opponents));
  let equity = 0;
  for (let trial = 0; trial < trials; trial++) {
    const deck = shuffledCopy(unseen, random);
    const fullBoard = [...board];
    while (fullBoard.length < 5) fullBoard.push(deck.pop()!);
    const ourScore = handScore([...cards, ...fullBoard]);
    let tied = 1;
    let beaten = false;
    for (let opponent = 0; opponent < opponentCount; opponent++) {
      const theirScore = handScore([deck.pop()!, deck.pop()!, ...fullBoard]);
      const result = compareScores(ourScore, theirScore);
      if (result < 0) { beaten = true; break; }
      if (result === 0) tied += 1;
    }
    if (!beaten) equity += 1 / tied;
  }
  return equity / trials;
}

export type AiDecisionOptions = {
  canRaise?: boolean;
  opponents?: number;
  position?: number;
  bigBlind?: number;
  betTo?: number;
  callers?: number;
  playersBehind?: number;
  isBigBlind?: boolean;
  isSmallBlind?: boolean;
  streetRaises?: number;
  random?: () => number;
};

function preflopTraits(cards: Card[]) {
  const first = VALUE[cards[0].rank];
  const second = VALUE[cards[1].rank];
  const high = Math.max(first, second);
  const low = Math.min(first, second);
  const gap = Math.abs(first - second);
  return {
    pair: first === second,
    suited: cards[0].suit === cards[1].suit,
    connected: gap <= 1,
    oneGap: gap === 2,
    broadway: high >= 11 && low >= 10,
    high,
    low,
  };
}

function logistic(value: number) {
  return 1 / (1 + Math.exp(-value));
}

export function aiDecision(cards: Card[], board: Card[], toCall: number, pot: number, stack: number, options: AiDecisionOptions | boolean = {}) {
  const config = typeof options === "boolean" ? { canRaise: options } : options;
  const canRaise = config.canRaise ?? true;
  const opponents = config.opponents ?? 1;
  const position = Math.max(0, Math.min(1, config.position ?? 0.5));
  const bigBlind = config.bigBlind ?? 20;
  const callers = Math.max(0, config.callers ?? 0);
  const playersBehind = Math.max(0, config.playersBehind ?? opponents - 1);
  const streetRaises = Math.max(0, config.streetRaises ?? 0);
  const random = config.random ?? Math.random;
  const potOdds = toCall / Math.max(1, pot + toCall);
  const stackPressure = toCall / Math.max(1, stack + toCall);
  const preflop = board.length === 0;
  const base = preflop ? preflopStrength(cards) : estimateEquity(cards, board, opponents, 90, random);
  const positionBonus = (position - 0.5) * 0.07;

  if (toCall > 0 && preflop) {
    const traits = preflopTraits(cards);
    const betTo = Math.max(toCall, config.betTo ?? toCall);
    const raiseSizeBb = betTo / Math.max(1, bigBlind);
    let continueThreshold = 0.51;
    continueThreshold += Math.min(0.2, Math.max(0, raiseSizeBb - 2.5) * 0.045);
    continueThreshold += Math.max(0, potOdds - 0.3) * 0.32;
    continueThreshold += stackPressure * 0.08;
    continueThreshold -= positionBonus;

    // Human-looking range adjustments: blinds defend their investment, pocket
    // pairs and suited connectors chase implied odds, and callers improve the
    // price for the players still in the hand.
    if (traits.pair) continueThreshold -= traits.high <= 8 ? 0.075 : 0.045;
    if (traits.suited && (traits.connected || traits.oneGap)) continueThreshold -= 0.065;
    else if (traits.suited) continueThreshold -= 0.025;
    if (traits.broadway) continueThreshold -= 0.035;
    if (config.isBigBlind) continueThreshold -= 0.075;
    else if (config.isSmallBlind) continueThreshold -= 0.025;
    continueThreshold -= Math.min(0.09, callers * 0.035);
    if (playersBehind === 0) continueThreshold -= 0.025;
    continueThreshold += Math.max(0, streetRaises - 1) * 0.055;

    const tableRead = (random() - 0.5) * 0.1;
    const continueChance = logistic((base + tableRead - continueThreshold) * 10.5);
    if (random() > continueChance) return { type: "fold" as const, amount: 0 };
  } else if (toCall > 0) {
    const postflopThreshold = potOdds + 0.025 + stackPressure * 0.08 - positionBonus;
    const continueChance = logistic((base - postflopThreshold) * 13 + (random() - 0.5) * 0.8);
    if (random() > continueChance) return { type: "fold" as const, amount: 0 };
  }

  const premium = preflop ? base > 0.84 : base > Math.max(0.64, potOdds + 0.3);
  const strongButTrappy = premium && random() < 0.2;
  const valueRaiseChance = preflop ? 0.27 + Math.max(0, base - 0.84) * 1.5 : 0.3 + Math.max(0, base - 0.64);
  const valueRaise = premium && !strongButTrappy && random() < Math.min(0.7, valueRaiseChance);
  const bluffRaise = !premium && position > 0.58 && callers === 0 && streetRaises <= 1 && toCall <= Math.max(bigBlind * 3, pot * 0.35) && random() < 0.045;
  if (canRaise && (valueRaise || bluffRaise) && stack > toCall + bigBlind) {
    const raiseSize = Math.max(bigBlind * 2.5, Math.round((pot * (0.52 + random() * 0.3)) / 10) * 10);
    return { type: "raise" as const, amount: Math.min(stack, toCall + raiseSize) };
  }
  return { type: toCall ? "call" as const : "check" as const, amount: Math.min(stack, toCall) };
}
