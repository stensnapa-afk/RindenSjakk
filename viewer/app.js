/* RindenSjakk — local viewer. Pure vanilla, no deps, no network.
   Renders a repertoire tree (board + move tree) and lets you rename / delete /
   annotate / prune what is saved locally (localStorage). */

'use strict';

const STORE_KEY = 'rinden.repertoires.v1';
const GLYPH = { k:'♚', q:'♛', r:'♜', b:'♝', n:'♞', p:'♟' };

const $ = (sel) => document.querySelector(sel);

/* ---------- storage ---------- */
function loadStore() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* private mode / blocked — fall through to seed */ }
  const seed = JSON.parse(JSON.stringify(window.RINDEN_SAMPLES || []));
  saveStore(seed);
  return seed;
}
function saveStore(list) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(list)); }
  catch (e) { setStatus('kunne ikke lagre lokalt (privat vindu?)'); }
}

let store = loadStore();
let currentId = store.length ? store[0].id : null;
let currentPath = [];           // list of child-indices from root
let pendingDelete = null;       // id awaiting 2nd-click confirm

/* ---------- helpers ---------- */
function current() { return store.find((r) => r.id === currentId) || null; }
function nodeAt(rep, path) {
  let children = rep.root.children, node = null;
  for (const idx of path) { node = children[idx]; if (!node) return null; children = node.children; }
  return node;
}
function fenAt(rep, path) {
  const node = nodeAt(rep, path);
  return node ? node.fen : rep.root.start_fen;
}
function uid() { return 'r' + Math.random().toString(36).slice(2, 9); }
function setStatus(msg) { $('#status-pill').textContent = msg; }

/* ---------- board ---------- */
function renderBoard() {
  const rep = current();
  const board = $('#board');
  board.innerHTML = '';
  if (!rep) { $('#fen').textContent = '—'; return; }
  const fen = fenAt(rep, currentPath);
  const placement = fen.split(' ')[0];
  const rows = placement.split('/');           // rank 8 .. rank 1
  const grid = {};                             // 'a1' -> pieceChar
  for (let r = 0; r < 8; r++) {
    const rank = 8 - r;
    let file = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) { file += parseInt(ch, 10); }
      else { grid['abcdefgh'[file] + rank] = ch; file++; }
    }
  }
  const node = nodeAt(rep, currentPath);
  const lastSquares = node && node.uci ? [node.uci.slice(0, 2), node.uci.slice(2, 4)] : [];

  const white = rep.orientation !== 'black';
  const ranks = white ? [8,7,6,5,4,3,2,1] : [1,2,3,4,5,6,7,8];
  const files = white ? [0,1,2,3,4,5,6,7] : [7,6,5,4,3,2,1,0];

  for (const rank of ranks) {
    for (const f of files) {
      const fileCh = 'abcdefgh'[f];
      const key = fileCh + rank;
      const dark = ((rank + (f + 1)) % 2) === 0;
      const sq = document.createElement('div');
      sq.className = 'sq ' + (dark ? 'dark' : 'light') + (lastSquares.includes(key) ? ' hl' : '');
      const pc = grid[key];
      if (pc) {
        const span = document.createElement('span');
        span.className = 'piece ' + (pc === pc.toUpperCase() ? 'w' : 'b');
        span.textContent = GLYPH[pc.toLowerCase()];
        sq.appendChild(span);
      }
      // edge coordinates
      const isBottom = rank === ranks[7];
      const isLeft = f === files[0];
      if (isBottom) { const c = document.createElement('span'); c.className = 'co file'; c.textContent = fileCh; sq.appendChild(c); }
      if (isLeft)   { const c = document.createElement('span'); c.className = 'co rank'; c.textContent = rank; sq.appendChild(c); }
      board.appendChild(sq);
    }
  }
  $('#fen').textContent = fen;
}

