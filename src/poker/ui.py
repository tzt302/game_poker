"""Polished Pygame interface for Neon Hold'em."""

from __future__ import annotations

import math
import random
import time

import pygame

from .engine import Card, HoldemGame, Stage, evaluate_seven


W, H = 1280, 760
SUIT_SYMBOL = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RED_SUITS = {"h", "d"}


class Button:
    def __init__(self, rect: pygame.Rect, label: str, action: str, accent=(41, 211, 164)):
        self.rect = rect
        self.label = label
        self.action = action
        self.accent = accent
        self.enabled = True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse: tuple[int, int]):
        hover = self.enabled and self.rect.collidepoint(mouse)
        base = self.accent if hover else tuple(max(0, c - 24) for c in self.accent)
        if not self.enabled:
            base = (52, 65, 70)
        shadow = self.rect.move(0, 5)
        pygame.draw.rect(surface, (5, 11, 14, 120), shadow, border_radius=14)
        pygame.draw.rect(surface, base, self.rect, border_radius=14)
        pygame.draw.rect(surface, (255, 255, 255, 45), self.rect, 1, border_radius=14)
        color = (7, 23, 25) if self.enabled else (130, 142, 144)
        text = font.render(self.label, True, color)
        surface.blit(text, text.get_rect(center=self.rect.center))


