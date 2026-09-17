# RindenSjakk — HANDOFF

Denne fila = sannhet for hvor vi står.

## Status (oppdatert 2026-09-17)

FERDIG og verifisert:
- **Viewer** (`viewer/`) — brett, variant-tre, autospill, bibliotek (rediger/slett/gjør-til-
  hovedlinje), notater. Lokal, localStorage. Kjøres via `start.bat` (server) eller ved å
  åpne `viewer/index.html` direkte.
- **Klientside PGN-import (NY — hovedfunksjon):** `viewer/chess.js` (komplett lovlig-trekk-
  motor i vanilla JS — perft 20/400/8902 + Kiwipete 48/2039 verifisert) + `viewer/pgn.js`
  (PGN→variant-tre: varianter, kommentarer, flere partier, FEN-setup, crammed tags).
  Testet ende-til-ende i nettleser. Lim inn PGN eller åpne `.pgn`-fil.
- **Lokal server** `server.py` (kun stdlib): serverer vieweren + `POST /api/extract`
  (video→tre) + `GET /api/storage` / `POST /api/storage/delete` (Lagring-panel).
- **Lagring-panel (NY):** «Lagring …»-knapp viser nedlastede videoer med størrelse; slett
  enkeltvis eller alle. Nedlasting går til synlig `downloads/<hash>.mp4` (gjenbrukes ved
  samme URL). Sti-vakt + `file://`-blokk + body-cap (Gemini-audit-herding).
- **Motor-tre** (`engine/fen_tree.py`) — 4 enhetstester grønne.
- **Trent gjenkjenner** (`engine/models/piece_svm.xml`) — video 1 = 94.4% hold-out
  (committet i git; Rinden får den ved nedlasting).

ROOT-FIKS 2026-09-17:
- `sample_frames` brukte `POS_MSEC`-seeking → ødelagt på YouTube DASH-mp4 → tom frame →
  `cvtColor` assertion-krasj (`!_src.empty()`). Byttet til sekvensiell `grab()/retrieve()`
  + tom-frame-vakt. Bekreftet: ingen krasj på video som tidligere kræsjet.

MÅLT BEGRENSNING (uendret vegg):
- Video→PGN-gjenkjenningen generaliserer ikke til vilkårlige renderinger og er fanget i en
  catch-22 (gjenkjenning best på lynparti, kjeding krever rolig video). På typiske
  repertoar-videoer leser den brettet tomt (`moves=0`) — nå returnerer den *pent*, ikke krasj.
  **PGN-import er den pålitelige veien.**

## NESTE STEG
1. (Valgfritt) Per-rendering-trening akkumulert av pipelinen for å knekke video 5 — eller
   dropp auto-video og stå på PGN-import som hovedvei.
2. (Valgfritt) PGN-eksport fra vieweren (nå kun import).
3. Slank modellen (72MB RBF → lineær SVM) hvis video-veien skal videreføres.

## Testdata (C:\temp\snapasjakk-spike\ — kan re-hentes)
- video 1 (gjenkjenning VIRKER): `vid720.mp4` = YT `3YvsmepLK7s`. Frames: `v1f/`.
- video 5 (gjenkjenning FEILER): `rep5.mp4` = YT `HalrW48gtOQ`. Frames: `rep5sp/`, `rep5scan/`.
- Re-hent: `python -m yt_dlp --js-runtimes node -f 136 -o vid720.mp4 "https://www.youtube.com/watch?v=3YvsmepLK7s"` (Node kreves!).

## Nøkkelfakta
- Graif spiller FLIPPET brett → `--orientation black`.
- yt-dlp trenger `--js-runtimes node`.
- Frame-uttrekk: sekvensiell grab/retrieve (IKKE POS_MSEC — kræsjer på DASH).
- Sjakkmotoren kan røyktestes uten nettleser: `node -e "require('./viewer/chess.js');require('./viewer/pgn.js');..."`.
- Full kontekst/mønstre: `blueprints/rindensjakk.md`, minne `project_rindensjakk.md`.