/* ---------- move tree ---------- */
function renderMoves() {
  const rep = current();
  $('#rep-title').textContent = rep ? rep.name : 'Trekk';
  const box = $('#moves');
  if (!rep) { box.innerHTML = '<div class="empty">Ingen åpning valgt.</div>'; renderNodeTools(); return; }
  if (!rep.root.children.length) { box.innerHTML = '<div class="empty">Tom — startstilling. Bruk motoren for å fylle trekk.</div>'; renderNodeTools(); return; }
  box.innerHTML = '<div class="movelist">' + renderSeq(rep.root.children, [], 0) + '</div>';
  box.querySelectorAll('.mv').forEach((el) => {
    el.addEventListener('click', () => {
      stopPlay();
      currentPath = el.dataset.path === '' ? [] : el.dataset.path.split(',').map(Number);
      render();
    });
  });
  renderNodeTools();
}
function moveSpan(node, path, ply, forceNum) {
  const moveNo = Math.floor(ply / 2) + 1;
  const white = ply % 2 === 0;
  const num = white ? `${moveNo}.` : (forceNum ? `${moveNo}...` : '');
  const cur = path.join(',') === currentPath.join(',') ? ' current' : '';
  const numHtml = num ? `<span class="mvnum">${num}</span> ` : '';
  return `<span class="mv${cur}" data-path="${path.join(',')}">${numHtml}${node.san}</span> `;
}
function renderSeq(children, basePath, ply) {
  let html = '';
  let cur = children, path = basePath, p = ply;
  while (cur && cur.length) {
    const main = cur[0];
    const mainPath = [...path, 0];
    html += moveSpan(main, mainPath, p, false);
    for (let s = 1; s < cur.length; s++) {
      const alt = cur[s];
      const altPath = [...path, s];
      html += `<div class="variation">` + moveSpan(alt, altPath, p, true) + renderSeq(alt.children, altPath, p + 1) + `</div>`;
    }
    cur = main.children; path = mainPath; p += 1;
  }
  return html;
}

/* ---------- per-node tools + comment ---------- */
function renderNodeTools() {
  const rep = current();
  const tools = $('#node-tools');
  const commentBox = $('#comment');
  tools.innerHTML = '';
  commentBox.textContent = '';
  if (!rep) return;
  const node = nodeAt(rep, currentPath);
  commentBox.textContent = node && node.comment ? '“' + node.comment + '”' : '';

  const noteBtn = mkBtn(node ? 'Notat' : 'Notat (velg trekk)', () => openComment());
  noteBtn.disabled = !node;
  tools.appendChild(noteBtn);

  if (node && currentPath.length) {
    tools.appendChild(mkBtn('Slett variant', () => deleteVariation(), 'danger'));
    const parentChildren = parentChildrenOf(currentPath);
    if (parentChildren && parentChildren.length > 1 && currentPath[currentPath.length - 1] !== 0) {
      tools.appendChild(mkBtn('Gjør til hovedlinje', () => promoteVariation()));
    }
  }
}
function mkBtn(label, fn, extra) {
  const b = document.createElement('button');
  b.className = 'btn' + (extra ? ' ' + extra : '');
  b.textContent = label; b.addEventListener('click', fn); return b;
}
function parentChildrenOf(path) {
  const rep = current();
  if (!path.length) return null;
  return nodeAt(rep, path.slice(0, -1)) ? nodeAt(rep, path.slice(0, -1)).children : rep.root.children;
}
function deleteVariation() {
  const rep = current();
  const parentPath = currentPath.slice(0, -1);
  const children = parentPath.length ? nodeAt(rep, parentPath).children : rep.root.children;
  children.splice(currentPath[currentPath.length - 1], 1);
  currentPath = parentPath;
  saveStore(store); render();
}
function promoteVariation() {
  const rep = current();
  const parentPath = currentPath.slice(0, -1);
  const children = parentPath.length ? nodeAt(rep, parentPath).children : rep.root.children;
  const idx = currentPath[currentPath.length - 1];
  const [moved] = children.splice(idx, 1);
  children.unshift(moved);
  currentPath = [...parentPath, 0];
  saveStore(store); render();
}

/* ---------- navigation ---------- */
function goStart() { currentPath = []; render(); }
function goPrev() { if (currentPath.length) { currentPath = currentPath.slice(0, -1); render(); } }
function goNext() {
  const rep = current(); if (!rep) return;
  const children = currentPath.length ? nodeAt(rep, currentPath).children : rep.root.children;
  if (children && children.length) { currentPath = [...currentPath, 0]; render(); }
}

