"""Rules engine for a single-table no-limit Texas Hold'em game."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
import random
from typing import Iterable


RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_VALUE = {rank: value for value, rank in enumerate(RANKS, start=2)}

STYLE_PROFILES = {
    "tight": {
        "label": "谨慎猎手", "tagline": "精选起手牌 · 小心追注",
        "fold_floor": 0.28, "raise_line": 0.73, "bluff": 0.02,
        "call_bonus": 0.00, "bet_low": 0.38, "bet_high": 0.62,
    },
    "aggressive": {
        "label": "强势施压", "tagline": "频繁加注 · 偶尔诈唬",
        "fold_floor": 0.16, "raise_line": 0.49, "bluff": 0.16,
        "call_bonus": 0.08, "bet_low": 0.68, "bet_high": 1.08,
    },
    "balanced": {
        "label": "冷静计算", "tagline": "重视赔率 · 尺寸多变",
        "fold_floor": 0.22, "raise_line": 0.61, "bluff": 0.06,
        "call_bonus": 0.04, "bet_low": 0.48, "bet_high": 0.78,
    },
    "loose": {
        "label": "松凶玩家", "tagline": "爱看翻牌 · 敢追听牌",
        "fold_floor": 0.12, "raise_line": 0.63, "bluff": 0.10,
        "call_bonus": 0.14, "bet_low": 0.52, "bet_high": 0.86,
    },
}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        return RANK_VALUE[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


@dataclass(frozen=True, order=True)
class HandRank:
    category: int
    kickers: tuple[int, ...]

    @property
    def name(self) -> str:
        return (
            "高牌", "一对", "两对", "三条", "顺子",
            "同花", "葫芦", "四条", "同花顺",
        )[self.category]


def evaluate_five(cards: Iterable[Card]) -> HandRank:
    hand = list(cards)
    values = sorted((card.value for card in hand), reverse=True)
    counts = {value: values.count(value) for value in set(values)}
    groups = sorted(((count, value) for value, count in counts.items()), reverse=True)
    flush = len({card.suit for card in hand}) == 1
    unique = sorted(set(values), reverse=True)
    if 14 in unique:
        unique.append(1)
    straight_high = 0
    for i in range(len(unique) - 4):
        window = unique[i : i + 5]
        if window[0] - window[4] == 4:
            straight_high = window[0]
            break
    if flush and straight_high:
        return HandRank(8, (straight_high,))
    if groups[0][0] == 4:
        four = groups[0][1]
        return HandRank(7, (four, max(value for value in values if value != four)))
    if groups[0][0] == 3 and groups[1][0] == 2:
        return HandRank(6, (groups[0][1], groups[1][1]))
    if flush:
        return HandRank(5, tuple(values))
    if straight_high:
        return HandRank(4, (straight_high,))
    if groups[0][0] == 3:
        trip = groups[0][1]
        rest = sorted((value for value in values if value != trip), reverse=True)[:2]
        return HandRank(3, (trip, *rest))
    pairs = sorted((value for value, count in counts.items() if count == 2), reverse=True)
    if len(pairs) >= 2:
        kicker = max(value for value in values if value not in pairs[:2])
        return HandRank(2, (pairs[0], pairs[1], kicker))
    if pairs:
        pair = pairs[0]
        rest = sorted((value for value in values if value != pair), reverse=True)[:3]
        return HandRank(1, (pair, *rest))
    return HandRank(0, tuple(values))


def evaluate_seven(cards: Iterable[Card]) -> HandRank:
    cards = list(cards)
    if len(cards) < 5:
        raise ValueError("At least five cards are required")
    return max(evaluate_five(combo) for combo in combinations(cards, 5))


class Stage(str, Enum):
    PREFLOP = "翻牌前"
    FLOP = "翻牌"
    TURN = "转牌"
    RIVER = "河牌"
    SHOWDOWN = "摊牌"


@dataclass
class Player:
    name: str
    is_human: bool = False
    style: str = "balanced"
    stack: int = 1000
    cards: list[Card] = field(default_factory=list)
    street_bet: int = 0
    committed: int = 0
    folded: bool = False
    all_in: bool = False
    last_action: str = ""

    @property
    def active(self) -> bool:
        return not self.folded and bool(self.cards)


class HoldemGame:
    """Five-seat cash game with blinds, betting streets and basic bot players."""

    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.players = [
            Player("你", True, "human"),
            Player("Luna", style="tight"),
            Player("Max", style="aggressive"),
            Player("Ivy", style="balanced"),
            Player("Kai", style="loose"),
        ]
        self.small_blind = 10
        self.big_blind = 20
        self.dealer = -1
        self.hand_number = 0
        self.community: list[Card] = []
        self.deck: list[Card] = []
        self.stage = Stage.PREFLOP
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.actor: int | None = None
        self.acted: set[int] = set()
        self.message = ""
        self.winners: list[int] = []
        self.hand_over = True
        self.last_pot = 0
        self.last_decision_note: dict[int, str] = {}
        self.start_hand()

    @property
    def pot(self) -> int:
        return sum(player.committed for player in self.players)

    @property
    def human_turn(self) -> bool:
        return self.actor == 0 and not self.hand_over

    def _next_live(self, start: int, can_act: bool = False) -> int | None:
        for offset in range(1, len(self.players) + 1):
            idx = (start + offset) % len(self.players)
            player = self.players[idx]
            if player.active and (not can_act or not player.all_in):
                return idx
        return None

    def start_hand(self) -> None:
        # Rebuy busted seats so every deal remains lively.
        for player in self.players:
            if player.stack < self.big_blind:
                player.stack = 1000
        self.hand_number += 1
        self.dealer = self._next_seated(self.dealer)
        self.deck = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        self.rng.shuffle(self.deck)
        self.community = []
        self.stage = Stage.PREFLOP
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.acted.clear()
        self.winners = []
        self.hand_over = False
        self.last_pot = 0
        self.last_decision_note.clear()
        for player in self.players:
            player.cards = [self.deck.pop(), self.deck.pop()]
            player.street_bet = 0
            player.committed = 0
            player.folded = False
            player.all_in = False
            player.last_action = ""
        sb = self._next_live(self.dealer)
        bb = self._next_live(sb if sb is not None else self.dealer)
        assert sb is not None and bb is not None
        self._put_chips(sb, self.small_blind)
        self.players[sb].last_action = "小盲"
        self._put_chips(bb, self.big_blind)
        self.players[bb].last_action = "大盲"
        self.current_bet = self.players[bb].street_bet
        self.actor = self._next_live(bb, can_act=True)
        self.message = f"第 {self.hand_number} 手牌 · 盲注 {self.small_blind}/{self.big_blind}"

    def _next_seated(self, start: int) -> int:
        return (start + 1) % len(self.players)

    def _put_chips(self, idx: int, amount: int) -> int:
        player = self.players[idx]
        paid = min(max(0, amount), player.stack)
        player.stack -= paid
        player.street_bet += paid
        player.committed += paid
        if player.stack == 0:
            player.all_in = True
        return paid

    def legal_actions(self, idx: int = 0) -> dict[str, int | bool]:
        player = self.players[idx]
        to_call = max(0, self.current_bet - player.street_bet)
        min_total = self.current_bet + self.min_raise
        has_responder = any(
            other != idx and candidate.active and not candidate.all_in and candidate.stack > 0
            for other, candidate in enumerate(self.players)
        )
        return {
            "to_call": min(to_call, player.stack),
            "can_check": to_call == 0,
            "can_raise": (
                has_responder
                and player.stack > to_call
                and player.street_bet + player.stack >= min_total
            ),
            "min_raise_to": min_total,
            "max_raise_to": player.street_bet + player.stack,
        }

    def act(self, idx: int, action: str, amount: int = 0) -> None:
        if self.hand_over or idx != self.actor:
            return
        player = self.players[idx]
        legal = self.legal_actions(idx)
        to_call = int(legal["to_call"])
        if action == "fold":
            player.folded = True
            player.last_action = "弃牌"
            self.acted.add(idx)
        elif action == "check" and to_call == 0:
            player.last_action = "过牌"
            self.acted.add(idx)
        elif action == "call":
            paid = self._put_chips(idx, to_call)
            player.last_action = "全下" if player.all_in else ("过牌" if paid == 0 else f"跟注 {paid}")
            self.acted.add(idx)
        elif action in ("raise", "allin"):
            target = player.street_bet + player.stack if action == "allin" else amount
            target = min(target, player.street_bet + player.stack)
            if target <= self.current_bet:
                self.act(idx, "call")
                return
            old_bet = self.current_bet
            paid = self._put_chips(idx, target - player.street_bet)
            new_total = player.street_bet
            self.min_raise = max(self.big_blind, new_total - old_bet)
            self.current_bet = new_total
            self.acted = {idx}
            player.last_action = "全下" if player.all_in else f"加注到 {new_total}"
        else:
            return
        self._after_action(idx)

    def _after_action(self, idx: int) -> None:
        live = [i for i, p in enumerate(self.players) if p.active]
        if len(live) == 1:
            self._award_uncontested(live[0])
            return
        able = [i for i in live if not self.players[i].all_in]
        settled = all(
            i in self.acted and self.players[i].street_bet == self.current_bet
            for i in able
        )
        if settled or not able:
            self._advance_stage()
            return
        self.actor = self._next_live(idx, can_act=True)

    def _advance_stage(self) -> None:
        for player in self.players:
            player.street_bet = 0
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.acted.clear()
        if self.stage == Stage.PREFLOP:
            self.deck.pop()  # burn
            self.community.extend([self.deck.pop(), self.deck.pop(), self.deck.pop()])
            self.stage = Stage.FLOP
        elif self.stage == Stage.FLOP:
            self.deck.pop()
            self.community.append(self.deck.pop())
            self.stage = Stage.TURN
        elif self.stage == Stage.TURN:
            self.deck.pop()
            self.community.append(self.deck.pop())
            self.stage = Stage.RIVER
        else:
            self._showdown()
            return
        able = [i for i, p in enumerate(self.players) if p.active and not p.all_in]
        if len(able) <= 1:
            self._run_out_board()
            return
        self.actor = self._next_live(self.dealer, can_act=True)
        self.message = self.stage.value

    def _run_out_board(self) -> None:
        while len(self.community) < 5:
            self.deck.pop()
            count = 3 if not self.community else 1
            self.community.extend(self.deck.pop() for _ in range(count))
        self.stage = Stage.RIVER
        self._showdown()

    def _showdown(self) -> None:
        self.stage = Stage.SHOWDOWN
        live = [i for i, p in enumerate(self.players) if p.active]
        ranks = {i: evaluate_seven(self.players[i].cards + self.community) for i in live}
        best = max(ranks.values())
        winners = [i for i, rank in ranks.items() if rank == best]
        self._pay_side_pots(ranks)
        self.winners = winners
        names = "、".join(self.players[i].name for i in winners)
        self.message = f"{names} 以{best.name}获胜"
        self.actor = None
        self.hand_over = True

    def _pay_side_pots(self, ranks: dict[int, HandRank]) -> None:
        self.last_pot = self.pot
        levels = sorted({p.committed for p in self.players if p.committed > 0})
        previous = 0
        for level in levels:
            contributors = [i for i, p in enumerate(self.players) if p.committed >= level]
            amount = (level - previous) * len(contributors)
            eligible = [i for i in contributors if i in ranks]
            if eligible:
                best = max(ranks[i] for i in eligible)
                winners = [i for i in eligible if ranks[i] == best]
                share, remainder = divmod(amount, len(winners))
                for order, idx in enumerate(winners):
                    self.players[idx].stack += share + (1 if order < remainder else 0)
            previous = level

    def _award_uncontested(self, idx: int) -> None:
        amount = self.pot
        self.players[idx].stack += amount
        self.last_pot = amount
        self.winners = [idx]
        self.message = f"{self.players[idx].name} 赢得底池 {amount}"
        self.actor = None
        self.hand_over = True

    def bot_action(self, idx: int) -> tuple[str, int]:
        """Choose a visibly personality-driven action without over-folding preflop."""
        player = self.players[idx]
        legal = self.legal_actions(idx)
        to_call = int(legal["to_call"])
        profile = STYLE_PROFILES[player.style]
        preflop = self.stage == Stage.PREFLOP
        strength = self._preflop_strength(player.cards) if preflop else self._estimate_strength(idx, 110)
        noise = self.rng.uniform(-0.055, 0.055)
        pot_odds = to_call / max(1, self.pot + to_call)

        # Cheap preflop calls are intentionally sticky. A large raise still creates
        # real fold equity, while an unopened pot no longer loses half the table.
        if preflop:
            extra_blinds = max(0.0, to_call / self.big_blind - 1.0)
            fold_line = float(profile["fold_floor"]) + min(0.34, extra_blinds * 0.075)
        else:
            fold_line = max(0.055, pot_odds * 0.62 - float(profile["call_bonus"]))
        if to_call and strength + noise < fold_line:
            self.last_decision_note[idx] = "牌力不足，面对压力选择止损"
            return "fold", 0

        bluffing = self.rng.random() < float(profile["bluff"]) and to_call <= max(self.big_blind, self.pot // 3)
        raise_line = float(profile["raise_line"]) + (0.04 if preflop else 0.0)
        if bool(legal["can_raise"]) and (strength + noise > raise_line or bluffing):
            low = int(legal["min_raise_to"])
            high = int(legal["max_raise_to"])
            fraction = self.rng.uniform(float(profile["bet_low"]), float(profile["bet_high"]))
            target = min(high, max(low, self.current_bet + int(self.pot * fraction)))
            target = max(low, (target // self.small_blind) * self.small_blind)
            if target >= high and strength > 0.86:
                self.last_decision_note[idx] = "拿到顶级牌力，直接推入全部筹码"
                return "allin", high
            self.last_decision_note[idx] = "主动施压" if bluffing else "牌力领先，扩大底池"
            return "raise", target

        if bool(legal["can_check"]):
            self.last_decision_note[idx] = "控制底池，免费看下一张牌"
            return "check", 0
        self.last_decision_note[idx] = "赔率合适，继续看牌"
        return "call", 0

    def _preflop_strength(self, cards: list[Card]) -> float:
        """Human-readable 0..1 starting-hand score used by preflop bots."""
        first, second = cards
        high, low = sorted((first.value, second.value), reverse=True)
        if high == low:
            return min(1.0, 0.50 + high / 28.0)
        score = (high + low) / 34.0
        if first.suit == second.suit:
            score += 0.075
        gap = high - low
        if gap == 1:
            score += 0.075
        elif gap == 2:
            score += 0.035
        elif gap >= 5:
            score -= 0.09
        if high == 14:
            score += 0.08
        if low >= 10:
            score += 0.06
        return max(0.0, min(1.0, score))

    def _estimate_strength(self, idx: int, samples: int) -> float:
        hero = self.players[idx].cards
        opponents = max(1, sum(p.active for p in self.players) - 1)
        known = set(hero + self.community)
        pool = [Card(rank, suit) for suit in SUITS for rank in RANKS if Card(rank, suit) not in known]
        wins = 0.0
        for _ in range(samples):
            self.rng.shuffle(pool)
            board = self.community + pool[: 5 - len(self.community)]
            hero_rank = evaluate_seven(hero + board)
            cursor = 5 - len(self.community)
            enemy_ranks = []
            for _enemy in range(opponents):
                enemy = pool[cursor : cursor + 2]
                cursor += 2
                enemy_ranks.append(evaluate_seven(enemy + board))
            best_enemy = max(enemy_ranks)
            if hero_rank > best_enemy:
                wins += 1
            elif hero_rank == best_enemy:
                wins += 0.5
        return wins / samples
