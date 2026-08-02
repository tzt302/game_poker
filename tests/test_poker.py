import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from neon_holdem.engine import Card, HoldemGame, evaluate_seven


def cards(text: str):
    return [Card(token[0], token[1]) for token in text.split()]


class HandEvaluationTests(unittest.TestCase):
    def test_straight_flush_beats_quads(self):
        straight_flush = evaluate_seven(cards("As Ks Qs Js Ts 2d 3c"))
        quads = evaluate_seven(cards("Ah Ad Ac As Kd 2c 3s"))
        self.assertGreater(straight_flush, quads)
        self.assertEqual(straight_flush.name, "同花顺")

    def test_wheel_straight(self):
        result = evaluate_seven(cards("As 2d 3c 4h 5s Kd Qd"))
        self.assertEqual(result.name, "顺子")
        self.assertEqual(result.kickers, (5,))

    def test_two_pair_kicker(self):
        ace = evaluate_seven(cards("Ah Ad Kc Kd Qs 3h 2c"))
        jack = evaluate_seven(cards("As Ac Kh Ks Jd 3c 2h"))
        self.assertGreater(ace, jack)


class GameFlowTests(unittest.TestCase):
    def test_random_deal_has_no_duplicates(self):
        game = HoldemGame(seed=7)
        dealt = [card for player in game.players for card in player.cards]
        self.assertEqual(len(dealt), len(set(dealt)))

    def test_everyone_folding_awards_pot(self):
        game = HoldemGame(seed=1)
        while not game.hand_over:
            idx = game.actor
            if idx is None:
                break
            if idx == 0:
                game.act(idx, "call")
            else:
                game.act(idx, "fold")
        self.assertTrue(game.hand_over)
        self.assertEqual(len(game.winners), 1)

    def test_calling_down_reaches_showdown(self):
        game = HoldemGame(seed=4)
        guard = 0
        while not game.hand_over and guard < 100:
            idx = game.actor
            legal = game.legal_actions(idx)
            game.act(idx, "check" if legal["can_check"] else "call")
            guard += 1
        self.assertTrue(game.hand_over)
        self.assertEqual(len(game.community), 5)


if __name__ == "__main__":
    unittest.main()
