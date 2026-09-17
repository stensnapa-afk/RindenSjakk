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

from engine.board_detect import detect_board_bbox, split_squares, square_has_piece, _center, valid_bbox

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
    # per-type silhouette (shape only, colour-agnostic) from the white pieces.
    types = {}
    for letter in "KQRBNP":
        wt = out.get("w" + letter)
        if wt is not None:
            types[letter] = wt[1]
    out["_types"] = types
    return out


def _piece_crop(sq: np.ndarray):
    """Isolate the piece as a filled silhouette, returned as (gray_crop, mask_crop)
    tight to the bbox, or None if no piece.

    Built from the piece OUTLINE via Canny edges + filled contour. The dark
    cburnett outline always contrasts with the square, so this is robust across
    board themes and to white-on-light / dark-on-dark blending that defeats a
    background-difference threshold."""
    c = _center(sq, 0.9)
    if c.size == 0:
        return None
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    big = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(big) < gray.size * 0.03:
        return None
    mask = np.zeros(gray.shape, np.uint8)
    cv2.drawContours(mask, [big], -1, 255, thickness=cv2.FILLED)
    ys, xs = np.where(mask > 0)
    if len(xs) < 25:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    return gray[y0:y1 + 1, x0:x1 + 1], mask[y0:y1 + 1, x0:x1 + 1] > 0


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
    res = _piece_crop(sq)
    if res is None:
        return None, 0.0
    gray_c, mask_c = res
    g = cv2.resize(gray_c, (CANON, CANON)).astype(np.float32)
    m = cv2.resize(mask_c.astype(np.uint8), (CANON, CANON), interpolation=cv2.INTER_NEAREST).astype(bool)

    # 1) type by silhouette IoU (robust to fill brightness / compression).
    best_letter, best_iou = None, -1.0
    for letter, tm in templates["_types"].items():
        inter = float(np.logical_and(m, tm).sum())
        union = float(np.logical_or(m, tm).sum())
        iou = inter / union if union else 0.0
        if iou > best_iou:
            best_iou, best_letter = iou, letter
    if best_letter is None:
        return None, 0.0

    # 2) colour: white cburnett pieces have a light fill, black pieces do not.
    #    Fraction of piece pixels that are bright separates them cleanly and is
    #    self-calibrating (independent of the square colour underneath).
    interior = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=2)
    sample = g[interior > 0] if int(interior.sum()) >= 8 else g[m]
    med = float(np.median(sample)) if sample.size else 0.0
    color = "w" if med > 120 else "b"
    char = best_letter if color == "w" else best_letter.lower()
    return char, best_iou


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


_SVM = None


def _svm():
    """Lazy-load the trained piece classifier (theme-robust). False if absent."""
    global _SVM
    if _SVM is None:
        path = os.path.join(os.path.dirname(__file__), "models", "piece_svm.xml")
        _SVM = cv2.ml.SVM_load(path) if os.path.exists(path) else False
    return _SVM


def image_grid_svm(img: np.ndarray, bbox) -> list[list[str]]:
    """8x8 grid of fen chars via the trained HOG+SVM classifier (batched)."""
    from engine.features import square_to_feature, CLASSES
    svm = _svm()
    squares = split_squares(img, bbox)
    feats = np.array([square_to_feature(squares[r][c]) for r in range(8) for c in range(8)], np.float32)
    preds = svm.predict(feats)[1].flatten().astype(int)
    grid = []
    for r in range(8):
        grid.append(["." if CLASSES[preds[r * 8 + c]] == "empty" else CLASSES[preds[r * 8 + c]] for c in range(8)])
    return grid


def recognize_placement(img: np.ndarray, orientation: str = "white",
                        templates: dict | None = None) -> str:
    bbox = detect_board_bbox(img)
    if not valid_bbox(bbox, img):               # no board in this frame -> empty
        return "8/8/8/8/8/8/8/8"
    if _svm():                                  # trained classifier preferred
        grid = image_grid_svm(img, bbox)
    else:                                        # fallback: template IoU
        templates = templates or _load_templates()
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