class PokerApp:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.canvas = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.game = HoldemGame()
        self.running = True
        self.bot_due = time.monotonic() + 0.9
        self.hand_over_at = 0.0
        self.raise_to = 60
        self.show_help = False
        self.particles: list[dict] = []
        self.last_stage = self.game.stage
        self.last_actor = self.game.actor
        self.notice = ""
        self.notice_until = 0.0
        self.fonts = self._load_fonts()
        self.seats = [(640, 530), (220, 445), (285, 190), (995, 190), (1060, 445)]
        self.buttons = [
            Button(pygame.Rect(345, 685, 135, 52), "弃 牌", "fold", (239, 91, 97)),
            Button(pygame.Rect(493, 685, 150, 52), "过 牌", "check", (78, 143, 181)),
            Button(pygame.Rect(656, 685, 150, 52), "跟 注", "call", (44, 199, 145)),
            Button(pygame.Rect(819, 685, 150, 52), "加 注", "raise", (242, 184, 72)),
        ]

    def _load_fonts(self) -> dict[str, pygame.font.Font]:
        candidates = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "Arial"]
        name = next((f for f in candidates if pygame.font.match_font(f)), None)
        return {
            "xs": pygame.font.SysFont(name, 14),
            "sm": pygame.font.SysFont(name, 17),
            "md": pygame.font.SysFont(name, 21, bold=True),
            "lg": pygame.font.SysFont(name, 28, bold=True),
            "xl": pygame.font.SysFont(name, 38, bold=True),
            "card": pygame.font.SysFont(name, 32, bold=True),
            "suit": pygame.font.SysFont("Segoe UI Symbol", 38),
        }

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000
            self._events()
            self._update(dt)
            self._draw()

    def _mouse_canvas(self) -> tuple[int, int]:
        sw, sh = self.screen.get_size()
        scale = min(sw / W, sh / H)
        ox, oy = (sw - W * scale) / 2, (sh - H * scale) / 2
        mx, my = pygame.mouse.get_pos()
        return int((mx - ox) / scale), int((my - oy) / scale)

    def _events(self) -> None:
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
                elif self.game.human_turn:
                    if event.key == pygame.K_f:
                        self._human_action("fold")
                    elif event.key in (pygame.K_c, pygame.K_SPACE):
                        legal = self.game.legal_actions()
                        self._human_action("check" if legal["can_check"] else "call")
                    elif event.key in (pygame.K_r, pygame.K_RETURN):
                        self._human_action("raise")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._click(self._mouse_canvas())

    def _click(self, pos: tuple[int, int]) -> None:
        if self.show_help:
            self.show_help = False
            return
        if pygame.Rect(1122, 24, 46, 42).collidepoint(pos):
            self._new_hand()
            return
        if pygame.Rect(1178, 24, 76, 42).collidepoint(pos):
            self.show_help = True
            return
        if self.game.hand_over and pygame.Rect(530, 650, 220, 54).collidepoint(pos):
            self._new_hand()
            return
        slider = pygame.Rect(830, 652, 285, 16)
        if self.game.human_turn and slider.inflate(0, 24).collidepoint(pos):
            legal = self.game.legal_actions()
            low, high = int(legal["min_raise_to"]), int(legal["max_raise_to"])
            ratio = max(0.0, min(1.0, (pos[0] - slider.x) / slider.width))
            self.raise_to = int(low + (high - low) * ratio)
            self.raise_to = max(low, (self.raise_to // 10) * 10)
            return
        for button in self.buttons:
            if button.enabled and button.rect.collidepoint(pos):
                self._human_action(button.action)
                return

    def _human_action(self, action: str) -> None:
        if not self.game.human_turn:
            return
        legal = self.game.legal_actions()
        if action == "check" and not legal["can_check"]:
            action = "call"
        if action == "raise":
            if not legal["can_raise"]:
                return
            self.game.act(0, "raise", self.raise_to)
        else:
            self.game.act(0, action)
        self.bot_due = time.monotonic() + 0.65
        self._after_state_change()

    def _new_hand(self) -> None:
        self.game.start_hand()
        self.bot_due = time.monotonic() + 0.8
        self.hand_over_at = 0
        self.last_stage = self.game.stage
        self.last_actor = self.game.actor

    def _update(self, dt: float) -> None:
        now = time.monotonic()
        if not self.game.hand_over and self.game.actor is not None and self.game.actor != 0:
            if now >= self.bot_due:
                idx = self.game.actor
                action, amount = self.game.bot_action(idx)
                self.game.act(idx, action, amount)
                self.bot_due = now + 0.62
                self._after_state_change()
        if self.game.hand_over and self.hand_over_at == 0:
            self.hand_over_at = now
            self._burst_chips()
        for particle in self.particles:
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["vy"] += 120 * dt
            particle["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0]

    def _after_state_change(self) -> None:
        if self.game.stage != self.last_stage:
            self.notice = self.game.stage.value
            self.notice_until = time.monotonic() + 1.1
            self.last_stage = self.game.stage
        if self.game.human_turn:
            legal = self.game.legal_actions()
            self.raise_to = max(int(legal["min_raise_to"]), min(self.raise_to, int(legal["max_raise_to"])))

    def _burst_chips(self) -> None:
        colors = [(240, 71, 88), (53, 205, 157), (246, 190, 64), (76, 148, 231)]
        for _ in range(45):
            angle = random.uniform(math.pi, math.tau)
            speed = random.uniform(70, 230)
            self.particles.append({
                "x": 640.0, "y": 365.0,
                "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                "life": random.uniform(0.8, 1.7), "color": random.choice(colors),
            })

    def _draw(self) -> None:
        self._draw_background()
        self._draw_header()
        self._draw_table()
        self._draw_community()
        for idx, pos in enumerate(self.seats):
            self._draw_seat(idx, pos)
        self._draw_controls()
        self._draw_particles()
        if time.monotonic() < self.notice_until:
            self._draw_notice()
        if self.show_help:
            self._draw_help()
        sw, sh = self.screen.get_size()
        scale = min(sw / W, sh / H)
        target = pygame.transform.smoothscale(self.canvas, (int(W * scale), int(H * scale)))
        self.screen.fill((5, 10, 15))
        self.screen.blit(target, ((sw - target.get_width()) // 2, (sh - target.get_height()) // 2))
        pygame.display.flip()

    def _draw_background(self) -> None:
        self.canvas.fill((6, 15, 22))
        for y in range(H):
            t = y / H
            color = (int(8 + 3 * t), int(22 + 7 * t), int(29 + 10 * t))
            pygame.draw.line(self.canvas, color, (0, y), (W, y))
        for x in range(-H, W, 90):
            pygame.draw.line(self.canvas, (13, 32, 40), (x, 0), (x + H, H), 1)

    def _draw_header(self) -> None:
        pygame.draw.rect(self.canvas, (7, 17, 23), (0, 0, W, 82))
        pygame.draw.line(self.canvas, (32, 214, 160), (0, 81), (W, 81), 2)
        pygame.draw.circle(self.canvas, (32, 214, 160), (42, 41), 25)
        pygame.draw.circle(self.canvas, (7, 17, 23), (42, 41), 16)
        pygame.draw.circle(self.canvas, (242, 190, 65), (42, 41), 8)
        title = self.fonts["lg"].render("NEON HOLD'EM", True, (237, 246, 244))
        self.canvas.blit(title, (80, 18))
        sub = self.fonts["xs"].render("NO-LIMIT  ·  5-MAX", True, (91, 123, 129))
        self.canvas.blit(sub, (82, 52))
        center = self.fonts["sm"].render(f"牌局 #{self.game.hand_number}    盲注 10 / 20", True, (158, 181, 181))
        self.canvas.blit(center, center.get_rect(center=(640, 42)))
        self._header_button((1122, 24, 46, 42), "重开")
        self._header_button((1178, 24, 76, 42), "玩法")

    def _header_button(self, rect, label):
        pygame.draw.rect(self.canvas, (20, 42, 49), rect, border_radius=10)
        pygame.draw.rect(self.canvas, (47, 78, 83), rect, 1, border_radius=10)
        text = self.fonts["sm"].render(label, True, (207, 224, 222))
        self.canvas.blit(text, text.get_rect(center=pygame.Rect(rect).center))

    def _draw_table(self) -> None:
        outer = pygame.Rect(88, 103, 1104, 520)
        pygame.draw.ellipse(self.canvas, (2, 7, 10), outer.move(0, 10))
        pygame.draw.ellipse(self.canvas, (96, 67, 37), outer)
        pygame.draw.ellipse(self.canvas, (39, 28, 21), outer.inflate(-12, -12))
        felt = outer.inflate(-28, -28)
        pygame.draw.ellipse(self.canvas, (9, 83, 65), felt)
        pygame.draw.ellipse(self.canvas, (10, 103, 78), felt.inflate(-18, -18))
        pygame.draw.ellipse(self.canvas, (32, 188, 138), felt.inflate(-34, -34), 2)
        # Subtle felt rings and center emblem.
        pygame.draw.ellipse(self.canvas, (14, 116, 87), (347, 226, 586, 254), 2)
        pygame.draw.circle(self.canvas, (11, 93, 71), (640, 355), 72, 2)
        mark = self.fonts["xl"].render("N", True, (20, 127, 95))
        self.canvas.blit(mark, mark.get_rect(center=(640, 373)))

    def _draw_community(self) -> None:
        pot_value = self.game.last_pot if self.game.hand_over else self.game.pot
        label = self.fonts["xs"].render("总底池", True, (169, 205, 194))
        self.canvas.blit(label, label.get_rect(center=(640, 200)))
        pot = self.fonts["lg"].render(f"{pot_value:,}", True, (255, 238, 179))
        self.canvas.blit(pot, pot.get_rect(center=(640, 226)))
        self._draw_chip_stack(586, 215, max(1, min(5, pot_value // 60 + 1)))
        self._draw_chip_stack(690, 215, max(1, min(5, pot_value // 100 + 1)), (242, 188, 66))
        start_x = 640 - (5 * 66 - 8) // 2
        for i in range(5):
            x = start_x + i * 66
            if i < len(self.game.community):
                self._draw_card(self.game.community[i], x, 260, 58, 82)
            else:
                self._draw_card_slot(x, 260, 58, 82)
        if len(self.game.community) >= 5 and not self.game.hand_over:
            try:
                rank = evaluate_seven(self.game.players[0].cards + self.game.community)
                text = self.fonts["sm"].render(f"你的牌型：{rank.name}", True, (220, 237, 232))
                self.canvas.blit(text, text.get_rect(center=(640, 365)))
            except ValueError:
                pass

    def _draw_card_slot(self, x, y, w, h):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (8, 62, 52, 115), (0, 0, w, h), border_radius=8)
        pygame.draw.rect(surf, (53, 155, 124, 120), (0, 0, w, h), 1, border_radius=8)
        self.canvas.blit(surf, (x, y))

    def _draw_card(self, card: Card, x: int, y: int, w=62, h=88, back=False):
        pygame.draw.rect(self.canvas, (2, 13, 17), (x + 3, y + 5, w, h), border_radius=9)
        pygame.draw.rect(self.canvas, (242, 244, 239), (x, y, w, h), border_radius=9)
        pygame.draw.rect(self.canvas, (207, 216, 210), (x, y, w, h), 1, border_radius=9)
        if back:
            pygame.draw.rect(self.canvas, (15, 43, 66), (x + 5, y + 5, w - 10, h - 10), border_radius=6)
            pygame.draw.rect(self.canvas, (33, 190, 143), (x + 9, y + 9, w - 18, h - 18), 2, border_radius=5)
            for yy in range(y + 15, y + h - 10, 10):
                for xx in range(x + 15, x + w - 8, 10):
                    pygame.draw.circle(self.canvas, (28, 104, 99), (xx, yy), 2)
            return
        color = (201, 43, 57) if card.suit in RED_SUITS else (19, 28, 32)
        display_rank = "10" if card.rank == "T" else card.rank
        rank_font = self.fonts["sm"] if card.rank == "T" else self.fonts["md"]
        rank = rank_font.render(display_rank, True, color)
        self.canvas.blit(rank, (x + 7, y + 4))
        suit = self.fonts["suit"].render(SUIT_SYMBOL[card.suit], True, color)
        self.canvas.blit(suit, suit.get_rect(center=(x + w // 2 + 5, y + h // 2 + 11)))

    def _draw_seat(self, idx: int, pos: tuple[int, int]) -> None:
        player = self.game.players[idx]
        x, y = pos
        is_actor = idx == self.game.actor
        is_winner = idx in self.game.winners
        if is_actor or is_winner:
            radius = 76 if idx == 0 else 64
            glow = (244, 192, 71) if is_winner else (49, 224, 167)
            pygame.draw.circle(self.canvas, (*glow, 40), (x, y), radius)
            pygame.draw.circle(self.canvas, glow, (x, y), radius, 3)
        if idx == 0:
            self._draw_card(player.cards[0], x - 58, y - 68, 62, 88)
            self._draw_card(player.cards[1], x + 2, y - 68, 62, 88)
        else:
            reveal = self.game.hand_over and player.active
            self._draw_card(player.cards[0], x - 46, y - 55, 50, 70, back=not reveal)
            self._draw_card(player.cards[1], x + 1, y - 55, 50, 70, back=not reveal)
        panel_w = 180 if idx == 0 else 144
        panel = pygame.Rect(x - panel_w // 2, y + 22, panel_w, 48)
        pygame.draw.rect(self.canvas, (8, 18, 23), panel, border_radius=10)
        border = (244, 190, 69) if is_winner else ((44, 214, 159) if is_actor else (50, 75, 79))
        pygame.draw.rect(self.canvas, border, panel, 2 if (is_actor or is_winner) else 1, border_radius=10)
        name_color = (245, 203, 83) if idx == 0 else (225, 236, 232)
        name = self.fonts["sm"].render(player.name, True, name_color)
        stack = self.fonts["xs"].render(f"{player.stack:,} 筹码", True, (144, 172, 171))
        self.canvas.blit(name, (panel.x + 12, panel.y + 5))
        self.canvas.blit(stack, (panel.x + 12, panel.y + 27))
        if idx == self.game.dealer:
            pygame.draw.circle(self.canvas, (242, 242, 228), (panel.right - 12, panel.y + 13), 10)
            d = self.fonts["xs"].render("D", True, (19, 38, 40))
            self.canvas.blit(d, d.get_rect(center=(panel.right - 12, panel.y + 13)))
        if player.folded:
            veil = pygame.Surface((panel_w, 48), pygame.SRCALPHA)
            veil.fill((3, 8, 10, 155))
            self.canvas.blit(veil, panel)
            folded = self.fonts["xs"].render("已弃牌", True, (145, 153, 153))
            self.canvas.blit(folded, folded.get_rect(center=panel.center))
        elif player.last_action:
            bubble = self.fonts["xs"].render(player.last_action, True, (237, 245, 239))
            bubble_rect = bubble.get_rect(center=(x, panel.bottom + 15)).inflate(18, 8)
            pygame.draw.rect(self.canvas, (13, 45, 48), bubble_rect, border_radius=10)
            self.canvas.blit(bubble, bubble.get_rect(center=bubble_rect.center))
        if player.street_bet:
            bx = x + (100 if idx in (0, 1, 2) else -100)
            by = y - 10 if idx else y - 80
            self._draw_chip_stack(bx, by, min(4, player.street_bet // 20 + 1))
            bet = self.fonts["xs"].render(str(player.street_bet), True, (239, 231, 199))
            self.canvas.blit(bet, bet.get_rect(center=(bx, by + 20)))

    def _draw_chip_stack(self, x, y, count, color=(48, 202, 151)):
        for i in range(count):
            yy = y - i * 4
            pygame.draw.ellipse(self.canvas, (4, 19, 22), (x - 10, yy - 4, 22, 12))
            pygame.draw.ellipse(self.canvas, color, (x - 10, yy - 6, 22, 10))
            pygame.draw.ellipse(self.canvas, (230, 245, 237), (x - 7, yy - 4, 16, 6), 2)

    def _draw_controls(self) -> None:
        pygame.draw.rect(self.canvas, (5, 13, 18), (0, 642, W, 118))
        pygame.draw.line(self.canvas, (28, 57, 62), (0, 642), (W, 642), 1)
        if self.game.hand_over:
            result = self.fonts["md"].render(self.game.message, True, (244, 226, 166))
            self.canvas.blit(result, result.get_rect(center=(640, 625)))
            rect = pygame.Rect(530, 672, 220, 54)
            pygame.draw.rect(self.canvas, (39, 210, 157), rect, border_radius=14)
            text = self.fonts["md"].render("再来一手  N", True, (6, 25, 25))
            self.canvas.blit(text, text.get_rect(center=rect.center))
            return
        legal = self.game.legal_actions() if self.game.human_turn else None
        for button in self.buttons:
            button.enabled = self.game.human_turn
            if button.action == "check":
                button.label = "过 牌" if legal and legal["can_check"] else "—"
                button.enabled = bool(legal and legal["can_check"])
            elif button.action == "call":
                call = int(legal["to_call"]) if legal else 0
                button.label = f"跟 注  {call}" if call else "过 牌"
            elif button.action == "raise":
                button.label = f"加 注  {self.raise_to}"
                button.enabled = bool(legal and legal["can_raise"])
            button.draw(self.canvas, self.fonts["sm"], self._mouse_canvas())
        if self.game.human_turn and legal and legal["can_raise"]:
            slider = pygame.Rect(830, 652, 285, 16)
            pygame.draw.rect(self.canvas, (38, 62, 66), slider, border_radius=8)
            low, high = int(legal["min_raise_to"]), int(legal["max_raise_to"])
            ratio = (self.raise_to - low) / max(1, high - low)
            fill = pygame.Rect(slider.x, slider.y, int(slider.w * ratio), slider.h)
            pygame.draw.rect(self.canvas, (239, 184, 67), fill, border_radius=8)
            knob_x = slider.x + int(slider.w * ratio)
            pygame.draw.circle(self.canvas, (255, 239, 186), (knob_x, slider.centery), 10)
            hint = self.fonts["xs"].render(f"加注额  {self.raise_to}   ·   最大 {high}", True, (158, 178, 178))
            self.canvas.blit(hint, (829, 623))
        status = "轮到你行动" if self.game.human_turn else f"{self.game.players[self.game.actor].name} 正在思考…"
        status_text = self.fonts["sm"].render(status, True, (64, 219, 169) if self.game.human_turn else (145, 171, 170))
        self.canvas.blit(status_text, status_text.get_rect(center=(640, 624)))

    def _draw_particles(self) -> None:
        for p in self.particles:
            pygame.draw.circle(self.canvas, p["color"], (int(p["x"]), int(p["y"])), 5)
            pygame.draw.circle(self.canvas, (245, 244, 218), (int(p["x"]), int(p["y"])), 3, 1)

    def _draw_notice(self) -> None:
        overlay = pygame.Surface((240, 70), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (5, 20, 23, 225), (0, 0, 240, 70), border_radius=18)
        pygame.draw.rect(overlay, (49, 218, 163, 200), (0, 0, 240, 70), 2, border_radius=18)
        text = self.fonts["lg"].render(self.notice, True, (230, 246, 239))
        overlay.blit(text, text.get_rect(center=(120, 35)))
        self.canvas.blit(overlay, (520, 370))

    def _draw_help(self) -> None:
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((1, 7, 10, 210))
        self.canvas.blit(shade, (0, 0))
        panel = pygame.Rect(320, 140, 640, 480)
        pygame.draw.rect(self.canvas, (10, 28, 34), panel, border_radius=22)
        pygame.draw.rect(self.canvas, (41, 207, 157), panel, 2, border_radius=22)
        title = self.fonts["lg"].render("怎么玩", True, (239, 246, 241))
        self.canvas.blit(title, (365, 180))
        lines = [
            "用你的 2 张底牌与 5 张公共牌，组成最强的 5 张牌型。",
            "牌型由强到弱：同花顺、四条、葫芦、同花、顺子、三条、",
            "两对、一对、高牌。每手牌依次经历翻牌前、翻牌、转牌、河牌。",
            "",
            "快捷键",
            "F  弃牌       C / 空格  跟注或过牌       R / 回车  加注",
            "N  下一手     H  打开帮助              Esc  退出",
            "",
            "提示：AI 会根据牌力、底池赔率和自己的性格作决定。",
            "每位破产玩家会自动带 1,000 筹码重新入座。",
        ]
        y = 238
        for line in lines:
            font = self.fonts["md"] if line == "快捷键" else self.fonts["sm"]
            color = (244, 203, 85) if line == "快捷键" else (184, 207, 202)
            text = font.render(line, True, color)
            self.canvas.blit(text, (365, y))
            y += 34
        close = self.fonts["xs"].render("点击任意位置关闭", True, (103, 139, 140))
        self.canvas.blit(close, close.get_rect(center=(640, 585)))
