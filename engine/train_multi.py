"""Train a piece classifier that covers MULTIPLE board renderings, reliably.

Two label sources, both trustworthy (no hand transcription):
  1. Real auto-labelled squares from a video the template recogniser handles
     (only legal-FEN frames kept) — real pieces, real rendering.
  2. For a NEW rendering we cannot yet recognise: harvest its REAL empty squares
     (empty detection is theme-robust) and composite the cburnett templates onto
     those real backgrounds. This puts the new theme/texture/compression in the
     training distribution with perfect labels.

Run: python engine/train_multi.py --label_glob <v1 frames> --bg_glob <v5 frames>
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

from engine.board_detect import detect_board_bbox, split_squares, square_has_piece
from engine.recognize import image_grid, placement_from_grid, _load_templates
from engine.features import square_to_feature, CLASS_TO_IDX, CLASSES
from engine.train_real import collect, augment
from engine.train_pieces import _load_pieces, _composite, _augment

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
SQUARE = 90


def harvest_empties(frames, limit=600):
    """Real empty-square BGR crops (resized to SQUARE) from the new rendering."""
    out = []
    for f in frames:
        img = cv2.imread(f)
        if img is None:
            continue
        bbox = detect_board_bbox(img)
        squares = split_squares(img, bbox)
        for r in range(8):
            for c in range(8):
                if not square_has_piece(squares[r][c]):
                    out.append(cv2.resize(squares[r][c], (SQUARE, SQUARE)))
                    if len(out) >= limit:
                        return out
    return out


def composite_on_real(empties, pieces, rng, per_class=260):
    """For each piece class, composite templates onto real empty backgrounds."""
    feats, labels = [], []
    for letter, piece in pieces.items():
        for _ in range(per_class):
            bg = empties[rng.randrange(len(empties))].copy()
            sq = _composite(bg, piece, rng)
            sq = _augment(sq, rng)
            feats.append(square_to_feature(sq))
            labels.append(CLASS_TO_IDX[letter])
    return feats, labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label_glob", required=True)   # video handled by templates (v1)
    parser.add_argument("--bg_glob", required=True)       # new rendering to cover (v5)
    parser.add_argument("--orientation", default="black")
    args = parser.parse_args()

    rng = random.Random(11)
    np.random.seed(11)
    tpl = _load_templates()
    pieces = _load_pieces()

    # 1) real auto-labelled squares (video 1)
    label_frames = sorted(glob.glob(args.label_glob))
    print(f"auto-merker {len(label_frames)} v1-frames ...")
    real, kept = collect(label_frames, args.orientation, tpl)
    print(f"  {kept} lovlige -> {len(real)} ruter")
    X, y = [], []
    for sq, lbl in real:
        for feat in augment(sq, rng):
            X.append(feat); y.append(lbl)

    # 2) real empty backgrounds (video 5) + composites + real empties as 'empty'
    bg_frames = sorted(glob.glob(args.bg_glob))
    print(f"høster tomme ruter fra {len(bg_frames)} v5-frames ...")
    empties = harvest_empties(bg_frames)
    print(f"  {len(empties)} ekte tomme v5-bakgrunner")
    if empties:
        cf, cl = composite_on_real(empties, pieces, rng)
        X.extend(cf); y.extend(cl)
        for bg in empties:                                  # real empties -> 'empty' class
            for _ in range(3):
                X.append(square_to_feature(_augment(bg.copy(), rng)))
                y.append(CLASS_TO_IDX["empty"])

    X = np.array(X, np.float32); y = np.array(y, np.int32)
    print(f"  totalt {len(X)} eksempler")
    idx = np.random.RandomState(11).permutation(len(X))
    X, y = X[idx], y[idx]
    nt = len(X) // 5
    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC); svm.setKernel(cv2.ml.SVM_RBF)
    svm.setC(12.5); svm.setGamma(0.50625)
    svm.train(X[nt:], cv2.ml.ROW_SAMPLE, y[nt:])
    acc = float((svm.predict(X[:nt])[1].flatten().astype(np.int32) == y[:nt]).mean())
    print(f"  hold-out (blandet): {acc*100:.1f}%")

    os.makedirs(MODEL_DIR, exist_ok=True)
    out = os.path.join(MODEL_DIR, "piece_svm.xml")
    svm.save(out)
    print("lagret:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
