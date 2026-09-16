# RindenSjakk — HANDOFF (sesjon 2026-09-16)

Fortsettes i ny sesjon. Denne fila = sannhet for hvor vi står.

## Status
FERDIG og virker:
- **Viewer** (`viewer/`, start med `start.bat`) — brett, variant-tre, autospill, bibliotek m/rediger/slett, notater, lenke-felt. Lokal, localStorage.
- **Tre-motor** (`engine/fen_tree.py`) — FEN-tidslinje → PGN-tre, takeback=variant, DFS m/node-budsjett, `root_fen`-seed. 4 tester grønne (`python -m unittest discover -s tests`).
- **Trent gjenkjenner** (`engine/train_real.py` → `engine/models/piece_svm.xml`, HOG+SVM i OpenCV) — **video 1 = 94.4% hold-out, alle test-frames lovlige+korrekte.**
- **Selv-installer** (`install.bat`/`hent.bat`), public repo `stensnapa-afk/RindenSjakk`.

BLOKKERT (der vi jobbet sist):
- Gjenkjenneren generaliserer IKKE til video 5s rendering (leser alt tomt — majoritetsklasse-bias for out-of-distribution). Bekreftet at det IKKE er brett-deteksjon (bbox-sveip: ingen boks gir brikker). Ingen startstilling i rep5 å auto-merke.

## NESTE STEG (start her i morgen)
Kjør den **avbrutte** multi-rendering-treningen (composite cburnett på EKTE video-5 tomme bakgrunner — pålitelige etiketter, ingen håndtranskribering):

```
cd C:/Claude-AI/projects/rindensjakk
python engine/train_multi.py --label_glob "C:/temp/snapasjakk-spike/v1f/v_*.png" --bg_glob "C:/temp/snapasjakk-spike/rep5sp/s_*.png"
# så test på held-out video-5-frames (rep5scan/r_90,r_120,r_240): filled>6 og valid=True = gjennombrudd
```
Hvis dette IKKE cracker video 5 → vurder liten CNN (onnxruntime) eller verifisert håndmerking av 2-3 rep5-frames (kryssjekk mot legalitet + kjent Benko-linje).

Etter gjenkjenning virker på video 5:
1. Ende-til-ende på repertoar-video (rolige trekk) → vis PGN-tre (trekk-kjeding funker på rolige sekvenser, IKKE lynparti @2fps).
2. Koble motor↔viewer (lokal server-endepunkt så «Hent trekk» faktisk kjører).
3. Slank modellen (72MB RBF → lineær SVM).

## Testdata (i C:\temp\snapasjakk-spike\ — kan re-hentes om slettet)
- video 1 (lynparti, gjenkjenning VIRKER): `vid720.mp4` = YouTube `3YvsmepLK7s`. Frames: `v1f/`, `f_180/300/540.png`.
- video 5 (repertoar/explorer, gjenkjenning FEILER): `rep5.mp4` = YouTube `HalrW48gtOQ`. Frames: `rep5sp/`, `rep5scan/`.
- Re-hent: `python -m yt_dlp --js-runtimes node -f 136 -o vid720.mp4 "https://www.youtube.com/watch?v=3YvsmepLK7s"` (Node kreves som JS-runtime!). Frames: `ffmpeg -ss <t> -i <mp4> -vf fps=<n> out_%03d.png`.

## Nøkkelfakta
- Graif spiller FLIPPET brett → `--orientation black`.
- yt-dlp trenger `--js-runtimes node` (ellers bare m3u8/heng).
- cv2 POS_MSEC-seeking henger på DASH-mp4 → bruk ffmpeg fps-uttrekk.
- Full kontekst/mønstre: `blueprints/rindensjakk.md`, minne `project_rindensjakk.md`.
