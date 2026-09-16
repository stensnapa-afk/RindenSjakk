"""Unit tests for the RindenSjakk placement-timeline -> PGN-tree core.

Run: python -m unittest discover -s tests   (from projects/rindensjakk)

The tests build a synthetic timeline with python-chess (so it is self-consistent
with the rules engine), then assert the reconstruction recovers the main line,
splits a takeback into a variation, and tolerates duplicate/noise frames.
"""

import os
import sys
import unittest

import chess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.fen_tree import build_tree  # noqa: E402


def _line_placements(sans: list[str]) -> list[str]:
    board = chess.Board()
    placements = []
    for san in sans:
        board.push_san(san)
        placements.append(board.board_fen())
    return placements


class BuildTreeTest(unittest.TestCase):
    MAINLINE = ["d4", "Nf6", "c4", "c5", "d5", "b5", "cxb5", "a6", "bxa6"]

    def _timeline_with_variation(self) -> list[str]:
        """Benko main line, a duplicate noise frame, a takeback to after ...b5,
        then a different 4th move (4.Nf3) forming a variation."""
        placements = _line_placements(self.MAINLINE)
        placements.append(placements[-1])            # duplicate frame (noise)
        after_b5 = placements[5]                      # position after 3...b5
        placements.append(after_b5)                   # takeback / return
        variation = _line_placements(["d4", "Nf6", "c4", "c5", "d5", "b5", "Nf3"])
        placements.append(variation[-1])              # 4.Nf3 branch
        return placements

    def _node_after_moves(self, game, sans: list[str]):
        board = chess.Board()
        node = game
        for san in sans:
            move = board.push_san(san)
            self.assertTrue(node.has_variation(move), f"missing node for {san}")
            node = node.variation(move)
        return node

    def test_mainline_recovered(self):
        placements = _line_placements(self.MAINLINE)
        game, stats = build_tree(placements)
        board = chess.Board()
        sans = []
        for move in game.mainline_moves():
            sans.append(board.san(move))
            board.push(move)
        self.assertEqual(sans, self.MAINLINE)
        self.assertEqual(stats["gaps"], 0)
        self.assertEqual(stats["moves"], len(self.MAINLINE))

    def test_takeback_becomes_variation(self):
        placements = self._timeline_with_variation()
        game, stats = build_tree(placements)

        # Main line still fully intact.
        board = chess.Board()
        sans = []
        for move in game.mainline_moves():
            sans.append(board.san(move))
            board.push(move)
        self.assertEqual(sans, self.MAINLINE)

        # Node after 3...b5 must carry two continuations: mainline cxb5 + variation Nf3.
        node = self._node_after_moves(game, ["d4", "Nf6", "c4", "c5", "d5", "b5"])
        variation_sans = []
        for child in node.variations:
            variation_sans.append(node.board().san(child.move))
        self.assertIn("cxb5", variation_sans)
        self.assertIn("Nf3", variation_sans)
        self.assertEqual(len(node.variations), 2)

        # Bookkeeping.
        self.assertGreaterEqual(stats["duplicates"], 1)
        self.assertGreaterEqual(stats["returns"], 1)
        self.assertGreaterEqual(stats["variations"], 1)
        self.assertEqual(stats["gaps"], 0)

    def test_bridges_single_missed_frame(self):
        """A dropped frame (two moves between observations) is bridged by legality."""
        full = _line_placements(self.MAINLINE)
        dropped = full[:3] + full[4:]  # remove one intermediate placement
        game, stats = build_tree(dropped, max_bridge=2)
        board = chess.Board()
        sans = []
        for move in game.mainline_moves():
            sans.append(board.san(move))
            board.push(move)
        self.assertEqual(sans, self.MAINLINE)
        self.assertEqual(stats["gaps"], 0)

    def test_all_moves_legal_by_construction(self):
        """The reconstructed line must be a legal game from the start position."""
        placements = self._timeline_with_variation()
        game, _ = build_tree(placements)
        board = chess.Board()
        for move in game.mainline_moves():
            self.assertIn(move, board.legal_moves)
            board.push(move)


if __name__ == "__main__":
    unittest.main()
