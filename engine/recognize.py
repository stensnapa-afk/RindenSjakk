"""RindenSjakk Fase 2 — classify each board square to a FEN placement.

Uses the cburnett templates (engine/templates/, fetched by gen_templates.py) and
masked normalised cross-correlation: only the piece silhouette (template alpha)
is compared, so the two board colours and the last-move highlight tint don't
matter. Empty squares are caught first by low variance (board_detect).

CLI: python engine/recognize.py <frame.png> [--orientation white|black]
     -> prints the detected placement as an ASCII board + FEN field 1.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.board_detect import detect_board_bbox, split_squares, square_has_piece, _center

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
CANON = 96  # canonical match size


def _load_templates() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """tag ('wK'..'bP') -> (gray float32 CANONxCANON, bool mask), cropped tight
    to the piece (alpha bbox) so scale/position matches the board-piece crop."""
    out = {}
    for path in sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.png"))):
        im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if im is None:
            continue
        if im.ndim == 3 and im.shape[2] == 4:
            alpha = im[:, :, 3]
            gray = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            alpha = np.full(im.shape[:2], 255, np.uint8)
            gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) if im.ndim == 3 else im
        ys, xs = np.where(alpha > 64)
        if len(xs) < 10:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        gray = gray[y0:y1 + 1, x0:x1 + 1]
        alpha = alpha[y0:y1 + 1, x0:x1 + 1]
        gray = cv2.resize(gray, (CANON, CANON)).astype(np.float32)
        alpha = cv2.resize(alpha, (CANON, CANON))
        tag = os.path.splitext(os.path.basename(path))[0]  # e.g. 'wK'
        out[tag] = (gray, alpha > 64)
    return out


def _piece_crop(sq: np.ndarray) -> np.ndarray | None:
    """Isolate the piece by its contrast against the (uniform) square background,
    return a tight grayscale crop of the piece — or None if too little foreground."""
    c = _center(sq, 0.86)
    if c.size == 0:
        return None
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
    bg = float(np.median(border))
    fg = (np.abs(gray.astype(np.float32) - bg) > 35).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.where(fg > 0)
    if len(xs) < 25:
        return None
    return gray[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _tag_to_fen(tag: str) -> str:
    letter = tag[1]                      # 'K'..'P'
    return letter if tag[0] == "w" else letter.lower()


def _masked_ncc(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    av = a[mask]; bv = b[mask]
    av = av - av.mean(); bv = bv - bv.mean()
    da = np.sqrt((av * av).sum()); db = np.sqrt((bv * bv).sum())
    if da < 1e-6 or db < 1e-6:
        return -1.0
    return float((av * bv).sum() / (da * db))


def classify_square(sq: np.ndarray, templates: dict) -> tuple[str | None, float]:
    """Return (fen_char or None for empty, score)."""
    if not square_has_piece(sq):
        return None, 0.0
    crop = _piece_crop(sq)
    if crop is None:
        return None, 0.0
    gray = cv2.resize(crop, (CANON, CANON)).astype(np.float32)
    best_tag, best = None, -2.0
    for tag, (tg, mask) in templates.items():
        s = _masked_ncc(gray, tg, mask)
        if s > best:
            best, best_tag = s, tag
    return (_tag_to_fen(best_tag) if best_tag else None), best


def image_grid(img: np.ndarray, bbox, templates) -> list[list[str]]:
    """8x8 grid of fen chars ('.' = empty), row 0 = top of the image."""
    squares = split_squares(img, bbox)
    grid = []
    for r in range(8):
        row = []
        for c in range(8):
            ch, _ = classify_square(squares[r][c], templates)
            row.append(ch if ch else ".")
        grid.append(row)
    return grid


def placement_from_grid(grid: list[list[str]], orientation: str) -> str:
    """Map the image grid to a FEN placement field given board orientation.

    'white': image (r,c) -> rank 8-r, file c(0=a).  'black' (board flipped,
    White at top): image (r,c) -> rank r+1, file 7-c.
    """
    board = {}
    for r in range(8):
        for c in range(8):
            if orientation == "black":
                rank, file = r + 1, 7 - c
            else:
                rank, file = 8 - r, c
            board[(file, rank)] = grid[r][c]
    rows = []
    for rank in range(8, 0, -1):
        row, empty = "", 0
        for file in range(8):
            ch = board[(file, rank)]
            if ch == ".":
                empty += 1
            else:
                if empty:
                    row += str(empty); empty = 0
                row += ch
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows)


def recognize_placement(img: np.ndarray, orientation: str = "white",
                        templates: dict | None = None) -> str:
    templates = templates or _load_templates()
    bbox = detect_board_bbox(img)
    grid = image_grid(img, bbox, templates)
    return placement_from_grid(grid, orientation)


def _ascii(placement: str) -> str:
    lines = []
    for row in placement.split("/"):
        line = ""
        for ch in row:
            line += "." * int(ch) if ch.isdigit() else ch
        lines.append(" ".join(line))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Classify a frame's board to a FEN placement.")
    parser.add_argument("frame")
    parser.add_argument("--orientation", choices=["white", "black"], default="white")
    args = parser.parse_args(argv)
    img = cv2.imread(args.frame)
    if img is None:
        print("could not read:", args.frame, file=sys.stderr)
        return 1
    placement = recognize_placement(img, args.orientation)
    print("placement:", placement)
    print(_ascii(placement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
