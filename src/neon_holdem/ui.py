"""2.5D animated table interface for Neon Hold'em."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
import time

import pygame

from .engine import Card, HoldemGame, STYLE_PROFILES, Stage, evaluate_seven


W, H = 1280, 760
TABLE_RIGHT = 1008
DECK_POS = (520, 210)
POT_POS = (520, 372)
SUIT_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RED_SUITS = {"h", "d"}


@dataclass
class Motion:
    kind: str
    start: tuple[float, float]
    end: tuple[float, float]
    started: float
    duration: float
    delay: float = 0.0
    card: Card | None = None
    back: bool = True
    flip: bool = False
    size: tuple[int, int] = (58, 82)
    rotation: float = 0.0
    amount: int = 0
    reveal: tuple[str, int, int] | None = None

    def progress(self, now: float) -> float:
        return max(0.0, min(1.0, (now - self.started - self.delay) / self.duration))

    def complete(self, now: float) -> bool:
        return now >= self.started + self.delay + self.duration


@dataclass
class LogEntry:
    name: str
    action: str
    accent: tuple[int, int, int]
    hand: int
    detail: str = ""


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str, accent):
        self.rect = rect
        self.label = label
        self.action = action
        self.accent = accent
        self.enabled = True

    def draw(self, surface, font, mouse):
        hover = self.enabled and self.rect.collidepoint(mouse)
        fill = self.accent if hover else tuple(max(0, c - 28) for c in self.accent)
        if not self.enabled:
            fill = (37, 48, 53)
        pygame.draw.rect(surface, (0, 4, 7), self.rect.move(0, 7), border_radius=13)
        pygame.draw.rect(surface, tuple(max(0, c - 65) for c in fill), self.rect.move(0, 4), border_radius=13)
        pygame.draw.rect(surface, fill, self.rect, border_radius=13)
        pygame.draw.line(surface, (255, 245, 194), (self.rect.x + 13, self.rect.y + 2),
                         (self.rect.right - 13, self.rect.y + 2), 2)
        pygame.draw.line(surface, tuple(max(0, c - 80) for c in fill),
                         (self.rect.x + 10, self.rect.bottom - 2), (self.rect.right - 10, self.rect.bottom - 2), 2)
        color = (5, 19, 22) if self.enabled else (102, 116, 119)
        label = font.render(self.label, True, color)
        surface.blit(label, label.get_rect(center=self.rect.center))


class PokerApp:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.game = HoldemGame()
        self.running = True
        self.fonts = self._load_fonts()
        self.seats = [(520, 548), (142, 430), (260, 176), (780, 176), (900, 430)]
        self.seat_accents = [(247, 194, 67), (61, 197, 239), (242, 99, 112),
                             (177, 112, 247), (64, 214, 159)]
        self.buttons = [
            Button(pygame.Rect(24, 697, 108, 43), "弃牌", "fold", (231, 81, 92)),
            Button(pygame.Rect(143, 697, 114, 43), "过牌", "check", (72, 142, 181)),
            Button(pygame.Rect(268, 697, 128, 43), "跟注", "call", (48, 204, 152)),
            Button(pygame.Rect(407, 697, 130, 43), "加注", "raise", (240, 183, 63)),
        ]
        self.preset_buttons = [
            (pygame.Rect(558, 656, 67, 29), "最小", "min"),
            (pygame.Rect(632, 656, 67, 29), "半池", "half"),
            (pygame.Rect(706, 656, 67, 29), "3/4池", "three_quarter"),
            (pygame.Rect(780, 656, 67, 29), "满池", "pot"),
            (pygame.Rect(854, 656, 67, 29), "全下", "allin"),
            (pygame.Rect(928, 656, 62, 29), "+10", "plus"),
        ]
        self.raise_to = 60
        self.show_help = False
        self.motions: list[Motion] = []
        self.revealed_hole: set[tuple[int, int]] = set()
        self.revealed_community = 0
        self.bubbles: dict[int, tuple[str, float, tuple[int, int, int]]] = {}
        self.logs: list[LogEntry] = []
        self.particles: list[dict] = []
        self.bot_due = float("inf")
        self.thinking_started = time.monotonic()
        self.observed_actor = self.game.actor
        self.hand_over_at = 0.0
        self.last_stage = self.game.stage
        self.stage_banner = ""
        self.stage_banner_until = 0.0
        self._begin_hand_animation(initial=True)

    def _load_fonts(self):
        candidates = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"]
        display_candidates = ["Bahnschrift SemiBold", "Bahnschrift", "Arial Black"]
        name = next((font for font in candidates if pygame.font.match_font(font)), None)
        display = next((font for font in display_candidates if pygame.font.match_font(font)), name)
        return {
            "tiny": pygame.font.SysFont(name, 12),
            "xs": pygame.font.SysFont(name, 14),
            "sm": pygame.font.SysFont(name, 16),
            "md": pygame.font.SysFont(name, 19, bold=True),
            "lg": pygame.font.SysFont(name, 26, bold=True),
            "xl": pygame.font.SysFont(name, 36, bold=True),
            "title": pygame.font.SysFont(display, 28, bold=True),
            "number": pygame.font.SysFont(display, 21, bold=True),
            "suit": pygame.font.SysFont("Segoe UI Symbol", 36),
        }

    @property
    def animation_locked(self) -> bool:
        return bool(self.motions)

    @property
    def can_human_act(self) -> bool:
        return self.game.human_turn and not self.animation_locked

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self._events()
            self._update(dt)
            self._draw()

    def _mouse_canvas(self):
        sw, sh = self.screen.get_size()
        scale = min(sw / W, sh / H)
        ox, oy = (sw - W * scale) / 2, (sh - H * scale) / 2
        mx, my = pygame.mouse.get_pos()
        return int((mx - ox) / scale), int((my - oy) / scale)

    def _events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.show_help:
                        self.show_help = False
                    else:
                        self.running = False
                elif event.key == pygame.K_h:
                    self.show_help = not self.show_help
                elif event.key == pygame.K_n and self.game.hand_over:
                    self._new_hand()
                elif self.can_human_act:
                    if event.key == pygame.K_f:
                        self._perform_action(0, "fold")
                    elif event.key in (pygame.K_c, pygame.K_SPACE):
                        legal = self.game.legal_actions()
                        self._perform_action(0, "check" if legal["can_check"] else "call")
                    elif event.key in (pygame.K_r, pygame.K_RETURN):
                        self._perform_action(0, "raise", self.raise_to)
                    elif event.key in (pygame.K_LEFT, pygame.K_DOWN):
                        self._adjust_raise(-10)
                    elif event.key in (pygame.K_RIGHT, pygame.K_UP):
                        self._adjust_raise(10)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._click(self._mouse_canvas())
            elif event.type == pygame.MOUSEWHEEL and self.can_human_act:
                self._adjust_raise(event.y * 10)

    def _click(self, pos):
        if self.show_help:
            self.show_help = False
            return
        if pygame.Rect(864, 22, 62, 38).collidepoint(pos):
            self._new_hand()
            return
        if pygame.Rect(934, 22, 58, 38).collidepoint(pos):
            self.show_help = True
            return
        if self.game.hand_over and pygame.Rect(405, 687, 230, 52).collidepoint(pos):
            self._new_hand()
            return
        for rect, _label, preset in self.preset_buttons:
            if self.can_human_act and rect.collidepoint(pos):
                self._set_raise_preset(preset)
                return
        slider = pygame.Rect(565, 716, 420, 12)
        if self.can_human_act and slider.inflate(0, 28).collidepoint(pos):
            legal = self.game.legal_actions()
            low, high = int(legal["min_raise_to"]), int(legal["max_raise_to"])
            ratio = max(0.0, min(1.0, (pos[0] - slider.x) / slider.width))
            # Quadratic response gives most of the track to useful small/medium bets.
            self.raise_to = self._clamp_raise(int(low + (high - low) * ratio * ratio))
            return
        for button in self.buttons:
            if button.enabled and button.rect.collidepoint(pos):
                self._perform_action(0, button.action, self.raise_to)

    def _clamp_raise(self, value):
        legal = self.game.legal_actions()
        low, high = int(legal["min_raise_to"]), int(legal["max_raise_to"])
        step = self.game.small_blind
        rounded = max(low, (int(value) // step) * step)
        return min(high, rounded)

    def _adjust_raise(self, delta):
        if self.can_human_act and self.game.legal_actions()["can_raise"]:
            self.raise_to = self._clamp_raise(self.raise_to + delta)

    def _set_raise_preset(self, preset):
        self.raise_to = self._clamp_raise(self._preset_target(preset))

    def _preset_target(self, preset):
        legal = self.game.legal_actions()
        low, high = int(legal["min_raise_to"]), int(legal["max_raise_to"])
        pot = max(self.game.big_blind, self.game.pot)
        targets = {
            "min": low,
            "half": self.game.current_bet + int(pot * 0.5),
            "three_quarter": self.game.current_bet + int(pot * 0.75),
            "pot": self.game.current_bet + pot,
            "allin": high,
            "plus": self.raise_to + self.game.small_blind,
        }
        return targets[preset]

    def _reset_raise_default(self):
        if self.game.human_turn:
            legal = self.game.legal_actions()
            if legal["can_raise"]:
                target = self.game.current_bet + max(self.game.big_blind, int(self.game.pot * 0.65))
                self.raise_to = self._clamp_raise(target)

    def _schedule_bot_turn(self, now, animation_delay=0.0):
        actor = self.game.actor
        self.observed_actor = actor
        self.thinking_started = now + animation_delay
        if actor in (None, 0) or self.game.hand_over:
            self.bot_due = float("inf")
            if actor == 0:
                self._reset_raise_default()
            return
        style = self.game.players[actor].style
        ranges = {
            "tight": (1.85, 2.75),
            "aggressive": (1.25, 1.95),
            "balanced": (2.05, 3.05),
            "loose": (1.45, 2.25),
        }
        low, high = ranges[style]
        self.bot_due = now + animation_delay + self.game.rng.uniform(low, high)

    def _new_hand(self):
        self.game.start_hand()
        self.last_stage = self.game.stage
        self.hand_over_at = 0.0
        self.bubbles.clear()
        self._begin_hand_animation()

    def _begin_hand_animation(self, initial=False):
        now = time.monotonic()
        self.motions.clear()
        self.revealed_hole.clear()
        self.revealed_community = 0
        self.logs.insert(0, LogEntry("系统", f"第 {self.game.hand_number} 手牌开始", (50, 210, 159), self.game.hand_number))
        for idx, player in enumerate(self.game.players):
            if player.last_action:
                self.logs.insert(0, LogEntry(player.name, player.last_action, self.seat_accents[idx], self.game.hand_number))
        order = []
        start = (self.game.dealer + 1) % len(self.game.players)
        for round_no in range(2):
            for offset in range(5):
                idx = (start + offset) % 5
                order.append((idx, round_no))
        for number, (idx, slot) in enumerate(order):
            target = self._hole_card_center(idx, slot)
            self.motions.append(Motion(
                "card", DECK_POS, target, now, 0.58, number * 0.11,
                self.game.players[idx].cards[slot], idx != 0, idx == 0,
                self._hole_card_size(idx), self._hole_rotation(idx, slot),
                reveal=("hole", idx, slot),
            ))
        self._schedule_bot_turn(now, 1.68)
        self.stage_banner = "发牌"
        self.stage_banner_until = now + 0.9

    def _perform_action(self, idx, action, amount=0):
        if idx != self.game.actor or self.animation_locked:
            return
        legal = self.game.legal_actions(idx)
        if action == "check" and not legal["can_check"]:
            action = "call"
        if action == "raise" and not legal["can_raise"]:
            return
        before_committed = self.game.players[idx].committed
        before_stage = self.game.stage
        before_community = len(self.game.community)
        before_over = self.game.hand_over
        self.game.act(idx, action, amount)
        player = self.game.players[idx]
        paid = player.committed - before_committed
        action_text = player.last_action or action
        accent = self.seat_accents[idx]
        now = time.monotonic()
        self.bubbles[idx] = (action_text, now + 2.8, accent)
        detail = ""
        if idx != 0:
            style_name = STYLE_PROFILES[player.style]["label"]
            reason = self.game.last_decision_note.get(idx, "按自己的节奏行动")
            detail = f"{style_name} · {reason}"
            self.motions.append(Motion("pulse", self.seats[idx], self.seats[idx], now, 0.62))
        self.logs.insert(0, LogEntry(player.name, action_text, accent, self.game.hand_number, detail))
        self.logs = self.logs[:18]
        delay = 0.0
        if paid > 0:
            self.motions.append(Motion("chip", self._chip_origin(idx), POT_POS, now, 0.72,
                                       amount=paid))
            delay = 0.52
        if action == "fold":
            for slot in range(2):
                self.revealed_hole.discard((idx, slot))
                self.motions.append(Motion(
                    "fold", self._hole_card_center(idx, slot), DECK_POS, now, 0.58,
                    slot * 0.09, player.cards[slot], True, False,
                    self._hole_card_size(idx), self._hole_rotation(idx, slot),
                ))
            delay = 0.52
        new_cards = len(self.game.community) - before_community
        if self.game.stage != before_stage and new_cards > 0:
            stage_name = self.game.stage.value
            self.logs.insert(0, LogEntry("牌桌", f"进入{stage_name}", (245, 193, 67), self.game.hand_number))
            self.stage_banner = stage_name
            self.stage_banner_until = now + 1.3
            for offset in range(new_cards):
                board_idx = before_community + offset
                self.motions.append(Motion(
                    "card", DECK_POS, self._community_center(board_idx), now,
                    0.72, delay + offset * 0.23, self.game.community[board_idx],
                    True, True, (68, 96), 0, reveal=("community", board_idx, 0),
                ))
            delay += 0.68 + new_cards * 0.23
        if self.game.hand_over and not before_over:
            self._schedule_payout(now + delay)
        remaining = max(
            (motion.started + motion.delay + motion.duration - now for motion in self.motions),
            default=0.0,
        )
        self._schedule_bot_turn(now, max(delay, remaining) + 0.18)

    def _schedule_payout(self, start_time):
        for order, winner in enumerate(self.game.winners):
            self.motions.append(Motion("payout", POT_POS, self._chip_origin(winner),
                                       start_time, 1.05, order * 0.18,
                                       amount=max(1, self.game.last_pot // max(1, len(self.game.winners)))))
        self.logs.insert(0, LogEntry("结果", self.game.message, (247, 198, 74), self.game.hand_number))
        self._burst_chips()

    def _update(self, dt):
        now = time.monotonic()
        finished = [motion for motion in self.motions if motion.complete(now)]
        for motion in finished:
            if motion.reveal:
                kind, first, second = motion.reveal
                if kind == "hole":
                    self.revealed_hole.add((first, second))
                else:
                    self.revealed_community = max(self.revealed_community, first + 1)
        self.motions = [motion for motion in self.motions if not motion.complete(now)]
        if not self.game.hand_over and self.game.actor not in (None, 0):
            if not self.animation_locked and now >= self.bot_due:
                idx = self.game.actor
                action, amount = self.game.bot_action(idx)
                self._perform_action(idx, action, amount)
        if self.game.hand_over and self.hand_over_at == 0:
            self.hand_over_at = now
        for particle in self.particles:
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["vy"] += 135 * dt
            particle["life"] -= dt
        self.particles = [particle for particle in self.particles if particle["life"] > 0]

    def _draw(self):
        self._draw_background()
        self._draw_header()
        self._draw_table_25d()
        self._draw_board()
        for idx in (2, 3, 1, 4, 0):
            self._draw_seat(idx)
        self._draw_motions()
        self._draw_log_panel()
        self._draw_controls()
        self._draw_particles()
        if time.monotonic() < self.stage_banner_until:
            self._draw_stage_banner()
        if self.show_help:
            self._draw_help()
        sw, sh = self.screen.get_size()
        scale = min(sw / W, sh / H)
        target = pygame.transform.smoothscale(self.canvas, (int(W * scale), int(H * scale)))
        self.screen.fill((3, 7, 11))
        self.screen.blit(target, ((sw - target.get_width()) // 2, (sh - target.get_height()) // 2))
        pygame.display.flip()

    def _draw_background(self):
        self.canvas.fill((4, 10, 15))
        for y in range(H):
            t = y / H
            pygame.draw.line(self.canvas, (5 + int(t * 4), 13 + int(t * 8), 19 + int(t * 10)), (0, y), (W, y))
        for x in range(-H, W, 80):
            pygame.draw.line(self.canvas, (11, 27, 33), (x, 0), (x + H, H), 1)

    def _draw_header(self):
        pygame.draw.rect(self.canvas, (4, 13, 18), (0, 0, W, 72))
        pygame.draw.line(self.canvas, (34, 219, 162), (0, 71), (TABLE_RIGHT, 71), 2)
        pygame.draw.circle(self.canvas, (35, 220, 164), (38, 35), 22)
        pygame.draw.circle(self.canvas, (4, 14, 18), (38, 35), 14)
        pygame.draw.circle(self.canvas, (246, 192, 61), (38, 35), 7)
        title_shadow = self.fonts["title"].render("NEON HOLD'EM", True, (15, 81, 71))
        self.canvas.blit(title_shadow, (74, 15))
        self.canvas.blit(self.fonts["title"].render("NEON HOLD'EM", True, (246, 243, 221)), (72, 12))
        self.canvas.blit(self.fonts["tiny"].render("CINEMATIC TABLE · 5-MAX", True, (88, 124, 127)), (74, 43))
        info = self.fonts["sm"].render(f"牌局 #{self.game.hand_number}   {self.game.stage.value}   盲注 10 / 20", True, (151, 178, 177))
        self.canvas.blit(info, info.get_rect(center=(570, 35)))
        self._mini_button((864, 22, 62, 38), "重开")
        self._mini_button((934, 22, 58, 38), "玩法")

    def _mini_button(self, rect, text):
        pygame.draw.rect(self.canvas, (15, 36, 42), rect, border_radius=9)
        pygame.draw.rect(self.canvas, (44, 81, 83), rect, 1, border_radius=9)
        label = self.fonts["xs"].render(text, True, (201, 221, 216))
        self.canvas.blit(label, label.get_rect(center=pygame.Rect(rect).center))

    def _draw_table_25d(self):
        # Thick lower layers sell the raised 2.5D table silhouette.
        shadow = pygame.Surface((1010, 560), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 150), (24, 42, 956, 472))
        self.canvas.blit(shadow, (0, 96))
        for depth, color in [(28, (34, 22, 19)), (22, (68, 43, 27)), (15, (105, 67, 34)), (8, (38, 27, 22))]:
            pygame.draw.ellipse(self.canvas, color, (42, 104 + depth, 956, 500))
        pygame.draw.ellipse(self.canvas, (9, 17, 19), (42, 104, 956, 500))
        pygame.draw.ellipse(self.canvas, (112, 73, 36), (49, 111, 942, 484))
        pygame.draw.ellipse(self.canvas, (30, 22, 19), (61, 122, 918, 462))
        pygame.draw.ellipse(self.canvas, (7, 91, 66), (73, 132, 894, 440))
        pygame.draw.ellipse(self.canvas, (9, 112, 81), (84, 141, 872, 421))
        pygame.draw.ellipse(self.canvas, (41, 212, 154), (91, 148, 858, 405), 2)
        pygame.draw.ellipse(self.canvas, (250, 194, 71), (55, 116, 930, 476), 2)
        for step in range(18):
            angle = math.tau * step / 18
            stud_x = int(520 + math.cos(angle) * 454)
            stud_y = int(352 + math.sin(angle) * 222)
            pygame.draw.circle(self.canvas, (35, 21, 16), (stud_x + 1, stud_y + 2), 4)
            pygame.draw.circle(self.canvas, (235, 175, 74), (stud_x, stud_y), 3)
            pygame.draw.circle(self.canvas, (255, 235, 164), (stud_x - 1, stud_y - 1), 1)
        # Perspective seams and central embossed logo.
        clip = pygame.Surface((W, H), pygame.SRCALPHA)
        for x in (155, 270, 390, 650, 770, 885):
            pygame.draw.line(clip, (18, 136, 100, 70), (520, 205), (x, 535), 1)
        pygame.draw.ellipse(clip, (5, 65, 52, 90), (266, 246, 508, 210), 2)
        self.canvas.blit(clip, (0, 0))
        pygame.draw.ellipse(self.canvas, (8, 76, 60), (461, 288, 118, 102))
        pygame.draw.ellipse(self.canvas, (15, 126, 91), (461, 282, 118, 102), 2)
        mark = self.fonts["xl"].render("N", True, (17, 143, 101))
        self.canvas.blit(mark, mark.get_rect(center=(520, 334)))
        # Deck shoe.
        pygame.draw.polygon(self.canvas, (4, 21, 27), [(493, 194), (546, 194), (554, 211), (500, 216)])
        pygame.draw.rect(self.canvas, (22, 67, 72), (494, 183, 54, 18), border_radius=4)
        for offset in range(0, 48, 6):
            pygame.draw.line(self.canvas, (54, 219, 164), (498 + offset, 187), (502 + offset, 198), 1)

    def _draw_board(self):
        pot = self.game.last_pot if self.game.hand_over else self.game.pot
        pot_label = self.fonts["tiny"].render("总底池", True, (151, 195, 182))
        self.canvas.blit(pot_label, pot_label.get_rect(center=(520, 397)))
        pot_text = self.fonts["lg"].render(f"{pot:,}", True, (255, 225, 128))
        self.canvas.blit(pot_text, pot_text.get_rect(center=(520, 419)))
        start = 520 - 5 * 34
        for idx in range(5):
            if idx < self.revealed_community:
                self._blit_card(self.game.community[idx], self._community_center(idx), (68, 96), False, 0)
            else:
                rect = pygame.Rect(0, 0, 64, 90)
                rect.center = self._community_center(idx)
                slot = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(slot, (3, 55, 45, 95), slot.get_rect(), border_radius=8)
                pygame.draw.rect(slot, (44, 165, 124, 90), slot.get_rect(), 1, border_radius=8)
                self.canvas.blit(slot, rect)
        if self.revealed_community >= 3 and not self.game.players[0].folded:
            try:
                rank = evaluate_seven(self.game.players[0].cards + self.game.community[:self.revealed_community])
                label = self.fonts["xs"].render(f"当前牌型  {rank.name}", True, (218, 235, 228))
                box = label.get_rect(center=(520, 472)).inflate(18, 8)
                pygame.draw.rect(self.canvas, (6, 48, 43), box, border_radius=10)
                self.canvas.blit(label, label.get_rect(center=box.center))
            except ValueError:
                pass

    def _draw_seat(self, idx):
        player = self.game.players[idx]
        x, y = self.seats[idx]
        active = idx == self.game.actor and not self.animation_locked
        winner = idx in self.game.winners
        accent = (247, 197, 68) if winner else self.seat_accents[idx]
        scale = 1.0 if idx in (0, 1, 4) else 0.88
        pulse = 3 + int((math.sin(time.monotonic() * 6) + 1) * 2) if active else 2
        if active or winner:
            glow = pygame.Surface((160, 110), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*accent, 45), (5, 5, 150, 96), pulse)
            self.canvas.blit(glow, (x - 80, y - 65))
        # Avatar, name plate, and depth shadow.
        avatar_y = y + (9 if idx != 0 else 18)
        pygame.draw.circle(self.canvas, (1, 9, 12), (x, avatar_y + 5), int(26 * scale))
        pygame.draw.circle(self.canvas, (18, 42, 48), (x, avatar_y), int(26 * scale))
        pygame.draw.circle(self.canvas, accent, (x, avatar_y), int(26 * scale), 3)
        initial = self.fonts["md"].render(player.name[0].upper(), True, (232, 242, 237))
        self.canvas.blit(initial, initial.get_rect(center=(x, avatar_y)))
        panel = pygame.Rect(x - 70, avatar_y + 25, 140, 42)
        pygame.draw.rect(self.canvas, (2, 10, 14), panel.move(0, 4), border_radius=9)
        pygame.draw.rect(self.canvas, (8, 24, 29), panel, border_radius=9)
        pygame.draw.rect(self.canvas, accent if active else (43, 69, 73), panel, 2 if active else 1, border_radius=9)
        self.canvas.blit(self.fonts["sm"].render(player.name, True, (247, 201, 77) if idx == 0 else (228, 238, 233)), (panel.x + 9, panel.y + 3))
        if idx != 0:
            persona = STYLE_PROFILES[player.style]["label"]
            persona_text = self.fonts["tiny"].render(persona, True, accent)
            self.canvas.blit(persona_text, (panel.right - persona_text.get_width() - 8, panel.y + 5))
        stack = self.fonts["tiny"].render(f"{player.stack:,} 筹码", True, (137, 164, 163))
        self.canvas.blit(stack, (panel.x + 9, panel.y + 23))
        if idx == self.game.dealer:
            pygame.draw.circle(self.canvas, (244, 242, 218), (panel.right - 11, panel.y + 12), 9)
            d = self.fonts["tiny"].render("D", True, (24, 37, 38))
            self.canvas.blit(d, d.get_rect(center=(panel.right - 11, panel.y + 12)))
        for slot in range(2):
            if (idx, slot) in self.revealed_hole and not player.folded:
                reveal = idx == 0 or (self.game.hand_over and player.active)
                self._blit_card(player.cards[slot], self._hole_card_center(idx, slot),
                                self._hole_card_size(idx), not reveal, self._hole_rotation(idx, slot))
        if player.folded:
            folded = self.fonts["xs"].render("已弃牌", True, (143, 151, 151))
            self.canvas.blit(folded, folded.get_rect(center=(x, panel.bottom + 13)))
        bubble = self.bubbles.get(idx)
        if bubble and time.monotonic() < bubble[1]:
            self._draw_action_bubble(idx, bubble[0], bubble[2])
        elif active and idx != 0:
            self._draw_thinking_bubble(idx, accent)
        if player.street_bet > 0:
            bx, by = self._chip_origin(idx)
            self._draw_chip_stack((bx, by), min(5, player.street_bet // 20 + 1), accent)
            amount = self.fonts["tiny"].render(str(player.street_bet), True, (245, 226, 166))
            self.canvas.blit(amount, amount.get_rect(center=(bx, by + 19)))

    def _draw_action_bubble(self, idx, text, accent):
        x, y = self.seats[idx]
        if idx == 0:
            center = (x + 112, y + 28)
        elif idx in (1, 2):
            center = (x + 104, y - 22)
        else:
            center = (x - 104, y - 22)
        label = self.fonts["md"].render(text, True, (242, 248, 243))
        rect = label.get_rect(center=center).inflate(24, 14)
        pygame.draw.rect(self.canvas, (2, 12, 16), rect.move(0, 4), border_radius=12)
        pygame.draw.rect(self.canvas, (12, 38, 42), rect, border_radius=12)
        pygame.draw.rect(self.canvas, accent, rect, 2, border_radius=12)
        self.canvas.blit(label, label.get_rect(center=rect.center))

    def _draw_thinking_bubble(self, idx, accent):
        x, y = self.seats[idx]
        center = (x + 104, y - 22) if idx in (1, 2) else (x - 104, y - 22)
        elapsed = max(0.0, time.monotonic() - self.thinking_started)
        dots = "." * (1 + int(elapsed * 2.4) % 3)
        label = self.fonts["sm"].render(f"思考中{dots}", True, (230, 240, 235))
        rect = label.get_rect(center=center).inflate(24, 13)
        pygame.draw.rect(self.canvas, (1, 9, 13), rect.move(0, 5), border_radius=12)
        pygame.draw.rect(self.canvas, (12, 34, 40), rect, border_radius=12)
        pygame.draw.rect(self.canvas, accent, rect, 2, border_radius=12)
        self.canvas.blit(label, label.get_rect(center=rect.center))

    def _draw_motions(self):
        now = time.monotonic()
        for motion in self.motions:
            t = motion.progress(now)
            if t <= 0:
                continue
            eased = 1 - (1 - t) ** 3
            x = motion.start[0] + (motion.end[0] - motion.start[0]) * eased
            y = motion.start[1] + (motion.end[1] - motion.start[1]) * eased
            if motion.kind == "pulse":
                radius = int(28 + 58 * eased)
                alpha = int(170 * (1 - t))
                ring = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
                pygame.draw.circle(ring, (255, 215, 105, alpha), (radius + 4, radius + 4), radius, 4)
                self.canvas.blit(ring, ring.get_rect(center=(int(x), int(y))))
                continue
            if motion.kind in ("chip", "payout"):
                y -= math.sin(math.pi * t) * (55 if motion.kind == "chip" else 78)
                self._draw_chip_stack((int(x), int(y)), 4, (244, 183, 62), alpha=int(255 * min(1, t * 3)))
                amount = self.fonts["xs"].render(f"+{motion.amount}", True, (255, 232, 153))
                self.canvas.blit(amount, amount.get_rect(center=(int(x), int(y) - 18)))
            else:
                rotation = motion.rotation * eased + (1 - eased) * -18
                back = motion.back
                width_scale = 1.0
                if motion.flip:
                    if t < 0.5:
                        width_scale = max(0.06, 1 - t * 2)
                    else:
                        width_scale = max(0.06, (t - 0.5) * 2)
                        back = False
                alpha = int(255 * (1 - t)) if motion.kind == "fold" else 255
                self._blit_card(motion.card, (int(x), int(y)), motion.size, back, rotation,
                                alpha=alpha, width_scale=width_scale)

    def _draw_log_panel(self):
        panel = pygame.Rect(TABLE_RIGHT, 0, W - TABLE_RIGHT, H)
        pygame.draw.rect(self.canvas, (5, 15, 20), panel)
        pygame.draw.line(self.canvas, (35, 65, 69), (TABLE_RIGHT, 0), (TABLE_RIGHT, H), 1)
        self.canvas.blit(self.fonts["md"].render("牌局动态", True, (233, 242, 237)), (1030, 26))
        stage = self.fonts["xs"].render(self.game.stage.value, True, (5, 25, 24))
        stage_rect = stage.get_rect(center=(1222, 36)).inflate(20, 8)
        pygame.draw.rect(self.canvas, (42, 211, 158), stage_rect, border_radius=10)
        self.canvas.blit(stage, stage.get_rect(center=stage_rect.center))
        pygame.draw.line(self.canvas, (27, 49, 54), (1028, 70), (1260, 70))
        y = 88
        for entry in self.logs[:8]:
            height = 66 if entry.detail else 54
            card = pygame.Rect(1025, y, 238, height)
            pygame.draw.rect(self.canvas, (9, 25, 30), card, border_radius=9)
            pygame.draw.rect(self.canvas, (27, 49, 54), card, 1, border_radius=9)
            pygame.draw.circle(self.canvas, entry.accent, (1041, y + 16), 5)
            name = self.fonts["xs"].render(entry.name, True, entry.accent)
            action = self.fonts["sm"].render(entry.action, True, (215, 229, 224))
            self.canvas.blit(name, (1052, y + 6))
            self.canvas.blit(action, (1040, y + 27))
            if entry.detail:
                detail = entry.detail if len(entry.detail) <= 20 else entry.detail[:19] + "…"
                self.canvas.blit(self.fonts["tiny"].render(detail, True, (111, 143, 143)), (1040, y + 48))
            y += height + 7
        if len(self.logs) < 3:
            hint = self.fonts["xs"].render("每一次下注都会记录在这里", True, (81, 112, 115))
            self.canvas.blit(hint, hint.get_rect(center=(1144, 292)))
        # Current-turn explainer at the bottom of the log.
        box = pygame.Rect(1025, 683, 238, 58)
        pygame.draw.rect(self.canvas, (12, 33, 37), box, border_radius=12)
        actor = self.game.actor
        if self.game.hand_over:
            headline, detail = "本手结束", self.game.message
        elif self.animation_locked:
            headline, detail = "动画进行中", "正在移动卡牌或筹码"
        elif actor == 0:
            headline, detail = "轮到你", "请选择弃牌、跟注或加注"
        else:
            bot = self.game.players[actor]
            profile = STYLE_PROFILES[bot.style]
            headline = f"{bot.name} · {profile['label']}"
            detail = profile["tagline"]
        self.canvas.blit(self.fonts["sm"].render(headline, True, (61, 220, 168)), (1038, 691))
        self.canvas.blit(self.fonts["tiny"].render(detail, True, (135, 159, 158)), (1038, 716))

    def _draw_controls(self):
        pygame.draw.rect(self.canvas, (3, 11, 15), (0, 645, TABLE_RIGHT, 115))
        pygame.draw.line(self.canvas, (28, 54, 58), (0, 645), (TABLE_RIGHT, 645))
        if self.game.hand_over:
            result = self.fonts["md"].render(self.game.message, True, (247, 220, 132))
            self.canvas.blit(result, result.get_rect(center=(520, 668)))
            rect = pygame.Rect(405, 697, 230, 48)
            pygame.draw.rect(self.canvas, (42, 211, 158), rect, border_radius=13)
            label = self.fonts["md"].render("再来一手  N", True, (4, 24, 23))
            self.canvas.blit(label, label.get_rect(center=rect.center))
            return
        legal = self.game.legal_actions() if self.can_human_act else None
        for button in self.buttons:
            button.enabled = self.can_human_act
            if button.action == "check":
                button.label = "过牌" if legal and legal["can_check"] else "—"
                button.enabled = bool(legal and legal["can_check"])
            elif button.action == "call":
                value = int(legal["to_call"]) if legal else 0
                button.label = f"跟注 {value}" if value else "过牌"
            elif button.action == "raise":
                button.label = f"加注 {self.raise_to}"
                button.enabled = bool(legal and legal["can_raise"])
            button.draw(self.canvas, self.fonts["sm"], self._mouse_canvas())
        status = "轮到你行动 · 滚轮/方向键可微调" if self.can_human_act else ("正在播放行动动画…" if self.animation_locked else "对手正在思考…")
        color = (55, 220, 167) if self.can_human_act else (125, 151, 151)
        self.canvas.blit(self.fonts["xs"].render(status, True, color), (24, 660))
        if self.can_human_act and legal and legal["can_raise"]:
            mouse = self._mouse_canvas()
            for rect, label, preset in self.preset_buttons:
                target = self._clamp_raise(self._preset_target(preset))
                selected = abs(self.raise_to - target) < self.game.small_blind
                hover = rect.collidepoint(mouse)
                fill = (238, 182, 63) if selected else ((40, 87, 83) if hover else (18, 46, 51))
                pygame.draw.rect(self.canvas, (0, 6, 8), rect.move(0, 3), border_radius=8)
                pygame.draw.rect(self.canvas, fill, rect, border_radius=8)
                pygame.draw.rect(self.canvas, (246, 208, 102) if selected else (53, 91, 92), rect, 1, border_radius=8)
                text_color = (20, 28, 27) if selected else (196, 216, 211)
                text = self.fonts["tiny"].render(label, True, text_color)
                self.canvas.blit(text, text.get_rect(center=rect.center))
            slider = pygame.Rect(565, 716, 420, 12)
            pygame.draw.rect(self.canvas, (1, 7, 10), slider.inflate(4, 8), border_radius=8)
            pygame.draw.rect(self.canvas, (28, 53, 57), slider, border_radius=6)
            low, high = int(legal["min_raise_to"]), int(legal["max_raise_to"])
            normalized = (self.raise_to - low) / max(1, high - low)
            ratio = math.sqrt(max(0.0, min(1.0, normalized)))
            fill_width = int(slider.w * ratio)
            pygame.draw.rect(self.canvas, (239, 183, 61), (slider.x, slider.y, fill_width, slider.h), border_radius=6)
            knob_x = slider.x + fill_width
            pygame.draw.circle(self.canvas, (3, 10, 12), (knob_x, slider.centery + 2), 12)
            pygame.draw.circle(self.canvas, (255, 224, 121), (knob_x, slider.centery), 10)
            pygame.draw.circle(self.canvas, (255, 247, 210), (knob_x - 2, slider.centery - 2), 3)
            amount = self.fonts["number"].render(f"加注到 {self.raise_to}", True, (255, 220, 111))
            self.canvas.blit(amount, (565, 689))
            bounds = self.fonts["tiny"].render(f"最小 {low}    最大 {high}", True, (112, 143, 143))
            self.canvas.blit(bounds, (850, 695))

    def _draw_stage_banner(self):
        t = max(0.0, self.stage_banner_until - time.monotonic())
        alpha = min(230, int(t * 350))
        surface = pygame.Surface((210, 66), pygame.SRCALPHA)
        pygame.draw.rect(surface, (3, 17, 21, alpha), surface.get_rect(), border_radius=16)
        pygame.draw.rect(surface, (45, 220, 165, alpha), surface.get_rect(), 2, border_radius=16)
        label = self.fonts["lg"].render(self.stage_banner, True, (238, 247, 241))
        surface.blit(label, label.get_rect(center=(105, 33)))
        self.canvas.blit(surface, (415, 477))

    def _draw_help(self):
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 5, 8, 220))
        self.canvas.blit(shade, (0, 0))
        panel = pygame.Rect(310, 135, 660, 490)
        pygame.draw.rect(self.canvas, (8, 27, 33), panel, border_radius=20)
        pygame.draw.rect(self.canvas, (43, 213, 160), panel, 2, border_radius=20)
        self.canvas.blit(self.fonts["lg"].render("德州扑克玩法", True, (238, 246, 241)), (352, 174))
        lines = [
            "用 2 张底牌与 5 张公共牌组成最强的 5 张牌型。",
            "牌型：同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 > 一对 > 高牌",
            "",
            "画面提示",
            "发光座位代表当前行动者；行动气泡显示刚才的决定。",
            "右侧牌局动态会保留每次过牌、跟注、加注、全下和弃牌。",
            "飞向中央的筹码代表下注，公共牌会在新阶段逐张翻开。",
            "加注区可选择最小、半池、3/4 池、满池或全下，滚轮可以微调。",
            "",
            "快捷键：F 弃牌 · C/空格 跟注或过牌 · R/回车 加注 · N 下一手",
        ]
        y = 226
        for line in lines:
            special = line == "画面提示"
            font = self.fonts["md"] if special else self.fonts["sm"]
            color = (246, 195, 70) if special else (187, 207, 202)
            self.canvas.blit(font.render(line, True, color), (352, y))
            y += 36
        close = self.fonts["xs"].render("点击任意位置关闭", True, (104, 137, 139))
        self.canvas.blit(close, close.get_rect(center=(640, 590)))

    def _card_surface(self, card, size, back=False):
        w, h = size
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        card_rect = pygame.Rect(1, 1, w - 7, h - 9)
        pygame.draw.rect(surface, (0, 0, 0, 120), card_rect.move(5, 8), border_radius=9)
        pygame.draw.rect(surface, (89, 69, 42), card_rect.move(2, 5), border_radius=9)
        if back:
            pygame.draw.rect(surface, (8, 25, 43), card_rect, border_radius=9)
            pygame.draw.rect(surface, (55, 225, 169), card_rect, 3, border_radius=9)
            inner = card_rect.inflate(-9, -9)
            pygame.draw.rect(surface, (14, 61, 70), inner, border_radius=6)
            pygame.draw.rect(surface, (243, 186, 67), inner, 2, border_radius=6)
            for yy in range(inner.top + 5, inner.bottom - 3, 8):
                for xx in range(inner.left + 5, inner.right - 3, 8):
                    phase = ((xx + yy) // 8) % 2
                    color = (50, 208, 161) if phase else (25, 119, 116)
                    pygame.draw.polygon(surface, color, [(xx, yy - 2), (xx + 3, yy + 1), (xx, yy + 4), (xx - 3, yy + 1)])
            pygame.draw.circle(surface, (6, 34, 42), inner.center, max(7, int(w * .16)))
            pygame.draw.circle(surface, (244, 188, 70), inner.center, max(5, int(w * .12)), 2)
            pygame.draw.line(surface, (255, 245, 194), (card_rect.left + 9, card_rect.top + 3), (card_rect.right - 9, card_rect.top + 3), 1)
            return surface
        color = (204, 48, 62) if card.suit in RED_SUITS else (18, 27, 31)
        edge = (244, 83, 103) if card.suit in RED_SUITS else (46, 201, 181)
        pygame.draw.rect(surface, (249, 244, 221), card_rect, border_radius=9)
        pygame.draw.rect(surface, edge, card_rect, 3, border_radius=9)
        inner = card_rect.inflate(-7, -7)
        pygame.draw.rect(surface, (255, 252, 235), inner, border_radius=6)
        for yy in range(inner.top + 2, inner.bottom, 6):
            pygame.draw.line(surface, (239, 229, 203), (inner.left + 1, yy), (inner.right - 1, yy), 1)
        rank_text = "10" if card.rank == "T" else card.rank
        rank_font = self.fonts["xs"] if w < 55 else self.fonts["md"]
        rank_shadow = rank_font.render(rank_text, True, (224, 183, 138))
        surface.blit(rank_shadow, (8, 6))
        surface.blit(rank_font.render(rank_text, True, color), (6, 4))
        suit_font = pygame.font.SysFont("Segoe UI Symbol", max(24, int(w * .54)))
        suit = suit_font.render(SUIT_SYMBOL[card.suit], True, color)
        watermark = suit_font.render(SUIT_SYMBOL[card.suit], True, edge)
        watermark.set_alpha(38)
        surface.blit(watermark, watermark.get_rect(center=(card_rect.centerx + 6, card_rect.centery + 9)))
        surface.blit(suit, suit.get_rect(center=(card_rect.centerx, card_rect.centery + 11)))
        pygame.draw.circle(surface, edge, (card_rect.right - 8, card_rect.bottom - 8), 3)
        pygame.draw.line(surface, (255, 255, 255, 210), (card_rect.left + 9, card_rect.top + 2), (card_rect.right - 9, card_rect.top + 2), 2)
        return surface

    def _blit_card(self, card, center, size, back, rotation, alpha=255, width_scale=1.0):
        if card is None:
            return
        surface = self._card_surface(card, size, back)
        if width_scale != 1.0:
            surface = pygame.transform.smoothscale(surface, (max(2, int(size[0] * width_scale)), size[1]))
        if rotation:
            surface = pygame.transform.rotozoom(surface, rotation, 1.0)
        surface.set_alpha(alpha)
        self.canvas.blit(surface, surface.get_rect(center=center))

    def _draw_chip_stack(self, center, count, color, alpha=255):
        x, y = center
        for idx in range(count):
            yy = y - idx * 4
            chip = pygame.Surface((28, 15), pygame.SRCALPHA)
            pygame.draw.ellipse(chip, (0, 8, 10, alpha), (1, 5, 26, 10))
            pygame.draw.ellipse(chip, (*color, alpha), (1, 1, 26, 11))
            pygame.draw.ellipse(chip, (238, 244, 226, alpha), (5, 3, 18, 7), 2)
            self.canvas.blit(chip, (x - 14, yy - 7))

    def _burst_chips(self):
        for _ in range(38):
            angle = random.uniform(math.pi, math.tau)
            speed = random.uniform(65, 210)
            self.particles.append({
                "x": float(POT_POS[0]), "y": float(POT_POS[1]),
                "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                "life": random.uniform(.8, 1.5),
                "color": random.choice(self.seat_accents),
            })

    def _draw_particles(self):
        for particle in self.particles:
            pygame.draw.circle(self.canvas, particle["color"], (int(particle["x"]), int(particle["y"])), 5)
            pygame.draw.circle(self.canvas, (245, 241, 219), (int(particle["x"]), int(particle["y"])), 3, 1)

    def _community_center(self, idx):
        return 520 - 2 * 74 + idx * 74, 276

    def _hole_card_size(self, idx):
        return (72, 102) if idx == 0 else (50, 72)

    def _hole_card_center(self, idx, slot):
        x, y = self.seats[idx]
        if idx == 0:
            float_y = math.sin(time.monotonic() * 2.2 + slot) * 2
            return x - 32 + slot * 64, y - 66 + float_y
        if idx in (2, 3):
            return x - 23 + slot * 46, y - 50
        return x - 23 + slot * 46, y - 50

    def _hole_rotation(self, idx, slot):
        return 7 if slot == 0 else -7

    def _chip_origin(self, idx):
        x, y = self.seats[idx]
        offsets = [(105, -45), (94, -34), (72, 80), (-72, 80), (-94, -34)]
        ox, oy = offsets[idx]
        return x + ox, y + oy
