"""RindenSjakk — end-to-end: a chess video -> PGN move tree.

Pipeline: sample frames -> recognize the board to a FEN placement per frame ->
keep only legal positions -> drop consecutive duplicates -> feed the placement
timeline to the rules-based tree builder (fen_tree). Orientation (Graif plays
flipped) is auto-detected by which orientation yields more legal positions.

CLI:
  python engine/process_video.py <video.mp4|youtube-url> [--interval 1.5]
      [--start 20] [--end 240] [--orientation auto|white|black] [--out out.pgn]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

import chess
import chess.pgn
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.fen_tree import build_tree
from engine.recognize import recognize_placement, _load_templates


def _is_legal(placement: str) -> bool:
    if placement.count("K") != 1 or placement.count("k") != 1:
        return False
    try:
        return chess.Board(placement + " w - - 0 1").status() == chess.STATUS_VALID
    except Exception:  # noqa: BLE001
        return False


def download_if_url(src: str) -> str:
    if not src.lower().startswith(("http://", "https://")):
        return src
    out = os.path.join(tempfile.gettempdir(), "rinden_video.mp4")
    print("laster ned video …", file=sys.stderr)
    subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--js-runtimes", "node",
         "-f", "bv*[height<=720][ext=mp4]/b[height<=720]", "-o", out, src],
        check=True,
    )
    return out


def sample_frames(path: str, interval: float, start: float, end: float | None):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"kan ikke åpne video: {path}")
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    t = start
    stop = min(end, dur) if end else dur
    while t <= stop:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if ok:
            yield t, frame
        t += interval
    cap.release()


def pick_orientation(frames, templates) -> str:
    score = {"white": 0, "black": 0}
    for _, frame in frames:
        for orient in ("white", "black"):
            if _is_legal(recognize_placement(frame, orient, templates)):
                score[orient] += 1
    return "black" if score["black"] >= score["white"] else "white"


def process(video: str, interval: float, start: float, end: float | None,
            orientation: str = "auto") -> tuple[chess.pgn.Game, dict, list[str]]:
    templates = _load_templates()
    frames = list(sample_frames(video, interval, start, end))
    if not frames:
        raise RuntimeError("ingen frames samplet")

    if orientation == "auto":
        probe = frames[:: max(1, len(frames) // 20)]
        orientation = pick_orientation(probe, templates)
        print(f"orientering: {orientation}", file=sys.stderr)

    placements = []
    for _, frame in frames:
        pl = recognize_placement(frame, orientation, templates)
        if _is_legal(pl):
            placements.append(pl)

    # drop consecutive duplicates (the board is static between moves).
    dedup = []
    for pl in placements:
        if not dedup or pl != dedup[-1]:
            dedup.append(pl)

    # Seed the tree from the start position, or from the first observation
    # (mid-game start) trying either side to move — pick whichever reconstructs
    # the most moves.
    seeds: list[str | None] = [None]
    if dedup:
        seeds += [dedup[0] + " w - - 0 1", dedup[0] + " b - - 0 1"]
    best = None
    for rf in seeds:
        try:
            g, s = build_tree(dedup, max_bridge=3, root_fen=rf)
        except Exception:  # noqa: BLE001
            continue
        if best is None or s["moves"] > best[1]["moves"]:
            best = (g, s)
    game, stats = best if best else build_tree(dedup)

    stats["frames"] = len(frames)
    stats["legal"] = len(placements)
    stats["unique"] = len(dedup)
    stats["orientation"] = orientation
    return game, stats, dedup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Chess video -> PGN move tree.")
    parser.add_argument("video")
    parser.add_argument("--interval", type=float, default=1.5)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=None)
    parser.add_argument("--orientation", choices=["auto", "white", "black"], default="auto")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    video = download_if_url(args.video)
    game, stats, _ = process(video, args.interval, args.start, args.end, args.orientation)
    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    pgn = game.accept(exporter)
    print(pgn)
    print("\n; stats:", stats, file=sys.stderr)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(pgn + "\n")
        print("skrev:", args.out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