/* ---------- library ---------- */
function renderLibrary() {
  const list = $('#lib-list');
  list.innerHTML = '';
  if (!store.length) { list.innerHTML = '<div class="empty">Tomt bibliotek.</div>'; return; }
  for (const rep of store) {
    const item = document.createElement('div');
    item.className = 'lib-item' + (rep.id === currentId ? ' active' : '');
    item.innerHTML = `<span class="name"><b></b><small></small></span>`;
    item.querySelector('b').textContent = rep.name;
    item.querySelector('small').textContent = rep.source || 'lokal';
    item.addEventListener('click', () => { stopPlay(); currentId = rep.id; currentPath = []; pendingDelete = null; render(); });

    const rename = document.createElement('button');
    rename.className = 'icon-btn'; rename.title = 'Gi nytt navn'; rename.textContent = '✎';
    rename.addEventListener('click', (e) => { e.stopPropagation(); openRename(rep.id); });

    const del = document.createElement('button');
    del.className = 'icon-btn danger';
    if (pendingDelete === rep.id) { del.textContent = 'Slett?'; del.style.width = 'auto'; del.style.padding = '0 8px'; del.style.color = '#e08b83'; }
    else { del.textContent = '🗑'; }
    del.title = 'Slett';
    del.addEventListener('click', (e) => {
      e.stopPropagation();
      if (pendingDelete === rep.id) { deleteRep(rep.id); }
      else { pendingDelete = rep.id; renderLibrary(); setTimeout(() => { if (pendingDelete === rep.id) { pendingDelete = null; renderLibrary(); } }, 3000); }
    });

    item.appendChild(rename); item.appendChild(del);
    list.appendChild(item);
  }
}
function deleteRep(id) {
  store = store.filter((r) => r.id !== id);
  pendingDelete = null;
  if (currentId === id) { currentId = store.length ? store[0].id : null; currentPath = []; }
  saveStore(store); render();
}
function addRep(name, source) {
  const rep = { id: uid(), name: name || 'Ny åpning', source: source || 'lokal', orientation: 'white',
    root: { start_fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', children: [] } };
  store.push(rep); currentId = rep.id; currentPath = []; saveStore(store); render();
  return rep;
}

/* ---------- dialogs ---------- */
function openRename(id) {
  const rep = store.find((r) => r.id === id); if (!rep) return;
  const dlg = $('#dlg-name'); $('#dlg-name-title').textContent = 'Gi nytt navn';
  const input = $('#dlg-name-input'); input.value = rep.name;
  $('#dlg-name-ok').onclick = () => { rep.name = input.value.trim() || rep.name; saveStore(store); dlg.close(); render(); };
  dlg.showModal(); input.focus(); input.select();
}
function openComment() {
  const rep = current(); const node = nodeAt(rep, currentPath); if (!node) return;
  const dlg = $('#dlg-comment'); const input = $('#dlg-comment-input'); input.value = node.comment || '';
  $('#dlg-comment-ok').onclick = () => { const v = input.value.trim(); if (v) node.comment = v; else delete node.comment; saveStore(store); dlg.close(); render(); };
  dlg.showModal(); input.focus();
}
function openImport() {
  const dlg = $('#dlg-import');
  $('#dlg-import-name').value = ''; $('#dlg-import-moves').value = ''; $('#dlg-import-status').textContent = '';
  const fileInput = $('#dlg-import-fileinput');
  $('#dlg-import-file').onclick = () => fileInput.click();
  fileInput.onchange = () => {
    const f = fileInput.files[0]; if (!f) return;
    const rd = new FileReader();
    rd.onload = () => { $('#dlg-import-moves').value = rd.result; $('#dlg-import-status').textContent = f.name + ' lastet — trykk «Legg til».'; };
    rd.readAsText(f);
  };
  $('#dlg-import-ok').onclick = () => doImport($('#dlg-import-moves').value, $('#dlg-import-name').value.trim());
  dlg.showModal();
}
function doImport(text, nameOverride) {
  const status = $('#dlg-import-status');
  if (!text || !text.trim()) { status.textContent = 'Lim inn PGN eller åpne en .pgn-fil først.'; return; }
  if (!window.RindenPGN) { status.textContent = 'PGN-motoren mangler (last siden på nytt).'; return; }
  let res;
  try { res = window.RindenPGN.parse(text); }
  catch (e) { status.textContent = 'Klarte ikke å lese PGN: ' + e.message; return; }
  if (!res.reps.length) { status.textContent = 'Fant ingen gyldige trekk i teksten.'; return; }
  let added = 0, lastId = null;
  res.reps.forEach((rep, i) => {
    rep.id = uid();
    if (nameOverride) rep.name = res.reps.length > 1 ? nameOverride + ' #' + (i + 1) : nameOverride;
    store.push(rep); lastId = rep.id; added++;
  });
  currentId = lastId; currentPath = []; saveStore(store);
  $('#dlg-import').close(); render();
  const warn = res.errors.length
    ? ' — hoppet over ' + res.errors.length + ' trekk (' + res.errors.slice(0, 3).join(', ') + (res.errors.length > 3 ? '…' : '') + ')'
    : '';
  setStatus('Importerte ' + added + ' åpning' + (added > 1 ? 'er' : '') + warn);
}

/* ---------- video link (queued; engine wires in next phase) ---------- */
function looksLikeVideoUrl(u) { return /^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i.test(u); }
function fetchFromLink() {
  const input = $('#video-url'), status = $('#link-status');
  const url = input.value.trim();
  if (!url) { status.textContent = 'Lim inn en lenke først.'; return; }
  if (!looksLikeVideoUrl(url)) { status.textContent = 'Ser ikke ut som en YouTube-lenke.'; return; }

  // Opened as a plain file (file://) there is no engine to call — queue instead.
  if (location.protocol === 'file:') {
    const rep = addRep('Ny åpning (fra video)', 'video-kø');
    rep.pending = true; rep.videoUrl = url;
    rep.root.children.push({ san: '(kjør motoren)', uci: '', fen: rep.root.start_fen, children: [],
      comment: 'Kilde: ' + url + ' — for automatisk uttrekk: start appen via start.bat (lokal server), eller kjør  hent.bat "' + url + '"' });
    saveStore(store); input.value = '';
    status.textContent = 'Lagret. Auto-uttrekk krever at appen startes via start.bat (server), ikke ved å åpne fila direkte.';
    render(); return;
  }

  const btn = $('#btn-fetch'), oldLabel = btn.textContent;
  btn.disabled = true; btn.textContent = 'Leser video …';
  status.textContent = 'Laster ned og leser brettet — dette kan ta et par minutter …';
  fetch('/api/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
    .then((r) => r.json().then((j) => ({ ok: r.ok, j })))
    .then(({ ok, j }) => {
      if (!ok || j.error) { status.textContent = 'Feil: ' + (j.error || 'ukjent'); return; }
      if (!j.root || !j.root.children || !j.root.children.length) { status.textContent = 'Motoren fant ingen lovlige trekk i videoen.'; return; }
      const rep = { id: uid(), name: j.name || 'Fra video', source: j.source || 'video', orientation: j.orientation || 'white', root: j.root };
      store.push(rep); currentId = rep.id; currentPath = []; saveStore(store);
      const s = j.stats || {};
      status.textContent = 'Ferdig' + (s.moves != null ? ': ' + s.moves + ' trekk' : '') + (s.unique != null ? ', ' + s.unique + ' stillinger' : '') + '.';
      input.value = ''; render();
    })
    .catch((e) => { status.textContent = 'Kunne ikke nå motoren: ' + e.message; })
    .finally(() => { btn.disabled = false; btn.textContent = oldLabel; });
}

/* ---------- storage (downloaded videos on disk) ---------- */
function fmtBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1024 * 1024) return (n / 1024).toFixed(0) + ' KB';
  if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + ' MB';
  return (n / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}
function openStorage() {
  const dlg = $('#dlg-storage');
  loadStorage();
  $('#storage-clear').onclick = () => {
    fetch('/api/storage/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ all: true }) })
      .then((r) => r.json()).then(() => loadStorage()).catch(() => {});
  };
  dlg.showModal();
}
function loadStorage() {
  const list = $('#storage-list'), total = $('#storage-total');
  list.innerHTML = '<div class="empty">Laster …</div>';
  fetch('/api/storage').then((r) => r.json()).then((data) => {
    const files = data.files || [];
    total.textContent = 'Til sammen ' + fmtBytes(data.total || 0) + ' i ' + (data.dir || 'downloads');
    if (!files.length) { list.innerHTML = '<div class="empty">Ingen nedlastede videoer.</div>'; return; }
    list.innerHTML = '';
    files.forEach((f) => {
      const row = document.createElement('div');
      row.className = 'lib-item';
      row.innerHTML = '<span class="name"><b></b><small></small></span>';
      row.querySelector('b').textContent = f.name;
      row.querySelector('small').textContent = fmtBytes(f.size);
      const del = document.createElement('button');
      del.className = 'icon-btn danger'; del.textContent = '🗑'; del.title = 'Slett';
      del.addEventListener('click', () => {
        fetch('/api/storage/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: f.name }) })
          .then((r) => r.json()).then(() => loadStorage()).catch(() => {});
      });
      row.appendChild(del);
      list.appendChild(row);
    });
  }).catch((e) => { list.innerHTML = '<div class="empty">Kunne ikke lese lagring: ' + e.message + '</div>'; });
}

/* ---------- flip ---------- */
function flipBoard() { const rep = current(); if (!rep) return; rep.orientation = rep.orientation === 'black' ? 'white' : 'black'; saveStore(store); renderBoard(); }

/* ---------- autoplay ---------- */
let playTimer = null;
function isAtEnd() {
  const rep = current(); if (!rep) return true;
  const ch = currentPath.length ? nodeAt(rep, currentPath).children : rep.root.children;
  return !(ch && ch.length);
}
function stopPlay() {
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
  const b = $('#btn-play'); if (b) { b.textContent = '▶ Spill av'; b.classList.remove('primary'); }
}
function togglePlay() {
  if (playTimer) { stopPlay(); return; }
  const rep = current(); if (!rep || !rep.root.children.length) return;
  if (isAtEnd()) { currentPath = []; render(); }   // restart from the beginning
  const b = $('#btn-play'); b.textContent = '⏸ Pause'; b.classList.add('primary');
  playTimer = setInterval(() => { if (isAtEnd()) { stopPlay(); return; } goNext(); }, 850);
}

/* ---------- repertoire notes (free text, autosaved) ---------- */
function renderNotes() {
  const rep = current(); const ta = $('#rep-notes');
  if (!ta) return;
  ta.value = rep && rep.notes ? rep.notes : '';
  ta.disabled = !rep;
  ta.placeholder = rep ? 'Skriv ned tanker om åpningen …' : 'Velg en åpning først';
}

/* ---------- render all ---------- */
function render() { renderLibrary(); renderBoard(); renderMoves(); renderNotes(); }

/* ---------- wire up ---------- */
$('#btn-start').addEventListener('click', () => { stopPlay(); goStart(); });
$('#btn-prev').addEventListener('click', () => { stopPlay(); goPrev(); });
$('#btn-next').addEventListener('click', goNext);
$('#btn-play').addEventListener('click', togglePlay);
$('#btn-flip').addEventListener('click', flipBoard);
$('#btn-new').addEventListener('click', () => addRep('Ny åpning', 'lokal'));
$('#btn-import').addEventListener('click', openImport);
$('#btn-fetch').addEventListener('click', fetchFromLink);
$('#video-url').addEventListener('keydown', (e) => { if (e.key === 'Enter') fetchFromLink(); });
if (location.protocol !== 'file:') {  // storage panel needs the local server
  const sb = $('#btn-storage');
  if (sb) { sb.style.display = ''; sb.addEventListener('click', openStorage); }
}
$('#rep-notes').addEventListener('input', () => { const rep = current(); if (!rep) return; rep.notes = $('#rep-notes').value; saveStore(store); });
document.querySelectorAll('dialog [data-close]').forEach((b) => b.addEventListener('click', (e) => e.target.closest('dialog').close()));
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') goPrev();
  else if (e.key === 'ArrowRight') goNext();
  else if (e.key === 'Home') goStart();
});

render();
