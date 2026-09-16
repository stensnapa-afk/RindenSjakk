"""RindenSjakk core: reconstruct a PGN repertoire *tree* from a timeline of
observed board placements.

The upstream board-CV stage (Fase 2) can only read the *piece placement* of the
board in each video frame -- it cannot see whose move it is, castling rights or
en-passant targets. This module infers everything else with the chess rules
engine: from the current node it plays only *legal* moves and matches the one
whose resulting placement equals the observed one. Illegal readings therefore
cannot survive.

The repertoire tree (main line + the side variations the presenter demonstrates)
is not parsed from narration -- it falls out mechanically: when the observed
position returns to one already seen and a *different* next move is played, that
is, by definition, a variation branching from that node.

Input:  an ordered list of placement strings (FEN field 1, e.g.
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"). Full FENs are accepted;
        only the first field is used.
Output: a `chess.pgn.Game` with variations, exportable straight to PGN.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

import chess
import chess.pgn


def _placement(fen_or_placement: str) -> str:
    """Normalize an input entry to the bare piece-placement field."""
    return fen_or_placement.strip().split(" ")[0]


def _find_sequence(board: chess.Board, target: str, max_depth: int) -> list[chess.Move] | None:
    """Shortest sequence of legal moves (1..max_depth plies) from `board` whose
    resulting placement equals `target`, or None if unreachable within depth.

    Iterative deepening guarantees the shortest bridge, so a single missed frame
    (one move) is preferred over spurious multi-move paths. Legality prunes the
    search hard, so even depth 2-3 stays cheap.
    """

    budget = [20000]  # cap total expansions so deep searches can't explode (~35^n)

    def dfs_exact(b: chess.Board, remaining: int) -> list[chess.Move] | None:
        if remaining == 0:
            return [] if b.board_fen() == target else None
        for move in b.legal_moves:
            if budget[0] <= 0:
                return None
            budget[0] -= 1
            b.push(move)
            sub = dfs_exact(b, remaining - 1)
            b.pop()
            if sub is not None:
                return [move] + sub
        return None

    probe = board.copy(stack=False)
    for depth in range(1, max_depth + 1):
        seq = dfs_exact(probe, depth)
        if seq is not None:
            return seq
        if budget[0] <= 0:
            break
    return None


def _pick_return(candidates: list[chess.pgn.GameNode], current: chess.pgn.GameNode) -> chess.pgn.GameNode:
    """Choose which existing node a 'jump' returned to.

    Prefer an ancestor of the current node (a genuine takeback along the current
    line); otherwise fall back to the most recently created match. Placement-only
    identity means transpositions can collide -- documented limitation for v0.
    """
    ancestors: set[int] = set()
    node: chess.pgn.GameNode | None = current
    while node is not None:
        ancestors.add(id(node))
        node = node.parent
    for cand in candidates:
        if id(cand) in ancestors:
            return cand
    return candidates[-1]


def build_tree(placements: Iterable[str], max_bridge: int = 2,
               root_fen: str | None = None) -> tuple[chess.pgn.Game, dict[str, int]]:
    """Reconstruct a PGN variation tree from an ordered placement timeline.

    `max_bridge` is how many missed plies the reconstruction will span with a
    legal-move search before treating a discontinuity as a jump/return.

    `root_fen` seeds the starting position. Leave it None for a game shown from
    the initial array (repertoire videos); pass a full FEN to start mid-game
    (e.g. a live game whose opening happened before the first sampled frame),
    otherwise the first observation is unreachable from the standard start and
    the whole timeline degrades to gaps.
    """
    game = chess.pgn.Game()
    game.headers["Event"] = "RindenSjakk import"
    game.headers["Site"] = "video"
    if root_fen:
        game.setup(chess.Board(root_fen))

    current: chess.pgn.GameNode = game
    # placement -> nodes reaching it, for return/jump detection.
    seen: dict[str, list[chess.pgn.GameNode]] = {}
    seen.setdefault(game.board().board_fen(), []).append(game)

    stats = {
        "observations": 0,
        "moves": 0,
        "returns": 0,
        "variations": 0,
        "gaps": 0,
        "duplicates": 0,
    }

    def apply_sequence(node: chess.pgn.GameNode, moves: list[chess.Move]) -> chess.pgn.GameNode:
        for move in moves:
            if node.has_variation(move):
                node = node.variation(move)
            else:
                first_child = len(node.variations) == 0
                node = node.add_variation(move)
                if not first_child:
                    stats["variations"] += 1
            seen.setdefault(node.board().board_fen(), []).append(node)
            stats["moves"] += 1
        return node

    for raw in placements:
        target = _placement(raw)
        stats["observations"] += 1

        if target == current.board().board_fen():
            stats["duplicates"] += 1
            continue

        seq = _find_sequence(current.board(), target, max_bridge)
        if seq is not None:
            current = apply_sequence(current, seq)
            continue

        # No legal bridge from here: a jump. Did we already reach this position?
        if seen.get(target):
            current = _pick_return(seen[target], current)
            stats["returns"] += 1
            continue

        # Unseen and unbridged: maybe he reset to the start and entered a new
        # line -- try to reach it from the root (a top-level repertoire branch).
        root_seq = _find_sequence(game.board(), target, max_bridge)
        if root_seq is not None:
            current = apply_sequence(game, root_seq)
            continue

        stats["gaps"] += 1

    return game, stats


def _read_placements(source: Iterable[str]) -> list[str]:
    return [line for line in (raw.strip() for raw in source) if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconstruct a PGN tree from a placement timeline.")
    parser.add_argument(
        "path",
        nargs="?",
        help="File with one placement (FEN field 1) per line. Reads stdin if omitted.",
    )
    parser.add_argument("--max-bridge", type=int, default=2, help="Max plies to bridge a missed frame.")
    args = parser.parse_args(argv)

    if args.path:
        with open(args.path, "r", encoding="utf-8") as handle:
            placements = _read_placements(handle)
    else:
        placements = _read_placements(sys.stdin)

    if not placements:
        print("No placements provided.", file=sys.stderr)
        return 1

    game, stats = build_tree(placements, max_bridge=args.max_bridge)
    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    print(game.accept(exporter))
    summary = ", ".join(f"{key}={value}" for key, value in stats.items())
    print(f"\n; stats: {summary}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
