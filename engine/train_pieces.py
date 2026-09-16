"""Train a theme-robust piece classifier on SYNTHETIC data.

We composite the cburnett piece templates onto squares of many Lichess board
themes, with the augmentations that make real video frames vary (last-move
highlight, scale/position jitter, blur, noise, brightness). Because we synthesize
exactly the variety that broke template matching, an SVM on HOG features learns
the piece SHAPES independent of board theme.

Run: python engine/train_pieces.py   ->  writes engine/models/piece_svm.xml
"""

from __future__ import annotations

import glob
import os
import random
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.features import CLASS_TO_IDX, CLASSES, square_to_feature

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
SQUARE = 90
SAMPLES_PER_CLASS = 220

# Lichess board themes as (light_BGR, dark_BGR). Covers brown/green/blue/gray/wood.
THEMES = [
    ((181, 217, 240), (99, 136, 181)),    # brown  (f0d9b5 / b58863)
    ((210, 238, 238), (86, 150, 118)),    # green  (eeeed2 / 769656)
    ((230, 227, 222), (173, 162, 140)),   # blue   (dee3e6 / 8ca2ad)
    ((220, 220, 220), (150, 150, 150)),   # gray
    ((206, 233, 247), (130, 168, 200)),   # light wood
    ((196, 216, 235), (110, 145, 175)),   # sandcastle
]
HIGHLIGHTS = [None, (120, 210, 200), (110, 200, 160)]  # None or last-move tint (BGR)


def _load_pieces() -> dict[str, np.ndarray]:
    out = {}
    for path in glob.glob(os.path.join(TEMPLATE_DIR, "*.png")):
        im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if im is None or im.ndim != 3 or im.shape[2] != 4:
            continue
        tag = os.path.splitext(os.path.basename(path))[0]  # 'wK'
        letter = tag[1] if tag[0] == "w" else tag[1].lower()
        out[letter] = im
    return out


def _composite(square_bgr: np.ndarray, piece_rgba: np.ndarray, rng: random.Random) -> np.ndarray:
    scale = rng.uniform(0.70, 0.92)
    s = max(8, int(SQUARE * scale))
    p = cv2.resize(piece_rgba, (s, s), interpolation=cv2.INTER_AREA)
    cx = (SQUARE - s) // 2 + rng.randint(-5, 5)
    cy = (SQUARE - s) // 2 + rng.randint(-5, 5)
    cx = max(0, min(SQUARE - s, cx))
    cy = max(0, min(SQUARE - s, cy))
    alpha = (p[:, :, 3:4].astype(np.float32)) / 255.0
    roi = square_bgr[cy:cy + s, cx:cx + s].astype(np.float32)
    square_bgr[cy:cy + s, cx:cx + s] = (p[:, :, :3].astype(np.float32) * alpha + roi * (1 - alpha)).astype(np.uint8)
    return square_bgr


def _augment(img: np.ndarray, rng: random.Random) -> np.ndarray:
    if rng.random() < 0.35:                                  # last-move highlight
        tint = np.array(rng.choice([h for h in HIGHLIGHTS if h]), np.float32)
        a = rng.uniform(0.15, 0.4)
        img = (img.astype(np.float32) * (1 - a) + tint * a).astype(np.uint8)
    beta = rng.uniform(-25, 25); alpha = rng.uniform(0.85, 1.15)   # brightness/contrast
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    k = rng.choice([1, 1, 3, 3, 5])                          # blur (compression softness)
    if k > 1:
        img = cv2.GaussianBlur(img, (k, k), 0)
    if rng.random() < 0.6:                                   # noise
        img = np.clip(img.astype(np.int16) + rng.randint(3, 10) * np.random.randn(*img.shape).astype(np.int16), 0, 255).astype(np.uint8)
    return img


def _sample(letter: str | None, pieces: dict, rng: random.Random) -> np.ndarray:
    light, dark = rng.choice(THEMES)
    shade = light if rng.random() < 0.5 else dark
    sq = np.zeros((SQUARE, SQUARE, 3), np.uint8)
    sq[:] = shade
    if letter is not None:
        sq = _composite(sq, pieces[letter], rng)
    return _augment(sq, rng)


def build_dataset(rng: random.Random):
    pieces = _load_pieces()
    feats, labels = [], []
    for cls in CLASSES:
        letter = None if cls == "empty" else cls
        for _ in range(SAMPLES_PER_CLASS):
            sq = _sample(letter, pieces, rng)
            feats.append(square_to_feature(sq))
            labels.append(CLASS_TO_IDX[cls])
    return np.array(feats, np.float32), np.array(labels, np.int32)


def main() -> int:
    rng = random.Random(42)
    np.random.seed(42)
    print("genererer syntetisk datasett ...")
    X, y = build_dataset(rng)
    print(f"  {len(X)} eksempler, {X.shape[1]} features/eksempel, {len(CLASSES)} klasser")

    # shuffle + hold-out split for an honest accuracy number
    idx = np.random.permutation(len(X))
    X, y = X[idx], y[idx]
    n_test = len(X) // 5
    Xtr, ytr, Xte, yte = X[n_test:], y[n_test:], X[:n_test], y[:n_test]

    print("trener SVM (RBF) ...")
    svm = cv2.ml.SVM_create()
    svm.setType(cv2.ml.SVM_C_SVC)
    svm.setKernel(cv2.ml.SVM_RBF)
    svm.setC(12.5)
    svm.setGamma(0.50625)
    svm.train(Xtr, cv2.ml.ROW_SAMPLE, ytr)

    pred = svm.predict(Xte)[1].flatten().astype(np.int32)
    acc = float((pred == yte).mean())
    print(f"  hold-out nøyaktighet: {acc*100:.1f}%")

    os.makedirs(MODEL_DIR, exist_ok=True)
    out = os.path.join(MODEL_DIR, "piece_svm.xml")
    svm.save(out)
    print("lagret:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
