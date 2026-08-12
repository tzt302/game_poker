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

function simulateFourWayResponse(betTo, hands = 1800, seed = 302) {
  const ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];
  const suits = ["♠", "♥", "♦", "♣"];
  const sourceDeck = suits.flatMap((suit) => ranks.map((rank) => ({ rank, suit })));
  const random = seededRandom(seed);
  let allFold = 0;
  let totalContinuers = 0;
  for (let hand = 0; hand < hands; hand++) {
    const deck = [...sourceDeck];
    for (let index = deck.length - 1; index > 0; index--) {
      const swap = Math.floor(random() * (index + 1));
      [deck[index], deck[swap]] = [deck[swap], deck[index]];
    }
    let pot = betTo + 30;
    let callers = 0;
    let continuers = 0;
    for (let player = 0; player < 4; player++) {
      const invested = player === 2 ? 10 : player === 3 ? 20 : 0;
      const toCall = betTo - invested;
      const decision = aiDecision([deck.pop(), deck.pop()], [], toCall, pot, 1000 - invested, {
        canRaise: false,
        opponents: 4 - callers,
        position: player / 3,
        bigBlind: 20,
        betTo,
        callers,
        playersBehind: 3 - player,
        isSmallBlind: player === 2,
        isBigBlind: player === 3,
        streetRaises: 1,
        random,
      });
      if (decision.type !== "fold") {
        continuers += 1;
        callers += 1;
        pot += decision.amount;
      }
    }
    totalContinuers += continuers;
    allFold += Number(continuers === 0);
  }
  return { allFoldRate: allFold / hands, averageContinuers: totalContinuers / hands };
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

test("a standard four-big-blind raise usually gets a human-like defence", () => {
  const result = simulateFourWayResponse(80);
  assert.ok(result.allFoldRate > 0.015 && result.allFoldRate < 0.14, `all-fold rate was ${result.allFoldRate}`);
  assert.ok(result.averageContinuers > 0.85 && result.averageContinuers < 2.3, `average continuers was ${result.averageContinuers}`);
});

test("an oversized raise earns substantially more folds than a normal raise", () => {
  const normal = simulateFourWayResponse(80, 1600, 91);
  const oversized = simulateFourWayResponse(240, 1600, 91);
  assert.ok(oversized.allFoldRate > normal.allFoldRate + 0.12, `normal=${normal.allFoldRate}, oversized=${oversized.allFoldRate}`);
  assert.ok(oversized.averageContinuers < normal.averageContinuers - 0.35, `normal=${normal.averageContinuers}, oversized=${oversized.averageContinuers}`);
});
