#!/usr/bin/env python3
"""Launch the Neon Hold'em desktop game."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

import pygame

from poker.ui import PokerApp


def main() -> None:
    pygame.init()
    try:
        screen = pygame.display.set_mode((1280, 760), pygame.RESIZABLE | pygame.DOUBLEBUF)
        pygame.display.set_caption("Neon Hold'em · 德州扑克")
        PokerApp(screen).run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
