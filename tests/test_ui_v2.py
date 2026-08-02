import os
import sys
import time
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pygame

from neon_holdem.ui import PokerApp


class AnimationFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.display.set_mode((1280, 760))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = PokerApp(self.screen)

    def finish_animations(self):
        for motion in self.app.motions:
            motion.started = time.monotonic() - motion.delay - motion.duration - 1
        self.app._update(0)

    def test_deal_reveals_all_ten_hole_cards(self):
        self.assertEqual(len(self.app.motions), 10)
        self.finish_animations()
        self.assertFalse(self.app.animation_locked)
        self.assertEqual(len(self.app.revealed_hole), 10)

    def test_ai_action_creates_log_and_visual_feedback(self):
        self.finish_animations()
        idx = self.app.game.actor
        self.assertNotEqual(idx, 0)
        legal = self.app.game.legal_actions(idx)
        action = "check" if legal["can_check"] else "call"
        before_logs = len(self.app.logs)
        self.app._perform_action(idx, action)
        self.assertEqual(len(self.app.logs), before_logs + 1)
        self.assertEqual(self.app.logs[0].name, self.app.game.players[idx].name)
        self.assertIn(idx, self.app.bubbles)
        self.assertTrue(self.app.animation_locked or action == "check")

    def test_render_one_frame(self):
        self.finish_animations()
        self.app._draw()
        self.assertEqual(self.app.canvas.get_size(), (1280, 760))

    def test_animated_state_machine_reaches_hand_end(self):
        self.finish_animations()
        guard = 0
        while not self.app.game.hand_over and guard < 100:
            idx = self.app.game.actor
            legal = self.app.game.legal_actions(idx)
            action = "check" if legal["can_check"] else "call"
            self.app._perform_action(idx, action)
            self.finish_animations()
            guard += 1
        self.assertLess(guard, 100)
        self.assertTrue(self.app.game.hand_over)
        self.assertEqual(self.app.revealed_community, 5)
        self.assertTrue(any(entry.name == "结果" for entry in self.app.logs))


if __name__ == "__main__":
    unittest.main()
