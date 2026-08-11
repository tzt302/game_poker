import assert from "node:assert/strict";
import test from "node:test";

import { aiDecision, estimateEquity } from "../app/poker.ts";

const cards = (text) => text.split(" ").map((token) => ({ rank: token.slice(0, -1), suit: token.slice(-1) }));

function seededRandom(seed = 1) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

test("a normal preflop raise keeps a realistic portion of hands in play", () => {
  const ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];
  const suits = ["♠", "♥", "♦", "♣"];
  const deck = suits.flatMap((suit) => ranks.map((rank) => ({ rank, suit })));
  const random = seededRandom(302);
  let folds = 0;
  let total = 0;
  for (let first = 0; first < deck.length; first++) {
    for (let second = first + 1; second < deck.length; second++) {
      const decision = aiDecision([deck[first], deck[second]], [], 60, 140, 940, { canRaise: false, opponents: 4, position: 0.5, random });
      folds += Number(decision.type === "fold");
      total += 1;
    }
  }
  const foldRate = folds / total;
  assert.ok(foldRate > 0.25 && foldRate < 0.7, `unexpected fold rate: ${foldRate}`);
  assert.ok(foldRate ** 4 < 0.25, `four-way fold frequency is still too high: ${foldRate ** 4}`);
});

test("postflop equity recognizes a strong made hand", () => {
  const equity = estimateEquity(cards("A♠ A♥"), cards("A♦ 7♣ 2♠"), 3, 160, seededRandom(19));
  assert.ok(equity > 0.75, `set equity was only ${equity}`);
});

test("large pressure still folds a genuinely weak hand", () => {
  const decision = aiDecision(cards("7♣ 2♦"), [], 240, 120, 760, { canRaise: false, opponents: 4, position: 0, random: seededRandom(7) });
  assert.equal(decision.type, "fold");
});
