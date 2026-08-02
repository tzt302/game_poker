#!/usr/bin/env python3
"""Launch the Neon Hold'em desktop game."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

if "--smoke-test" in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from neon_holdem.ui import PokerApp


def main() -> None:
    pygame.init()
    try:
        screen = pygame.display.set_mode((1280, 760), pygame.RESIZABLE | pygame.DOUBLEBUF)
        pygame.display.set_caption("Neon Hold'em · 德州扑克")
        PokerApp(screen).run()
    finally:
        pygame.quit()


def smoke_test() -> None:
    """Render one frame and exit, allowing packaged builds to be verified."""
    pygame.init()
    try:
        screen = pygame.display.set_mode((1280, 760))
        PokerApp(screen)._draw()
    finally:
        pygame.quit()


if __name__ == "__main__":
    smoke_test() if "--smoke-test" in sys.argv else main()
