"""Fetch the cburnett piece set (the default Lichess pieces) as transparent PNG
templates, once, into engine/templates/. Runtime matching then needs only these
PNGs — no SVG/rendering dependency.

The artwork is Colin M.L. Burnett's set, identical to what Lichess renders; the
same files back Wikipedia's chess pieces, so we pull them from Wikimedia's
Special:FilePath (renders the SVG to PNG at a requested width).

Run once: python engine/gen_templates.py
"""

from __future__ import annotations

import os
import sys
import urllib.request

# piece letter (FEN) -> Wikimedia Commons cburnett file (l = light/white, d = dark/black)
FILES = {
    "K": "Chess_klt45.svg", "Q": "Chess_qlt45.svg", "R": "Chess_rlt45.svg",
    "B": "Chess_blt45.svg", "N": "Chess_nlt45.svg", "P": "Chess_plt45.svg",
    "k": "Chess_kdt45.svg", "q": "Chess_qdt45.svg", "r": "Chess_rdt45.svg",
    "b": "Chess_bdt45.svg", "n": "Chess_ndt45.svg", "p": "Chess_pdt45.svg",
}
BASE = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=128"
OUT_DIR = os.path.join(os.path.dirname(__file__), "templates")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "RindenSjakk/0.1 (local chess tool)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    ok = 0
    for piece, name in FILES.items():
        # prefix w/b so uppercase/lowercase don't collide on case-insensitive FS.
        tag = ("w" if piece.isupper() else "b") + piece.upper()
        out = os.path.join(OUT_DIR, f"{tag}.png")
        try:
            data = fetch(BASE.format(name=name))
            with open(out, "wb") as fh:
                fh.write(data)
            ok += 1
            print(f"  {piece} -> {os.path.basename(out)} ({len(data)} B)")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {piece} ({name}): {exc}", file=sys.stderr)
    print(f"fetched {ok}/{len(FILES)} templates into {OUT_DIR}")
    return 0 if ok == len(FILES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
