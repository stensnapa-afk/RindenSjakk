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
    item.addEventListener('click', () => { currentId = rep.id; currentPath = []; pendingDelete = null; render(); });

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
  const dlg = $('#dlg-import'); $('#dlg-import-name').value = ''; $('#dlg-import-moves').value = '';
  $('#dlg-import-ok').onclick = () => {
    const name = $('#dlg-import-name').value.trim() || 'Importert';
    const moves = $('#dlg-import-moves').value.trim();
    const rep = addRep(name, 'manuell import');
    if (moves) rep.root.children.push({ san: '(se notat)', uci: '', fen: rep.root.start_fen, children: [], comment: 'Trekk: ' + moves + ' — full parsing skjer i motoren.' });
    saveStore(store); dlg.close(); render();
  };
  dlg.showModal();
}

/* ---------- flip ---------- */
function flipBoard() { const rep = current(); if (!rep) return; rep.orientation = rep.orientation === 'black' ? 'white' : 'black'; saveStore(store); renderBoard(); }

/* ---------- render all ---------- */
function render() { renderLibrary(); renderBoard(); renderMoves(); }

/* ---------- wire up ---------- */
$('#btn-start').addEventListener('click', goStart);
$('#btn-prev').addEventListener('click', goPrev);
$('#btn-next').addEventListener('click', goNext);
$('#btn-flip').addEventListener('click', flipBoard);
$('#btn-new').addEventListener('click', () => addRep('Ny åpning', 'lokal'));
$('#btn-import').addEventListener('click', openImport);
document.querySelectorAll('dialog [data-close]').forEach((b) => b.addEventListener('click', (e) => e.target.closest('dialog').close()));
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') goPrev();
  else if (e.key === 'ArrowRight') goNext();
  else if (e.key === 'Home') goStart();
});

render();
