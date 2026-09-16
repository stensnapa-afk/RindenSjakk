"""Train the piece classifier on REAL auto-labelled squares.

The template recogniser works on video 1's board theme, so we run it over many
video-1 frames, keep only frames that yield a LEGAL position (labels we can
trust), and harvest every square as a labelled real example. Heavy brightness /
gamma / contrast augmentation makes the grayscale-HOG features generalise across
board themes without needing labelled data from each theme.

Run: python engine/train_real.py <frames_glob> --orientation black
     -> writes engine/models/piece_svm.xml
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import sys

import cv2
import numpy as np
import chess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.board_detect import detect_board_bbox, split_squares
from engine.recognize import image_grid, placement_from_grid, _load_templates
from engine.features import square_to_feature, CLASS_TO_IDX, CLASSES

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
AUG_PER_SQUARE = 4


def collect(frames, orientation, tpl):
    data, kept = [], 0
    for f in frames:
        img = cv2.imread(f)
        if img is None:
            continue
        bbox = detect_board_bbox(img)
        grid = image_grid(img, bbox, tpl)
        pl = placement_from_grid(grid, orientation)
        if pl.count("K") != 1 or pl.count("k") != 1:
            continue
        try:
            if chess.Board(pl + " w - - 0 1").status() != chess.STATUS_VALID:
                continue
        except Exception:  # noqa: BLE001
            continue
        kept += 1
        squares = split_squares(img, bbox)
        for r in range(8):
            for c in range(8):
                ch = grid[r][c]
                data.append((squares[r][c], CLASS_TO_IDX["empty" if ch == "." else ch]))
    return data, kept


def _zoom(img, f):
    """Simulate different piece-fill fractions (board pixel size varies per video)."""
    h, w = img.shape[:2]
    if abs(f - 1) < 0.02:
        return img
    if f > 1:                                    # zoom in -> piece bigger
        ch, cw = int(h / f), int(w / f)
        y, x = (h - ch) // 2, (w - cw) // 2
        return cv2.resize(img[y:y + ch, x:x + cw], (w, h))
    nh, nw = int(h * f), int(w * f)              # zoom out -> piece smaller, border padded
    small = cv2.resize(img, (nw, nh))
    canvas = np.zeros_like(img)
    canvas[:] = np.median(img.reshape(-1, img.shape[2]), axis=0).astype(np.uint8)
    y, x = (h - nh) // 2, (w - nw) // 2
    canvas[y:y + nh, x:x + nw] = small
    return canvas


def augment(sq, rng):
    out = []
    for _ in range(AUG_PER_SQUARE):
        img = _zoom(sq.copy(), rng.uniform(0.92, 1.12))             # mild piece-scale jitter
        g = rng.uniform(0.55, 1.7)                                   # gamma (theme brightness)
        img = (((img.astype(np.float32) / 255.0) ** g) * 255).astype(np.uint8)
        img = cv2.convertScaleAbs(img, alpha=rng.uniform(0.8, 1.2), beta=rng.uniform(-30, 30))
        if rng.random() < 0.4:
            img = cv2.GaussianBlur(img, (3, 3), 0)
        out.append(square_to_feature(img))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames_glob")
    parser.add_argument("--orientation", default="black")
    parser.add_argument("--test_glob", default=None)
    args = parser.parse_args()

    rng = random.Random(7)
    tpl = _load_templates()
    frames = sorted(glob.glob(args.frames_glob))
    print(f"auto-merker {len(frames)} frames ...")
    data, kept = collect(frames, args.orientation, tpl)
    print(f"  {kept} lovlige frames -> {len(data)} ruter")
    if not data:
        print("ingen data", file=sys.stderr)
        return 1

    X, y = [], []
    for sq, lbl in data:
        for feat in augment(sq, rng):
            X.append(feat); y.append(lbl)
    X = np.array(X, np.float32); y = np.array(y, np.int32)
    print(f"  {len(X)} augmenterte eksempler")

    idx = np.random.RandomState(7).permutation(len(X))
    X, y = X[idx], y[idx]
    nt = len(X) // 5
    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC)
    svm.setKernel(cv2.ml.SVM_RBF)
    svm.setC(12.5); svm.setGamma(0.50625)
    svm.train(X[nt:], cv2.ml.ROW_SAMPLE, y[nt:])
    acc = float((svm.predict(X[:nt])[1].flatten().astype(np.int32) == y[:nt]).mean())
    print(f"  hold-out (samme tema): {acc*100:.1f}%")

    os.makedirs(MODEL_DIR, exist_ok=True)
    out = os.path.join(MODEL_DIR, "piece_svm.xml")
    svm.save(out)
    print("lagret:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
