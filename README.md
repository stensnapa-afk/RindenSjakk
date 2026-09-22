# RindenSjakk

Et **lokalt sjakk-repertoarverktøy** for Windows. Bygg og studer åpnings­repertoar som
et **variant-tre** (hovedlinje + varianter), med brett, autospill, notater og bibliotek.
Alt kjører på din egen PC — ingen sky, ingen konto, ingen internett nødvendig for å bruke det.

To måter å få repertoar inn:

1. **Importer PGN** — lim inn PGN eller åpne en `.pgn`-fil. Håndterer varianter,
   kommentarer, flere partier og oppsett fra en gitt stilling (FEN). *Dette er den
   pålitelige hovedveien* og virker med alt fra Lichess-studier, ChessBase, Chessable, osv.
2. **Fra video (eksperimentelt)** — lim inn en YouTube-lenke til en åpningsvideo, så
   prøver motoren å lese brettet frame for frame. Se ærlig status nederst.

---

## Installasjon (én gang)

Alt er lokalt. Du trenger **Python 3** (og **Node.js** hvis du vil bruke video-import —
`yt-dlp` bruker Node for å laste ned fra YouTube).

1. **Hent koden:** grønn `Code`-knapp på GitHub → `Download ZIP` → pakk ut.
   Eller: `git clone https://github.com/stensnapa-afk/RindenSjakk`
2. Kjør installasjonen for din plattform:
   - **Windows:** dobbeltklikk **`install.bat`**. Husk å krysse av *«Add python.exe to PATH»*
     hvis den ber deg installere Python.
   - **Mac:** dobbeltklikk **`install.command`**. Første gang blokkerer macOS ukjente scripts —
     da: **høyreklikk (Ctrl-klikk) → Åpne → Åpne**. (Alternativt fjern karantene i Terminal:
     `xattr -d com.apple.quarantine *.command`.)

   Installasjonen sjekker at **Python 3** og **Node.js** finnes (åpner nedlastingssiden om noe
   mangler), lager et lokalt miljø (`.venv`) og installerer avhengighetene.

Avhengigheter (se `requirements.txt`): `opencv-python-headless`, `chess`, `yt-dlp`, `numpy`,
`certifi`. Node.js trengs kun for video-nedlasting (yt-dlp bruker det som JS-runtime).

> **Oppdaterer du en eksisterende installasjon?** Etter `git pull` må du kjøre
> **`install.bat`** (Windows) / **`install.command`** (Mac) på nytt, ellers får du ikke
> de nye avhengighetene inn i `.venv`. Se *Feilsøking* nederst hvis video-nedlasting gir
> en SSL-/sertifikatfeil.

---

## Starte appen

Dobbeltklikk **`start.bat`** (Windows) eller **`start.command`** (Mac). Den starter en lokal
server og åpner `http://localhost:8777/` i nettleseren automatisk. Lukk vinduet for å stoppe.
Video-uttrekk fra kommandolinjen: **`hent.bat "…"`** (Windows) / **`hent.command`** (Mac).

> Vil du bare studere PGN uten å installere noe? Åpne `viewer/index.html` direkte i
> nettleseren (funker på Windows, Mac og Linux). Da virker alt unntatt video-import
> (som trenger serveren + Python).

---

## Bruk

### Importer PGN (hovedfunksjonen)
1. Klikk **«Importer PGN»** i biblioteket.
2. Lim inn PGN i tekstfeltet, **eller** klikk *«Åpne .pgn-fil …»*.
3. **«Legg til»**. Åpningen dukker opp i biblioteket med hele variant-treet.

Støtter:
- Varianter i parentes: `1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 (3... Nf6 4. O-O) 4. Ba4`
- Kommentarer i `{ ... }` (festes på trekket og vises under brettet)
- Flere partier i samme fil (blir flere åpninger)
- Oppsett fra en gitt stilling (`[FEN "…"]` / `[SetUp "1"]`)
- Bare en trekkrekke uten tagger: `e4 e5 Nf3 Nc6 Bb5`

Ulovlige/ugjenkjennelige trekk hoppes over, og du får beskjed om hvor mange.

### Bygge og studere
- **+ Ny** — tom åpning fra startstillingen.
- Klikk et trekk i trelista for å hoppe dit; **⏮ ◀ ▶** og piltaster navigerer;
  **▶ Spill av** spiller gjennom hovedlinjen automatisk.
- **⇅ Snu brett** — se fra hvit eller svart side.
- **Notat** — kommentar på det valgte trekket. **Slett variant** / **Gjør til hovedlinje**
  rydder treet. Fritekst-**Notater** per åpning lagres automatisk.
