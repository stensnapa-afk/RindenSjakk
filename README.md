# SnapaSjakk

Trekk ut sjakkåpninger/repertoar fra video (f.eks. *The Gambit Man* på Lichess) og
lagre dem som **PGN repertoar-tre** — hovedlinje + variantene som vises i videoen.

Analogt med SnapaOppskrift (video → oppskrift), men sjakk er *deterministisk*: en
regelmotor (`python-chess`) feilretter alt, så ulovlige avlesninger kan ikke passere.

**Portabel, lokal-først, kun PC:** ingen sky, ingen hosting, ingen mobil/PWA. Kjører på
hvilken som helst Windows-PC med Python. Lagring blir lokale PGN-filer (+ SQLite),
viewer blir en desktop-flate (lokal nettleser-side verktøyet åpner, evt. lett
desktop-vindu).

## Arkitektur (faser)

| Fase | Innhold | Status |
|---|---|---|
| 0 | Deterministisk kjerne: FEN-tidslinje → PGN-tre + regelmotor-validering | ✅ ferdig, testet |
| 1 | Inntak: `yt-dlp` (video/beskrivelse/undertekst) + lichess-study-snarvei | planlagt |
| 2 | Brett-CV: `ffmpeg`-frames → lichess-brett → brikke-template-match → FEN/frame | planlagt |
| 3 | Fusjon: lokal Whisper (valgfri) muntlig notasjon × CV → regelmotor | planlagt |
| 4 | Lokal lagring (PGN + SQLite) + desktop-viewer (chessground + tre-navigator, ikke mobil/PWA) | planlagt |
| 5 | Pakking: `.exe` (PyInstaller) med medfølgende `ffmpeg`/`yt-dlp` | planlagt |

## Kjernens idé (Fase 0)

Brett-CV kan bare lese *brikkeplassering* pr. frame. Motoren utleder tur/rokade/en
passant ved å spille kun lovlige trekk fra start og matche den som gir observert
plassering. Repertoar-treet faller ut mekanisk: når posisjonen **gjentar en tidligere
stilling** og et *annet* trekk følger → det er en variant fra den noden.

## Kom i gang

```bash
python -m pip install -r requirements.txt

# Enhetstester
python -m unittest discover -s tests -v

# Demo: Benko-fragment med én variant → skriver engine/demo_benko.pgn
python engine/demo_benko.py

# Egen tidslinje (én brikkeplassering / FEN-felt-1 per linje)
python engine/fen_tree.py placements.txt > repertoire.pgn
```

## Struktur

```
engine/fen_tree.py     # kjernen: build_tree(placements) -> (chess.pgn.Game, stats)
engine/demo_benko.py   # demo som skriver demo_benko.pgn
tests/test_fen_tree.py # enhetstester (mainline, variant, brolegging, lovlighet)
```
