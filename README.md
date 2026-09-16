RindenSjakk

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
| 4 | Desktop-viewer (brett + variant-tre + bibliotek med rediger/slett, lagres lokalt) | ✅ demo kjører |
| 5 | Koble motoren til vieweren (video → tre → viewer) + pakking `.exe` (PyInstaller) | planlagt |

## Installasjon hjemme (én gang)

Alt kjører lokalt på din egen Windows-PC — ingen sky, ingen konto.

1. **Last ned prosjektet:** grønn `Code`-knapp på GitHub → `Download ZIP` → pakk ut.
   (Eller `git clone https://github.com/stensnapa-afk/RindenSjakk`.)
2. **Dobbeltklikk `install.bat`.** Den sjekker at Python 3 og Node.js finnes
   (åpner nedlastingssiden om noe mangler), lager et lokalt miljø og installerer alt.
3. Ferdig. Deretter:
   - **`start.bat`** → åpner appen (brett + repertoar) i nettleseren.
   - **`hent.bat "https://youtu.be/…"`** → trekker trekk ut av en video til PGN.

## Kjør vieweren (lokalt, kun PC)

Dobbeltklikk **`start.bat`** (krever Python 3) — åpner http://localhost:8777/ i nettleseren.
Eller manuelt:

```bash
cd viewer
python -m http.server 8777
# åpne http://localhost:8777/
```

Vieweren er ren statisk HTML/JS uten avhengigheter eller nett-tilgang. Alt du lagrer
(navn, notater, sletting av varianter) ligger i nettleserens `localStorage` på denne
maskinen. Seed-data genereres fra motoren med `python engine/tree_json.py`.

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