- I biblioteket: **✎** gir nytt navn, **🗑** sletter (klikk to ganger for å bekrefte).

### Fra video (eksperimentelt)
- Lim en YouTube-lenke i **«Video → repertoar»**-feltet og trykk **«Hent trekk»**.
  Appen laster ned videoen, leser brettet frame for frame og prøver å bygge treet.
- Kommandolinje-variant: `hent.bat "https://youtu.be/…"` (flagg: `--start`, `--end`,
  `--interval`, `--orientation auto|white|black`, `--out fil.pgn`).

**Ærlig status på video:** brikkegjenkjenningen er trent per video-rendering og
generaliserer ikke til vilkårlige videoer. Den er dessuten fanget i en catch-22 —
gjenkjenning er best på raske lynpartier, men trekk-kjeding krever rolige sekvenser.
På typiske repertoar-/explorer-videoer leser den ofte brettet tomt og finner ingen
trekk. Verktøyet sier fra ærlig når det ikke fikk til noe. **Bruk PGN-import for
pålitelig resultat.**

---

## Hvor lagres dataene?

I nettleserens `localStorage` på denne maskinen (nøkkel `rinden.repertoires.v1`) — knyttet
til hvordan du åpner appen. Ingenting sendes noe sted. Vil du dele et repertoar, eksporter
det som PGN fra kilden din og importer på den andre maskinen.

---

## Under panseret

- **`viewer/`** — statisk HTML/JS, ingen npm-avhengigheter:
  - `chess.js` — komplett lovlig-trekk-motor i vanilla JS (FEN, SAN, rokade, en passant,
    promotering). Verifisert med perft (20 / 400 / 8902 fra start; Kiwipete 48 / 2039).
  - `pgn.js` — PGN → variant-tre (`{san, uci, fen, children}`).
  - `app.js` / `index.html` / `samples.js` — brett, tre, bibliotek, seed-data.
- **`engine/`** — Python video-pipeline:
  - `process_video.py` — video → FEN/frame → lovlige stillinger → `fen_tree` → PGN-tre.
  - `fen_tree.py` — deterministisk kjerne: brikkeplassering-tidslinje → PGN-tre
    (takeback = variant, DFS med node-budsjett). Enhetstestet.
  - `recognize.py` / `board_detect.py` — brett-lokalisering + brikkegjenkjenning
    (trent HOG+SVM i `engine/models/piece_svm.xml`).
  - `tree_json.py` — eksporterer trær til viewerens JSON-form.
- **`server.py`** — liten lokal server (kun stdlib): serverer vieweren og kjører
  video-uttrekk på `POST /api/extract`. Motoren importeres først når den trengs, så
  vieweren virker selv uten OpenCV installert.

### Utvikling / tester

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v      # motor-enhetstester
python engine/tree_json.py                    # regenerer viewer/samples.js
```

Sjakkmotoren i JS kan røyktestes uten nettleser:

```bash
node -e "require('./viewer/chess.js'); require('./viewer/pgn.js'); \
  console.log(RindenPGN.parse('1. e4 e5 2. Nf3 *').reps[0].root.children[0].san)"  # -> e4
```

---

## Feilsøking

**Video-nedlasting feiler med `[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local
issuer certificate`.** `yt-dlp` verifiserer YouTube mot en CA-bundle (`certifi`), men
finner den ikke — typisk fordi `certifi` mangler i miljøet (vanlig Windows-Python-felle).

Slik fikser du det:
1. **`git pull`** (henter siste kode).
2. Kjør **`install.bat`** / **`install.command`** på nytt — det installerer `certifi` i
   `.venv`, og verifisert nedlasting virker igjen.

Appen har også en innebygd sikkerhets­net: om verifisering *fortsatt* feiler på selve
sertifikatet (f.eks. ødelagt cert-lager eller proxy), prøver den nedlastingen én gang til
uten sertifikatsjekk og skriver en tydelig **ADVARSEL** i loggen. Kjør reinstall (over) for
å få tilbake full verifisert nedlasting.

---

## Filoversikt

```
install.bat / install.command   # engangs-oppsett (Windows / Mac): Python/Node + .venv + deps
start.bat   / start.command     # start appen (lokal server + nettleser)
hent.bat    / hent.command      # video → PGN på kommandolinjen
server.py          # lokal server: viewer + /api/extract
viewer/            # brett + variant-tre + PGN-import (statisk, ingen deps)
engine/            # video-pipeline + deterministisk tre-motor (Python)
tests/             # enhetstester for tre-motoren
```
