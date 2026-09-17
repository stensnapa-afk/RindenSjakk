/* RindenSjakk — PGN import (vanilla JS, no deps). Turns real PGN text (with
   variations, comments, NAGs, multiple games, optional FEN setup) into the
   viewer's repertoire tree. Depends on window.RindenChess. Exposed as
   window.RindenPGN.parse(text) -> { reps: [...], errors: [...] }.

   Tree node: { san, uci, fen, children: [], comment? }
   Rep:       { id?, name, source, orientation, root: { start_fen, children } } */
(function (root) {
  'use strict';
  var C = root.RindenChess;

  // ---- split a multi-game PGN into { tags, movetext } records ----
  function splitGames(text) {
    var lines = String(text).replace(/\r\n?/g, '\n').split('\n');
    var games = [], cur = null, inMoves = false;
    var isTagLine = /^\s*\[\w+\s+"/;                 // line begins a tag section
    var pairRe = /\[(\w+)\s+"([\s\S]*?)"\]/g;        // one or more pairs on the line
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (isTagLine.test(line)) {
        if (inMoves && cur) { games.push(cur); cur = null; inMoves = false; }  // new game begins
        if (!cur) cur = { tags: {}, movetext: '' };
        var pm; pairRe.lastIndex = 0;
        while ((pm = pairRe.exec(line))) cur.tags[pm[1]] = pm[2];
      } else {
        if (line.trim() === '' && !cur) continue;
        if (!cur) cur = { tags: {}, movetext: '' };
        if (line.trim() !== '') inMoves = true;
        cur.movetext += line + '\n';
      }
    }
    if (cur) games.push(cur);
    // drop empty shells
    return games.filter(function (g) { return g.movetext.trim() || Object.keys(g.tags).length; });
  }

  // ---- tokenize movetext ----
  function tokenize(mt) {
    var toks = [], i = 0, n = mt.length;
    var RESULT = /^(1-0|0-1|1\/2-1\/2|\*)$/;
    while (i < n) {
      var ch = mt[i];
      if (ch === ' ' || ch === '\n' || ch === '\t' || ch === '\r') { i++; continue; }
      if (ch === '{') {
        var j = mt.indexOf('}', i + 1); if (j < 0) j = n;
        toks.push({ t: 'comment', v: mt.slice(i + 1, j).replace(/\s+/g, ' ').trim() });
        i = j + 1; continue;
      }
      if (ch === ';') { // line comment to EOL
        var e = mt.indexOf('\n', i); if (e < 0) e = n;
        toks.push({ t: 'comment', v: mt.slice(i + 1, e).trim() });
        i = e + 1; continue;
      }
      if (ch === '(') { toks.push({ t: '(' }); i++; continue; }
      if (ch === ')') { toks.push({ t: ')' }); i++; continue; }
      if (ch === '$') { // NAG
        var k = i + 1; while (k < n && /\d/.test(mt[k])) k++;
        toks.push({ t: 'nag', v: mt.slice(i, k) }); i = k; continue;
      }
      // a word: read until whitespace or a delimiter
      var w = i;
      while (w < n && ' \n\t\r{}();'.indexOf(mt[w]) < 0) w++;
      var word = mt.slice(i, w); i = w;
      if (!word) continue;
      // strip leading move number(s): "12.", "12...", "12.e4"
      word = word.replace(/^\d+\.(\.\.)?/, '');
      if (!word) continue;
      if (RESULT.test(word)) { toks.push({ t: 'result', v: word }); continue; }
      if (/^\d+$/.test(word)) continue;             // stray move number
      toks.push({ t: 'san', v: word });
    }
    return toks;
  }

  // ---- build a tree from tokens ----
  function buildLine(toks, pos, state, nextArray, errors) {
    var branchArray = nextArray;   // array holding the last move (variations branch here)
    var preState = null;           // position before the last move
    var lastNode = null;
    var pending = null;            // comment awaiting the next move
    while (pos < toks.length) {
      var tok = toks[pos];
      if (tok.t === ')') return pos + 1;
      if (tok.t === '(') {
        if (preState) pos = buildLine(toks, pos + 1, C.clone(preState), branchArray, errors);
        else pos = skipVariation(toks, pos + 1);
        continue;
      }
      if (tok.t === 'comment') {
        if (lastNode) lastNode.comment = (lastNode.comment ? lastNode.comment + ' ' : '') + tok.v;
        else pending = (pending ? pending + ' ' : '') + tok.v;
        pos++; continue;
      }
      if (tok.t === 'nag' || tok.t === 'result') { pos++; continue; }
      if (tok.t === 'san') {
        var m = C.moveFromSAN(state, tok.v);
        if (!m) { errors.push(tok.v); pos++; continue; }
        var after = C.apply(state, m);
        var node = { san: C.moveToSAN(state, m), uci: C.uciOf(m), fen: C.toFEN(after), children: [] };
        if (pending) { node.comment = pending; pending = null; }
        nextArray.push(node);
        branchArray = nextArray;
        preState = state;
        state = after;
        lastNode = node;
        nextArray = node.children;
        pos++; continue;
      }
      pos++;
    }
    return pos;
  }

  function skipVariation(toks, pos) {
    var depth = 1;
    while (pos < toks.length && depth > 0) {
      if (toks[pos].t === '(') depth++;
      else if (toks[pos].t === ')') depth--;
      pos++;
    }
    return pos;
  }

  function nameFrom(tags) {
    if (tags.Opening) return tags.Opening + (tags.Variation ? ', ' + tags.Variation : '');
    if (tags.Event && tags.Event !== '?') {
      if (tags.White && tags.Black) return tags.Event + ' — ' + tags.White + ' vs ' + tags.Black;
      return tags.Event;
    }
    if (tags.White && tags.Black) return tags.White + ' vs ' + tags.Black;
    return null;
  }

  function parse(text) {
    if (!C) throw new Error('RindenChess mangler (last chess.js foer pgn.js)');
    var games = splitGames(text), reps = [], errors = [];
    for (var g = 0; g < games.length; g++) {
      var tags = games[g].tags;
      var startFen = (tags.FEN && (tags.SetUp === '1' || tags.SetUp === undefined)) ? tags.FEN : C.START_FEN;
      // validate FEN; fall back to standard start if unparseable
      var startState;
      try { startState = C.parseFEN(startFen); C.toFEN(startState); }
      catch (e) { startFen = C.START_FEN; startState = C.parseFEN(startFen); }
      var toks = tokenize(games[g].movetext);
      if (!toks.some(function (t) { return t.t === 'san'; }) && !tags.FEN) continue;
      var root = { start_fen: startFen, children: [] };
      var gErr = [];
      buildLine(toks, 0, C.clone(startState), root.children, gErr);
      // orientation: if the setup position has Black to move, show from Black.
      var orientation = /\s+b\s+/.test(' ' + startFen + ' ') ? 'black' : 'white';
      reps.push({
        name: nameFrom(tags) || ('Importert PGN' + (games.length > 1 ? ' #' + (g + 1) : '')),
        source: 'PGN-import',
        orientation: orientation,
        root: root
      });
      for (var e = 0; e < gErr.length; e++) errors.push(gErr[e]);
    }
    return { reps: reps, errors: errors };
  }

  root.RindenPGN = { parse: parse, splitGames: splitGames, tokenize: tokenize };
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
