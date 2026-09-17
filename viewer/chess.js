/* RindenSjakk — minimal, dependency-free chess engine (vanilla JS).
   Purpose: legal-move generation, SAN <-> move, FEN, so the viewer can import
   real PGN (variations, comments) into its move tree with correct positions —
   no server, no npm. Board index 0 = a8 (top-left), 63 = h1 (bottom-right):
   row = 8 - rank, col = file(0=a). Exposed as window.RindenChess. */
(function (root) {
  'use strict';

  var START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

  function fileOf(i) { return i % 8; }
  function rowOf(i) { return (i / 8) | 0; }
  function rankOf(i) { return 8 - rowOf(i); }
  function idx(row, col) { return row * 8 + col; }
  function onBoard(row, col) { return row >= 0 && row < 8 && col >= 0 && col < 8; }
  function sqName(i) { return 'abcdefgh'[fileOf(i)] + rankOf(i); }
  function parseSq(name) {
    var col = 'abcdefgh'.indexOf(name[0]);
    var rank = parseInt(name[1], 10);
    return idx(8 - rank, col);
  }

  function isWhitePiece(p) { return p && p === p.toUpperCase(); }
  function colorOf(p) { return isWhitePiece(p) ? 'w' : 'b'; }

  // ---- FEN ----
  function parseFEN(fen) {
    var parts = String(fen).trim().split(/\s+/);
    var rows = parts[0].split('/');
    var board = new Array(64).fill(null);
    for (var r = 0; r < 8; r++) {
      var c = 0;
      for (var k = 0; k < rows[r].length; k++) {
        var ch = rows[r][k];
        if (/\d/.test(ch)) { c += parseInt(ch, 10); }
        else { board[idx(r, c)] = ch; c++; }
      }
    }
    return {
      board: board,
      turn: parts[1] || 'w',
      castling: parts[2] || '-',
      ep: (parts[3] && parts[3] !== '-') ? parseSq(parts[3]) : -1,
      half: parts[4] ? parseInt(parts[4], 10) : 0,
      full: parts[5] ? parseInt(parts[5], 10) : 1
    };
  }

  function toFEN(s) {
    var rows = [];
    for (var r = 0; r < 8; r++) {
      var run = 0, line = '';
      for (var c = 0; c < 8; c++) {
        var p = s.board[idx(r, c)];
        if (p) { if (run) { line += run; run = 0; } line += p; }
        else run++;
      }
      if (run) line += run;
      rows.push(line);
    }
    var ep = s.ep >= 0 ? sqName(s.ep) : '-';
    var castling = s.castling && s.castling.length ? s.castling : '-';
    return rows.join('/') + ' ' + s.turn + ' ' + castling + ' ' + ep + ' ' + s.half + ' ' + s.full;
  }

  function clone(s) {
    return { board: s.board.slice(), turn: s.turn, castling: s.castling, ep: s.ep, half: s.half, full: s.full };
  }

  var KNIGHT = [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]];
  var KING = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
  var BISHOP = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
  var ROOK = [[-1, 0], [1, 0], [0, -1], [0, 1]];

  // Is square `target` attacked by side `by` ('w'|'b')?
  function isAttacked(board, target, by) {
    var tr = rowOf(target), tc = fileOf(target), i, r, c, p;
    // pawns: a white pawn at (tr+1, tc±1) attacks target; black pawn at (tr-1, tc±1).
    var pr = by === 'w' ? tr + 1 : tr - 1;
    for (var dc = -1; dc <= 1; dc += 2) {
      if (onBoard(pr, tc + dc)) {
        p = board[idx(pr, tc + dc)];
        if (p && colorOf(p) === by && p.toUpperCase() === 'P') return true;
      }
    }
    // knights
    for (i = 0; i < KNIGHT.length; i++) {
      r = tr + KNIGHT[i][0]; c = tc + KNIGHT[i][1];
      if (onBoard(r, c)) { p = board[idx(r, c)]; if (p && colorOf(p) === by && p.toUpperCase() === 'N') return true; }
    }
    // king
    for (i = 0; i < KING.length; i++) {
      r = tr + KING[i][0]; c = tc + KING[i][1];
      if (onBoard(r, c)) { p = board[idx(r, c)]; if (p && colorOf(p) === by && p.toUpperCase() === 'K') return true; }
    }
    // sliders: bishop/queen (diagonals), rook/queen (orthogonals)
    var dirs = [[BISHOP, 'BQ'], [ROOK, 'RQ']];
    for (var d = 0; d < dirs.length; d++) {
      var set = dirs[d][0], letters = dirs[d][1];
      for (i = 0; i < set.length; i++) {
        r = tr + set[i][0]; c = tc + set[i][1];
        while (onBoard(r, c)) {
          p = board[idx(r, c)];
          if (p) {
            if (colorOf(p) === by && letters.indexOf(p.toUpperCase()) >= 0) return true;
            break;
          }
          r += set[i][0]; c += set[i][1];
        }
      }
    }
    return false;
  }

  function kingSquare(board, color) {
    var target = color === 'w' ? 'K' : 'k';
    for (var i = 0; i < 64; i++) if (board[i] === target) return i;
    return -1;
  }

  // pseudo-legal moves for the side to move
  function pseudoMoves(s) {
    var moves = [], board = s.board, us = s.turn, them = us === 'w' ? 'b' : 'w';
    for (var i = 0; i < 64; i++) {
      var p = board[i];
      if (!p || colorOf(p) !== us) continue;
      var type = p.toUpperCase(), r = rowOf(i), c = fileOf(i), j, tr, tc, q, dir, startRow, promoRow;
      if (type === 'P') {
        dir = us === 'w' ? -1 : 1;
        startRow = us === 'w' ? 6 : 1;
        promoRow = us === 'w' ? 0 : 7;
        // single push
        if (onBoard(r + dir, c) && !board[idx(r + dir, c)]) {
          addPawn(moves, i, idx(r + dir, c), r + dir === promoRow, false, false);
          // double push
          if (r === startRow && !board[idx(r + 2 * dir, c)]) {
            moves.push({ from: i, to: idx(r + 2 * dir, c), piece: p, capture: false, promotion: null, castle: null, ep: false, dbl: true });
          }
        }
        // captures + en passant
        for (var ddc = -1; ddc <= 1; ddc += 2) {
          tr = r + dir; tc = c + ddc;
          if (!onBoard(tr, tc)) continue;
          var to = idx(tr, tc), tp = board[to];
          if (tp && colorOf(tp) === them) addPawn(moves, i, to, tr === promoRow, true, false);
          else if (to === s.ep && s.ep >= 0) addPawn(moves, i, to, false, true, true);
        }
      } else if (type === 'N') {
        for (j = 0; j < KNIGHT.length; j++) {
          tr = r + KNIGHT[j][0]; tc = c + KNIGHT[j][1];
          if (!onBoard(tr, tc)) continue;
          q = board[idx(tr, tc)];
          if (!q || colorOf(q) === them) moves.push(mk(i, idx(tr, tc), p, !!q));
        }
      } else if (type === 'K') {
        for (j = 0; j < KING.length; j++) {
          tr = r + KING[j][0]; tc = c + KING[j][1];
          if (!onBoard(tr, tc)) continue;
          q = board[idx(tr, tc)];
          if (!q || colorOf(q) === them) moves.push(mk(i, idx(tr, tc), p, !!q));
        }
        // castling
        addCastles(s, moves, i, us);
      } else { // sliders
        var set = type === 'B' ? BISHOP : type === 'R' ? ROOK : BISHOP.concat(ROOK);
        for (j = 0; j < set.length; j++) {
          tr = r + set[j][0]; tc = c + set[j][1];
          while (onBoard(tr, tc)) {
            var t2 = idx(tr, tc), oc = board[t2];
            if (!oc) { moves.push(mk(i, t2, p, false)); }
            else { if (colorOf(oc) === them) moves.push(mk(i, t2, p, true)); break; }
            tr += set[j][0]; tc += set[j][1];
          }
        }
      }
    }
    return moves;
  }

  function mk(from, to, piece, capture) {
    return { from: from, to: to, piece: piece, capture: capture, promotion: null, castle: null, ep: false, dbl: false };
  }
  function addPawn(moves, from, to, promo, capture, ep) {
    if (promo) {
      ['Q', 'R', 'B', 'N'].forEach(function (pr) {
        moves.push({ from: from, to: to, piece: null, capture: capture, promotion: pr, castle: null, ep: ep, dbl: false });
      });
    } else {
      moves.push({ from: from, to: to, piece: null, capture: capture, promotion: null, castle: null, ep: ep, dbl: false });
    }
  }
  function addCastles(s, moves, kingIdx, us) {
    var rights = s.castling, board = s.board, them = us === 'w' ? 'b' : 'w';
    var row = us === 'w' ? 7 : 0;
    if (kingIdx !== idx(row, 4)) return;               // king must be on e1/e8
    if (isAttacked(board, kingIdx, them)) return;      // not out of check
    var kSide = us === 'w' ? 'K' : 'k', qSide = us === 'w' ? 'Q' : 'q';
    if (rights.indexOf(kSide) >= 0 && !board[idx(row, 5)] && !board[idx(row, 6)] &&
        board[idx(row, 7)] === (us === 'w' ? 'R' : 'r') &&
        !isAttacked(board, idx(row, 5), them) && !isAttacked(board, idx(row, 6), them)) {
      moves.push({ from: kingIdx, to: idx(row, 6), piece: board[kingIdx], capture: false, promotion: null, castle: kSide, ep: false, dbl: false });
    }
    if (rights.indexOf(qSide) >= 0 && !board[idx(row, 3)] && !board[idx(row, 2)] && !board[idx(row, 1)] &&
        board[idx(row, 0)] === (us === 'w' ? 'R' : 'r') &&
        !isAttacked(board, idx(row, 3), them) && !isAttacked(board, idx(row, 2), them)) {
      moves.push({ from: kingIdx, to: idx(row, 2), piece: board[kingIdx], capture: false, promotion: null, castle: qSide, ep: false, dbl: false });
    }
  }

  // apply a (legal or pseudo-legal) move, returning the new state
  function apply(s, m) {
    var n = clone(s), board = n.board, us = s.turn, them = us === 'w' ? 'b' : 'w';
    var moving = board[m.from];
    var movingType = moving ? moving.toUpperCase() : 'P';
    board[m.to] = moving;
    board[m.from] = null;
    // en passant capture removes the pawn behind the target
    if (m.ep) {
      var capRow = rowOf(m.to) + (us === 'w' ? 1 : -1);
      board[idx(capRow, fileOf(m.to))] = null;
    }
    // promotion
    if (m.promotion) board[m.to] = us === 'w' ? m.promotion : m.promotion.toLowerCase();
    // castling: move the rook
    if (m.castle) {
      var row = us === 'w' ? 7 : 0;
      if (m.castle === 'K' || m.castle === 'k') { board[idx(row, 5)] = board[idx(row, 7)]; board[idx(row, 7)] = null; }
      else { board[idx(row, 3)] = board[idx(row, 0)]; board[idx(row, 0)] = null; }
    }
    // update castling rights
    var rights = n.castling.replace('-', '');
    function drop(ch) { rights = rights.replace(ch, ''); }
    if (movingType === 'K') { drop(us === 'w' ? 'K' : 'Q'); if (us === 'w') { drop('K'); drop('Q'); } else { drop('k'); drop('q'); } }
    // rook moved from / rook captured on corner squares
    if (m.from === parseSq('h1') || m.to === parseSq('h1')) drop('K');
    if (m.from === parseSq('a1') || m.to === parseSq('a1')) drop('Q');
    if (m.from === parseSq('h8') || m.to === parseSq('h8')) drop('k');
    if (m.from === parseSq('a8') || m.to === parseSq('a8')) drop('q');
    n.castling = rights.length ? rights : '-';
    // en passant target
    n.ep = (movingType === 'P' && m.dbl) ? idx(rowOf(m.from) + (us === 'w' ? -1 : 1), fileOf(m.from)) : -1;
    // clocks
    n.half = (movingType === 'P' || m.capture) ? 0 : n.half + 1;
    if (us === 'b') n.full = n.full + 1;
    n.turn = them;
    return n;
  }

  function legalMoves(s) {
    var us = s.turn, out = [], pseudo = pseudoMoves(s);
    for (var i = 0; i < pseudo.length; i++) {
      var n = apply(s, pseudo[i]);
      var ks = kingSquare(n.board, us);
      if (ks >= 0 && !isAttacked(n.board, ks, us === 'w' ? 'b' : 'w')) out.push(pseudo[i]);
    }
    return out;
  }

  function inCheck(s) {
    var ks = kingSquare(s.board, s.turn);
    return ks >= 0 && isAttacked(s.board, ks, s.turn === 'w' ? 'b' : 'w');
  }

  // SAN for a move given the position `s` (uses full legal list for disambiguation)
  function moveToSAN(s, m, legal) {
    legal = legal || legalMoves(s);
    var suffix = '';
    var after = apply(s, m);
    if (inCheck(after)) suffix = legalMoves(after).length === 0 ? '#' : '+';
    if (m.castle === 'K' || m.castle === 'k') return 'O-O' + suffix;
    if (m.castle === 'Q' || m.castle === 'q') return 'O-O-O' + suffix;
    var piece = (m.piece || (s.board[m.from])) || '';
    var type = piece.toUpperCase();
    var dest = sqName(m.to);
    if (type === 'P') {
      var body = m.capture ? ('abcdefgh'[fileOf(m.from)] + 'x' + dest) : dest;
      if (m.promotion) body += '=' + m.promotion;
      return body + suffix;
    }
    // disambiguation among same-type pieces that can also reach m.to
    var sameFile = false, sameRank = false, ambiguous = false;
    for (var i = 0; i < legal.length; i++) {
      var o = legal[i];
      if (o.from === m.from || o.to !== m.to) continue;
      var op = (o.piece || s.board[o.from]);
      if (!op || op.toUpperCase() !== type) continue;
      ambiguous = true;
      if (fileOf(o.from) === fileOf(m.from)) sameFile = true;
      if (rowOf(o.from) === rowOf(m.from)) sameRank = true;
    }
    var dis = '';
    if (ambiguous) {
      if (!sameFile) dis = 'abcdefgh'[fileOf(m.from)];
      else if (!sameRank) dis = String(rankOf(m.from));
      else dis = sqName(m.from);
    }
    return type + dis + (m.capture ? 'x' : '') + dest + suffix;
  }

  // find the legal move matching a SAN token (strips !?+# and glyphs)
  function moveFromSAN(s, san) {
    var clean = String(san).replace(/[+#!?]+$/g, '').replace(/[!?]+/g, '').trim();
    clean = clean.replace(/^0-0-0$/, 'O-O-O').replace(/^0-0$/, 'O-O');
    var legal = legalMoves(s);
    for (var i = 0; i < legal.length; i++) {
      var gen = moveToSAN(s, legal[i], legal).replace(/[+#]+$/g, '');
      if (gen === clean) return legal[i];
    }
    // tolerant fallback: compare without check/annotation & optional '='/promotion case
    var target = clean.replace(/=/, '').toUpperCase();
    for (var k = 0; k < legal.length; k++) {
      var g2 = moveToSAN(s, legal[k], legal).replace(/[+#]+$/g, '').replace(/=/, '').toUpperCase();
      if (g2 === target) return legal[k];
    }
    return null;
  }

  function uciOf(m) {
    return sqName(m.from) + sqName(m.to) + (m.promotion ? m.promotion.toLowerCase() : '');
  }

  root.RindenChess = {
    START_FEN: START_FEN,
    parseFEN: parseFEN, toFEN: toFEN, clone: clone,
    legalMoves: legalMoves, apply: apply, inCheck: inCheck,
    moveToSAN: moveToSAN, moveFromSAN: moveFromSAN, uciOf: uciOf,
    sqName: sqName, parseSq: parseSq
  };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
