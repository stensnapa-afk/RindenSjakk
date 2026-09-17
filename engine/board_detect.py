"""RindenSjakk Fase 2 — locate the Lichess board in a video frame.

The board is Lichess' fixed UI: a square 8x8 grid of two alternating colours on
the left, with a dark side panel (clocks / move list / facecam) to the right. We
find the board box from brightness profiles (board columns/rows are bright and
alternating; the panel is dark), constrain it to a square, and expose an 8x8
split. Orientation (which corner is a1) is handled downstream.

CLI: python engine/board_detect.py <frame.png> [--out overlay.png]
     -> prints detected box + saves an overlay with the 8x8 grid drawn.
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np


def detect_board_bbox(img: np.ndarray, bright_thr: float = 95.0) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) of the board, constrained to a square.

    Strategy: the board sits on the left. A column that crosses the board mixes
    bright (light squares) and mid (dark squares) rows, so its mean brightness is
    clearly above the dark side panel. We take the contiguous bright run from the
    left edge as the board's horizontal span, then the bright run vertically
    within that span, then square it off on the smaller side.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape

    col_mean = gray.mean(axis=0)
    bright_cols = col_mean > bright_thr
    # horizontal board span = first contiguous bright run starting near the left.
    x0 = int(np.argmax(bright_cols))                 # first bright column
    x1 = x0
    for x in range(x0, w):
        if bright_cols[x]:
            x1 = x
        elif x1 - x0 > w * 0.15:                      # long enough run -> stop at first gap
            break
    # vertical span, measured only over the board's columns.
    row_mean = gray[:, x0:x1 + 1].mean(axis=1)
    bright_rows = row_mean > bright_thr
    y0 = int(np.argmax(bright_rows))
    y1 = y0
    for y in range(y0, h):
        if bright_rows[y]:
            y1 = y
        elif y1 - y0 > h * 0.2:
            break

    # square it off on the smaller dimension, anchored at the top-left.
    side = min(x1 - x0, y1 - y0)
    return x0, y0, x0 + side, y0 + side


def valid_bbox(bbox: tuple[int, int, int, int], img: np.ndarray) -> bool:
    """True if the detected board box is plausibly a real board and inside the
    frame. A board-less frame (intro / talking head) yields a tiny degenerate
    run; splitting that gives zero-size squares that crash cvtColor downstream.
    A real Lichess board is a large square (~700px on 720p), so a modest floor
    rejects the garbage without touching real boards."""
    x0, y0, x1, y1 = bbox
    h, w = img.shape[:2]
    side = min(x1 - x0, y1 - y0)
    return side >= 96 and 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h


def split_squares(img: np.ndarray, bbox: tuple[int, int, int, int]) -> list[list[np.ndarray]]:
    """Return an 8x8 grid of square sub-images, row 0 = top of the image."""
    x0, y0, x1, y1 = bbox
    step = (x1 - x0) / 8.0
    grid = []
    for r in range(8):
        row = []
        for c in range(8):
            sx = int(x0 + c * step); sy = int(y0 + r * step)
            ex = int(x0 + (c + 1) * step); ey = int(y0 + (r + 1) * step)
            row.append(img[sy:ey, sx:ex])
        grid.append(row)
    return grid


def _center(sq: np.ndarray, frac: float = 0.72) -> np.ndarray:
    """Center crop of a square, trimming grid-line bleed and coordinate labels."""
    h, w = sq.shape[:2]
    my, mx = int(h * (1 - frac) / 2), int(w * (1 - frac) / 2)
    return sq[my:h - my, mx:w - mx]


def square_has_piece(sq: np.ndarray, std_thr: float = 22.0) -> bool:
    """A square holds a piece if its centre has high intensity variance.

    Empty squares (including last-move highlight tints) are near-flat colour ->
    low std. A piece adds a dark outline + light/dark interior -> high std.
    """
    c = _center(sq)
    if c.size == 0:
        return False
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    return float(gray.std()) > std_thr


def board_occupancy(img: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """8x8 boolean occupancy grid (row 0 = top of the image)."""
    grid = split_squares(img, bbox)
    occ = np.zeros((8, 8), dtype=bool)
    for r in range(8):
        for c in range(8):
            occ[r, c] = square_has_piece(grid[r][c])
    return occ


def is_startpos(occ: np.ndarray) -> bool:
    """True if occupancy matches the initial array: two full ranks top and bottom,
    four empty ranks in the middle (orientation-independent)."""
    top_full = occ[0].all() and occ[1].all()
    bot_full = occ[6].all() and occ[7].all()
    middle_empty = not occ[2:6].any()
    return bool(top_full and bot_full and middle_empty)


def draw_overlay(img: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    out = img.copy()
    x0, y0, x1, y1 = bbox
    step = (x1 - x0) / 8.0
    for i in range(9):
        p = int(x0 + i * step)
        cv2.line(out, (p, y0), (p, y1), (40, 90, 220), 1)
        q = int(y0 + i * step)
        cv2.line(out, (x0, q), (x1, q), (40, 90, 220), 1)
    cv2.rectangle(out, (x0, y0), (x1, y1), (60, 200, 90), 2)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Locate the Lichess board in a frame.")
    parser.add_argument("frame")
    parser.add_argument("--out", default=None, help="Path to save the grid overlay.")
    args = parser.parse_args(argv)

    img = cv2.imread(args.frame)
    if img is None:
        print("could not read:", args.frame, file=sys.stderr)
        return 1
    bbox = detect_board_bbox(img)
    x0, y0, x1, y1 = bbox
    print(f"frame {img.shape[1]}x{img.shape[0]} -> board bbox x0={x0} y0={y0} x1={x1} y1={y1} side={x1 - x0}")
    if args.out:
        cv2.imwrite(args.out, draw_overlay(img, bbox))
        print("overlay:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
