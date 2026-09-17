"""RindenSjakk — per-rendering self-calibration ("bootstrap").

The trained SVM only knows one piece rendering; on a new video it reads the
board empty. But the theme-agnostic template matcher gets a fraction of frames
FULLY legal, and a legal chess position produced by independent per-square
classification is almost never legal by accident with wrong pieces. So legal
frames give trustworthy per-square labels for THIS video's own piece set.

Pipeline: harvest labelled squares from legal template frames -> train a HOG+SVM
on them -> that classifier is tuned to this exact rendering, so it labels the
rest of the frames too. No hand labelling, no new dependencies.

CLI (proof/eval): python engine/bootstrap.py <video> [--interval 1.0]

MÅLT (2026-09-17, Graif-lynparti-video): 98% per-rute hold-out, men lovlig-rate
på hele videoen løftes bare ~13% -> ~13% (0.98^64 ≈ 27% per brett er taket).
Gjenkjenning er FAKTISK korrekt på rene, stabile frames (verifisert mot bildet),
men (a) løper-på-mørk/highlightet-rute flimrer ~50%, og (b) undervisningsvideoer
dveler på stillinger og hopper ikke-lineært, så trekk-KJEDING lyktes ikke (7
metoder testet: rå/template/bootstrap-SVM, eksakt-sprite, helbrett-voting,
per-rute temporal-mode). Beholdt som gjenbrukbart SELV-KALIBRERINGS-mønster for
plattformen (auto-verifiserte utfall -> etiketter), ikke som pålitelig video->PGN.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

import cv2
import numpy as np
import chess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.board_detect import detect_board_bbox, valid_bbox, split_squares
from engine.recognize import image_grid, placement_from_grid, _load_templates
from engine.features import square_to_feature, CLASS_TO_IDX, CLASSES
from engine.process_video import sample_frames


def _legal(placement: str) -> bool:
    try:
        return chess.Board(placement + " w - - 0 1").status() == chess.STATUS_VALID
    except Exception:  # noqa: BLE001
        return False


def _plausible(grid) -> bool:
    """Sanity beyond chess-legality to keep label noise out of training."""
    flat = [c for row in grid for c in row if c != "."]
    if not (2 <= len(flat) <= 32):
        return False
    cnt = Counter(flat)
    if cnt.get("P", 0) > 8 or cnt.get("p", 0) > 8:
        return False
    if cnt.get("K", 0) != 1 or cnt.get("k", 0) != 1:
        return False
    return True


def _grid_is_legal(grid) -> bool:
    return _plausible(grid) and (
        _legal(placement_from_grid(grid, "white")) or _legal(placement_from_grid(grid, "black"))
    )


def harvest(video: str, interval: float = 1.0, templates=None, verbose=True):
    """Return (X, y, n_legal, n_frames): labelled square features from legal frames."""
    tpl = templates or _load_templates()
    X, y = [], []
    n_legal = n_frames = 0
    for _, frame in sample_frames(video, interval, 0.0, None):
        n_frames += 1
        try:
            bbox = detect_board_bbox(frame)
            if not valid_bbox(bbox, frame):
                continue
            grid = image_grid(frame, bbox, tpl)
            if not _grid_is_legal(grid):
                continue
            n_legal += 1
            squares = split_squares(frame, bbox)
            for r in range(8):
                for c in range(8):
                    key = "empty" if grid[r][c] == "." else grid[r][c]
                    X.append(square_to_feature(squares[r][c]))
                    y.append(CLASS_TO_IDX[key])
        except Exception:  # noqa: BLE001 — a bad frame never stops harvesting
            continue
        if verbose and n_frames % 100 == 0:
            print(f"  ...{n_frames} frames, {n_legal} lovlige", file=sys.stderr)
    return np.array(X, np.float32), np.array(y, np.int32), n_legal, n_frames


def _balance(X, y, seed=7):
    """Cap the dominant 'empty' class so the model doesn't inherit empty-bias."""
    empty = CLASS_TO_IDX["empty"]
    piece_idx = np.where(y != empty)[0]
    empty_idx = np.where(y == empty)[0]
    n_keep = min(len(empty_idx), max(300, 2 * len(piece_idx)))
    rng = np.random.RandomState(seed)
    keep = np.concatenate([piece_idx, rng.choice(empty_idx, n_keep, replace=False)]) if len(empty_idx) else piece_idx
    rng.shuffle(keep)
    return X[keep], y[keep]


def train(X, y, out_path, seed=11):
    Xb, yb = _balance(X, y)
    idx = np.random.RandomState(seed).permutation(len(Xb))
    Xb, yb = Xb[idx], yb[idx]
    nt = max(1, len(Xb) // 5)
    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC)
    svm.setKernel(cv2.ml.SVM_RBF)
    svm.setC(12.5)
    svm.setGamma(0.50625)
    svm.train(Xb[nt:], cv2.ml.ROW_SAMPLE, yb[nt:])
    pred = svm.predict(Xb[:nt])[1].flatten().astype(np.int32)
    acc = float((pred == yb[:nt]).mean())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    svm.save(out_path)
    return svm, acc, len(Xb)


def grid_with_svm(frame, bbox, svm):
    squares = split_squares(frame, bbox)
    feats = np.array([square_to_feature(squares[r][c]) for r in range(8) for c in range(8)], np.float32)
    preds = svm.predict(feats)[1].flatten().astype(int)
    return [["." if CLASSES[preds[r * 8 + c]] == "empty" else CLASSES[preds[r * 8 + c]] for c in range(8)] for r in range(8)]


def eval_legal(video, svm, interval, templates, limit=400):
    """Legal-frame rate with the bootstrap SVM vs the template matcher."""
    tpl = templates
    svm_ok = tpl_ok = n = 0
    for _, frame in sample_frames(video, interval, 0.0, None):
        if n >= limit:
            break
        try:
            bbox = detect_board_bbox(frame)
            if not valid_bbox(bbox, frame):
                continue
            n += 1
            gs = grid_with_svm(frame, bbox, svm)
            if _plausible(gs) and (_legal(placement_from_grid(gs, "white")) or _legal(placement_from_grid(gs, "black"))):
                svm_ok += 1
            gt = image_grid(frame, bbox, tpl)
            if _grid_is_legal(gt):
                tpl_ok += 1
        except Exception:  # noqa: BLE001
            continue
    return svm_ok, tpl_ok, n


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a per-video piece classifier.")
    parser.add_argument("video")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    tpl = _load_templates()
    print("høster etiketter fra lovlige template-frames ...", file=sys.stderr)
    X, y, n_legal, n_frames = harvest(args.video, args.interval, tpl)
    print(f"lovlige frames: {n_legal}/{n_frames} -> {len(X)} merkede ruter", file=sys.stderr)
    if n_legal < 5:
        print("FOR FÅ lovlige frames til bootstrap.", file=sys.stderr)
        return 2
    dist = Counter(CLASSES[i] for i in y)
    print("klassefordeling:", dict(dist), file=sys.stderr)
    out = args.out or os.path.join(os.path.dirname(__file__), "models", "bootstrap_tmp.xml")
    svm, acc, ntrain = train(X, y, out)
    print(f"trening: {ntrain} eks (balansert), hold-out {acc*100:.1f}%", file=sys.stderr)
    svm_ok, tpl_ok, n = eval_legal(args.video, svm, args.interval, tpl)
    print(f"LOVLIG-RATE på {n} frames: bootstrap-SVM={svm_ok} ({svm_ok/max(n,1)*100:.0f}%)  vs  template={tpl_ok} ({tpl_ok/max(n,1)*100:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
