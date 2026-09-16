"""Shared feature extraction for the trained piece classifier.

A board square -> HOG vector, using a fixed centre crop (no fragile piece
segmentation). Training and runtime MUST use the exact same transform, so it
lives here and both import it.
"""

import cv2
import numpy as np

# 13 classes: empty + 6 white + 6 black (FEN letters). Order is the SVM label order.
CLASSES = ["empty", "P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

CROP_FRAC = 0.86     # trim grid-line bleed + edge coordinate labels
CANON = 64

_HOG = cv2.HOGDescriptor((CANON, CANON), (16, 16), (8, 8), (8, 8), 9)


def square_to_feature(bgr_square: np.ndarray) -> np.ndarray:
    """Centre-crop -> grayscale -> 64x64 -> HOG (contrast-normalised => theme-robust)."""
    h, w = bgr_square.shape[:2]
    my, mx = int(h * (1 - CROP_FRAC) / 2), int(w * (1 - CROP_FRAC) / 2)
    c = bgr_square[my:h - my, mx:w - mx]
    if c.size == 0:
        c = bgr_square
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (CANON, CANON))
    return _HOG.compute(gray).flatten()
