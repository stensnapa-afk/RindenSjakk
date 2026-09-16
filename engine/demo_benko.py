"""Demo: reconstruct a Benko-Gambit repertoire fragment (main line + one
variation from a takeback) and write the PGN tree to demo_benko.pgn.

Run: python engine/demo_benko.py   (from projects/rindensjakk)
"""

import os
import sys

import chess
import chess.pgn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.fen_tree import build_tree


def line_placements(sans):
    board = chess.Board()
    out = []
    for san in sans:
        board.push_san(san)
        out.append(board.board_fen())
    return out


def main():
    mainline = ["d4", "Nf6", "c4", "c5", "d5", "b5", "cxb5", "a6", "bxa6"]
    placements = line_placements(mainline)
    placements.append(placements[-1])            # duplicate frame (noise)
    placements.append(placements[5])             # takeback to after 3...b5
    placements.append(line_placements(mainline[:6] + ["Nf3"])[-1])  # 4.Nf3 variation

    game, stats = build_tree(placements)
    game.headers["White"] = "The Gambit Man"
    game.headers["Black"] = "Repertoire"

    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    pgn = game.accept(exporter)

    out_path = os.path.join(os.path.dirname(__file__), "demo_benko.pgn")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(pgn + "\n")

    print(pgn)
    print("\n; stats:", stats)
    print(";wrote:", out_path)


if __name__ == "__main__":
    main()
