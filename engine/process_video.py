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
import hashlib
import os
import subprocess
import sys

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


DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")


def _is_cert_error(stderr: str | None) -> bool:
    """Er yt-dlp-feilen en TLS/sertifikat-verifiseringsfeil? Da (og bare da) er det
    trygt å falle tilbake til --no-check-certificates for nedlastingen."""
    s = (stderr or "").upper()
    return ("CERTIFICATE_VERIFY_FAILED" in s
            or "UNABLE TO GET LOCAL ISSUER CERTIFICATE" in s
            or "SSL: CERTIFICATE" in s
            or "CERTIFICATE VERIFY FAILED" in s)


def download_if_url(src: str) -> str:
    """A local file path is returned as-is; an http(s) URL is downloaded once
    into downloads/ (named by a hash of the URL, so the same video is reused and
    Rinden can see/delete it). Other schemes (file://, ftp://, …) are refused —
    yt-dlp would otherwise happily read local files off disk."""
    low = src.lower()
    if not low.startswith(("http://", "https://")):
        if "://" in low:
            raise ValueError("kun http(s)-lenker eller lokale filstier er tillatt")
        return src  # local file path
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    out = os.path.join(DOWNLOAD_DIR, hashlib.sha1(src.encode("utf-8")).hexdigest()[:12] + ".mp4")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        print("bruker tidligere nedlastet video", file=sys.stderr)
        return out
    print("laster ned video …", file=sys.stderr)
    # --no-playlist: en YouTube-lenke bærer ofte &list=… (spilleliste). Uten dette
    # flagget laster yt-dlp ned HELE spillelista til samme fil, og returnerer exit 1
    # dersom BARE ÉN av videoene feiler (region-sperret, medlems-only, slettet, mangler
    # format) — selv om mål-videoen gikk fint. Vi vil alltid ha kun den ene lenken.
    base_cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--js-runtimes", "node",
                "-f", "bv*[height<=720][ext=mp4]/b[height<=720]", "-o", out, src]

    # SSL-cert-fella (Windows Python): [SSL: CERTIFICATE_VERIFY_FAILED] "unable to get
    # local issuer certificate". yt-dlp verifiserer youtube.com mot certifi sin CA-bundle
    # — men BARE hvis certifi er installert i venv'et. Mangler den, faller yt-dlp tilbake
    # til OS-lageret, som Python på Windows ofte ikke finner et utsteder-sertifikat i.
    # Rot-fiksen er derfor at certifi ligger i requirements.txt (installeres i venv);
    # da virker verifisert nedlasting likt på alle maskiner etter `git pull`.
    proc = subprocess.run(base_cmd, capture_output=True, text=True)

    # Siste utvei: hvis det FORTSATT feiler på selve sertifikat-verifiseringen (f.eks.
    # bedrifts-proxy/MITM, ødelagt cert-lager, eller certifi ikke installert ennå), prøv
    # én gang UTEN verifisering. Kun ved påvist cert-feil — aldri generelt — og med
    # tydelig advarsel i loggen.
    if proc.returncode != 0 and _is_cert_error(proc.stderr):
        print("ADVARSEL: SSL-verifisering feilet — prøver på nytt uten cert-sjekk "
              "(--no-check-certificates). Kjør install.bat på nytt for å få certifi "
              "og verifisert nedlasting.", file=sys.stderr)
        proc = subprocess.run(base_cmd + ["--no-check-certificates"],
                              capture_output=True, text=True)

    if proc.returncode != 0:
        # Løft yt-dlp sin FAKTISKE feilårsak videre (stderr), ikke bare den ugjennom-
        # trengelige "returned non-zero exit status 1". ERROR-linjer først; ellers hale.
        err = (proc.stderr or "").strip()
        lines = [ln for ln in err.splitlines() if "ERROR" in ln] or err.splitlines()[-8:]
        detail = "\n".join(lines).strip() or "ukjent feil (ingen stderr)"
        raise RuntimeError("nedlasting feilet (yt-dlp):\n" + detail)
    return out


def sample_frames(path: str, interval: float, start: float, end: float | None):
    """Yield (timestamp, frame) at ~`interval` seconds apart.

    Reads SEQUENTIALLY with grab()/retrieve() instead of POS_MSEC seeking:
    time-based seeking is unreliable on YouTube DASH-mp4 and returns empty
    frames that crash cvtColor downstream (assertion !_src.empty()). Grabbing
    every frame and decoding only at sample points is seek-free and robust.
    Empty/garbage frames are skipped, never yielded.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"kan ikke åpne video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0 or fps != fps:  # 0 / NaN guard
        fps = 25.0
    step = max(1, int(round(interval * fps)))
    start_frame = max(0, int(round(start * fps)))
    end_frame = int(round(end * fps)) if end else None
    idx = -1
    try:
        while True:
            if not cap.grab():
                break
            idx += 1
            if idx < start_frame:
                continue
            if end_frame is not None and idx > end_frame:
                break
            if (idx - start_frame) % step != 0:
                continue
            ok, frame = cap.retrieve()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                yield idx / fps, frame
    finally:
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
