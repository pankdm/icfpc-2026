// xray.js — decision-grade profiler for littleman solutions. Beyond profile.js's
// heatmaps, it answers the questions that drive optimization CHOICES:
//   1. HEADROOM   — the ceiling of each lever: if glide/turn/stall were 0, what avgTicks/score?
//   2. BOX DRIVER — which dimension bounds the box, which interior rows/cols are empty
//                   (mechanical-compaction targets), and the box/score after deleting them.
//   3. CORRIDORS  — the longest blank runs the critical man walks, ranked (the tick-cut targets).
//   4. DOMINANT   — across ALL public cases, which case sets avgTicks (the one to optimize).
//
//   node sim/xray.js <slug> <file.man> [caseIdx]      deep single-case x-ray (default case = dominant)
//   node sim/xray.js <slug> <file.man> --all          per-case settle ticks + dominant case + score
//   flags: --cap=N (per-cell step cap, default 120000) --heat (also print heatmaps)
const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const lib = require('/Users/visenbaev/icfpc26/tools/lib.js');
const fs = require('fs'), path = require('path');

const TURN = new Set(['<', '>', '^', 'v', 'V']);
const NOP = new Set([' ', '.', '']);
const clsGlyph = ch => TURN.has(ch) ? 'turn' : NOP.has(ch) ? 'nop' : 'op';
const RAMP = ' .:-=+*o%#@';
const heat = (v, mx) => v === 0 ? ' ' : RAMP[Math.min(RAMP.length - 1, 1 + Math.floor((RAMP.length - 2) * Math.log(1 + v) / Math.log(1 + mx)))];
const pctS = (k, tot) => (100 * k / (tot || 1)).toFixed(1) + '%';
const fmt = n => n == null ? '?' : (n >= 1e9 ? (n / 1e9).toFixed(2) + 'B' : n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(Math.round(n)));

function loadProblem(slug) {
  return JSON.parse(fs.readFileSync(path.join('/Users/visenbaev/icfpc26/tests', slug + '.json'), 'utf8'));
}
function caseDims(tc) { const r = tc.rounds ? tc.rounds[0] : tc; return (r.in || []).slice(0, 3).join('x') || '?'; }

// Run one case to settle, chunked (fast) — returns settle tick + halted/settled.
function runSettle(w, rows, tc, tickCap) {
  const { input, expected, framesJson } = lib.buildCase(tc);
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, expected, framesJson));
  if (j.type === 'error') { w.closeSession(s); return { err: j.message }; }
  const cap = tickCap || 5e6;
  while (!j.halted && !j.outputSettled && j.step < cap) {
    const nj = JSON.parse(w.stepN(s, 5000, false));
    if (nj.type === 'error' || nj.step === j.step) { j = nj; break; }
    j = nj;
  }
  w.closeSession(s);
  return { settle: j.step, halted: !!j.halted, settled: !!j.outputSettled, capped: j.step >= cap };
}

// ---- ALL-CASES mode: which case dominates avgTicks / the score ----
async function allCases(w, rows, problem, slug, file) {
  const fp = lib.footprint(rows);
  const cases = problem.publicTestData || [];
  const out = [];
  for (let i = 0; i < cases.length; i++) {
    const r = runSettle(w, rows, cases[i], problem.tickCap);
    out.push({ i, dims: caseDims(cases[i]), ...r });
  }
  const ok = out.filter(o => o.settle != null && !o.err);
  const avg = ok.length ? ok.reduce((a, b) => a + b.settle, 0) / ok.length : null;
  const footOnly = problem.scoring === 'footprint';
  const score = footOnly ? fp.box : (avg != null ? fp.box * avg : null);
  console.log(`\n=== ${path.basename(file)} [${slug}] ALL CASES ===`);
  console.log(`box=${fp.box} (${fp.w}x${fp.h})  scoring=${footOnly ? 'FOOTPRINT-only' : 'footprint x avgTicks'}  avgTicks=${fmt(avg)}  SCORE=${fmt(score)}`);
  console.log(`\ncase  dims        settle   share-of-avg`);
  const sum = ok.reduce((a, b) => a + b.settle, 0) || 1;
  out.sort((a, b) => (b.settle || 0) - (a.settle || 0)).forEach(o =>
    console.log(`  ${String(o.i).padEnd(3)} ${String(o.dims).padEnd(11)} ${String(o.err ? 'ERR' : fmt(o.settle)).padStart(8)}   ${o.settle ? (100 * o.settle / sum).toFixed(0) + '%' : '-'}${o.capped ? '  (CAPPED)' : ''}`));
  const dom = out[0];
  console.log(`\n>> DOMINANT case = ${dom.i} (${dom.dims}, ${fmt(dom.settle)} ticks = ${(100 * dom.settle / sum).toFixed(0)}% of total). Deep-profile it:  node sim/xray.js ${slug} ${file} ${dom.i}`);
  return dom.i;
}

// ---- DEEP single-case x-ray ----
async function deep(w, rows, problem, slug, file, ci, opts) {
  const tc = problem.publicTestData[ci];
  const { input, expected, framesJson } = lib.buildCase(tc);
  const W = Math.max(...rows.map(r => r.length)), H = rows.length;
  const glyph = (x, y) => (rows[y] && rows[y][x]) || ' ';
  const idx = (x, y) => y * W + x;
  const fp = lib.footprint(rows);
  const footOnly = problem.scoring === 'footprint';

  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, expected, framesJson));
  if (j.type === 'error') { console.log('LOAD ERROR:', j.message); return; }

  const V = new Int32Array(W * H), ST = new Int32Array(W * H);
  const per = new Map(); const prev = new Map();
  const cap = Math.min(problem.tickCap || 5e6, opts.cap);
  while (!j.halted && !j.outputSettled && j.step < cap) {
    for (const r of (j.entities?.runners || [])) {
      if (r.halted) continue;
      const [x, y] = r.pos, g = glyph(x, y), i = idx(x, y);
      if (!per.has(r.id)) per.set(r.id, { op: 0, turn: 0, nop: 0, stall: 0, send: 0, recv: 0 });
      const p = per.get(r.id); const key = `${r.pos},${r.a},${r.b},${r.backpack}`;
      V[i]++;
      if (prev.get(r.id) === key) { ST[i]++; p.stall++; if ('rRU'.includes(g)) p.recv++; else if ('sS'.includes(g)) p.send++; }
      else { p[clsGlyph(g)]++; }
      prev.set(r.id, key);
    }
    const nj = JSON.parse(w.stepN(s, 1, false));
    if (nj.type === 'error' || nj.step === j.step) { j = nj; break; }
    j = nj;
  }
  const settle = j.step, capped = j.step >= cap && !j.halted && !j.outputSettled;
  w.closeSession(s);

  const men = [...per.entries()].map(([id, p]) => ({ id, ...p, tot: p.op + p.turn + p.nop + p.stall })).sort((a, b) => b.op - a.op);
  const crit = men[0] || { op: 0, turn: 0, nop: 0, stall: 0, tot: 1 };
  const G = men.reduce((a, m) => ({ op: a.op + m.op, turn: a.turn + m.turn, nop: a.nop + m.nop, stall: a.stall + m.stall }), { op: 0, turn: 0, nop: 0, stall: 0 });
  const manTicks = G.op + G.turn + G.nop + G.stall;

  console.log(`\n=== ${path.basename(file)} [${slug} case ${ci}: ${caseDims(tc)}] ===`);
  console.log(`settle=${fmt(settle)}${capped ? ` (CAPPED at ${fmt(cap)} — raise --cap for exact)` : ''}  box=${fp.box} (${fp.w}x${fp.h})  scoring=${footOnly ? 'FOOTPRINT-only' : 'box x avgTicks'}`);
  console.log(`\nGLOBAL man-ticks: compute ${pctS(G.op, manTicks)}  turn ${pctS(G.turn, manTicks)}  nop/glide ${pctS(G.nop, manTicks)}  stall ${pctS(G.stall, manTicks)}   (${men.length} men)`);
  console.log(`PER-MAN (critical = most compute):`);
  men.forEach(m => console.log(`  man#${m.id}${m.id === crit.id ? ' *CRIT' : '     '} tot ${fmt(m.tot).padStart(7)}  op ${pctS(m.op, m.tot).padStart(6)}  turn ${pctS(m.turn, m.tot).padStart(6)}  nop ${pctS(m.nop, m.tot).padStart(6)}  stall ${pctS(m.stall, m.tot).padStart(6)} [recv ${m.recv}/send ${m.send}]`));

  // ---- 1. HEADROOM: ceiling of each lever on the CRITICAL man (it defines settle) ----
  // settle ~= critical man's lifetime; eliminating a waste class caps tick reduction at that fraction.
  const base = settle;
  const lever = (label, saved) => {
    const nt = base - saved, ns = footOnly ? fp.box : fp.box * nt;
    console.log(`  ${label.padEnd(34)} avgTicks ${fmt(base)} -> ${fmt(nt)}  (-${pctS(saved, base)})   score ${fmt(footOnly ? fp.box : fp.box * base)} -> ${fmt(ns)}`);
  };
  console.log(`\n[1] HEADROOM — max effect of each lever (critical man#${crit.id}; box held constant):`);
  if (footOnly) console.log(`  (scoring is FOOTPRINT-only — ticks do not affect score; skip to [2])`);
  else {
    lever('kill GLIDE (tighten walks/corridors)', crit.nop);
    lever('kill TURN (fewer bends)', crit.turn);
    lever('kill STALL (pipe waits)', crit.stall);
    lever('kill ALL waste (theoretical floor)', crit.nop + crit.turn + crit.stall);
  }

  // ---- 2. BOX DRIVER: empty interior rows/cols = mechanical-compaction targets ----
  const rowFill = new Array(H).fill(0), colFill = new Array(W).fill(0);
  let minx = 1e9, maxx = -1, miny = 1e9, maxy = -1;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (glyph(x, y) !== ' ') {
    rowFill[y]++; colFill[x]++; if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y;
  }
  const emptyRows = []; for (let y = miny; y <= maxy; y++) if (rowFill[y] === 0) emptyRows.push(y);
  const emptyCols = []; for (let x = minx; x <= maxx; x++) if (colFill[x] === 0) emptyCols.push(x);
  const boxDim = fp.h >= fp.w ? 'HEIGHT' : 'WIDTH';
  console.log(`\n[2] BOX DRIVER — box = ${boxDim} (${Math.max(fp.w, fp.h)})²=${fp.box}. Slack dim=${Math.min(fp.w, fp.h)} (foldable down to ${Math.max(fp.w, fp.h)} free).`);
  const compact = (delRows, delCols) => {
    const nh = fp.h - delRows, nw = fp.w - delCols, nb = Math.max(nw, nh) ** 2;
    return { nw, nh, nb, gain: fp.box ? (1 - nb / fp.box) : 0 };
  };
  if (emptyRows.length) { const c = compact(emptyRows.length, 0); console.log(`  ${emptyRows.length} EMPTY interior rows (deletable, byte-identical): ${emptyRows.slice(0, 24).join(',')}${emptyRows.length > 24 ? '…' : ''}`); console.log(`    -> delete them: ${fp.w}x${fp.h} -> ${c.nw}x${c.nh}, box ${fp.box} -> ${c.nb} (-${(100 * c.gain).toFixed(0)}%)`); }
  else console.log(`  0 empty interior rows.`);
  if (emptyCols.length) { const c = compact(0, emptyCols.length); console.log(`  ${emptyCols.length} EMPTY interior cols (deletable): ${emptyCols.slice(0, 24).join(',')}${emptyCols.length > 24 ? '…' : ''}`); console.log(`    -> delete them: box ${fp.box} -> ${c.nb} (-${(100 * c.gain).toFixed(0)}%)`); }
  else console.log(`  0 empty interior cols.`);
  // sparse rows/cols near the bounding edges (near-empty = pull-in candidates)
  const sparseR = []; for (let y = miny; y <= maxy; y++) if (rowFill[y] > 0 && rowFill[y] <= 2) sparseR.push(`${y}:${rowFill[y]}`);
  const sparseC = []; for (let x = minx; x <= maxx; x++) if (colFill[x] > 0 && colFill[x] <= 2) sparseC.push(`${x}:${colFill[x]}`);
  if (sparseR.length) console.log(`  sparse rows (≤2 cells, cheap to relocate/fold): ${sparseR.slice(0, 20).join(' ')}`);
  if (sparseC.length) console.log(`  sparse cols (≤2 cells): ${sparseC.slice(0, 20).join(' ')}`);

  // ---- 3. CORRIDORS: longest blank runs the men actually walk (glide tick-cut targets) ----
  const runs = [];
  for (let y = 0; y < H; y++) { let st = -1, vis = 0, len = 0;
    for (let x = 0; x <= W; x++) { const blank = x < W && glyph(x, y) === ' ' && V[idx(x, y)] > 0;
      if (blank) { if (st < 0) { st = x; vis = 0; len = 0; } vis += V[idx(x, y)]; len++; }
      else { if (st >= 0 && len >= 3) runs.push({ len, vis, where: `row ${y} cols ${st}-${x - 1}`, dir: 'H' }); st = -1; } } }
  for (let x = 0; x < W; x++) { let st = -1, vis = 0, len = 0;
    for (let y = 0; y <= H; y++) { const blank = y < H && glyph(x, y) === ' ' && V[idx(x, y)] > 0;
      if (blank) { if (st < 0) { st = y; vis = 0; len = 0; } vis += V[idx(x, y)]; len++; }
      else { if (st >= 0 && len >= 3) runs.push({ len, vis, where: `col ${x} rows ${st}-${y - 1}`, dir: 'V' }); st = -1; } } }
  runs.sort((a, b) => b.len * b.vis - a.len * a.vis);
  console.log(`\n[3] GLIDE CORRIDORS — longest walked blank runs (len×visits = wasted man-ticks; shorten these):`);
  if (!runs.length) console.log(`  none ≥3 cells (walks are already tight).`);
  runs.slice(0, 10).forEach(r => console.log(`  ${String(r.len).padStart(3)} cells × ${String(r.vis).padStart(6)} visits = ${fmt(r.len * r.vis).padStart(6)} man-ticks   ${r.dir} ${r.where}`));

  if (opts.heat) {
    const render = (arr, label) => { const mx = Math.max(1, ...arr); console.log(`\n${label} (ramp "${RAMP.trim()}"):`);
      for (let y = 0; y < H; y++) { let line = ''; for (let x = 0; x < W; x++) line += arr[idx(x, y)] ? heat(arr[idx(x, y)], mx) : (glyph(x, y) === ' ' ? ' ' : '·'); if (line.trimEnd()) console.log(line.replace(/\s+$/, '')); } };
    render(V, 'ACTIVITY (visits)'); render(ST, 'STALL (blocked)');
  }
  console.log('');
}

(async () => {
  const argv = process.argv.slice(2);
  const flags = argv.filter(a => a.startsWith('--'));
  const pos = argv.filter(a => !a.startsWith('--'));
  const [slug, file, ciRaw] = pos;
  if (!slug || !file) { console.log('usage: node sim/xray.js <slug> <file.man> [caseIdx|--all] [--cap=N] [--heat]'); process.exit(1); }
  const opts = { cap: (flags.find(f => f.startsWith('--cap=')) || '--cap=120000').split('=')[1] | 0, heat: flags.includes('--heat') };
  const problem = loadProblem(slug);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  if (flags.includes('--all')) { await allCases(w, rows, problem, slug, file); process.exit(0); }
  let ci = ciRaw != null ? parseInt(ciRaw, 10) : null;
  if (ci == null) { console.log('(no case given — finding dominant case first…)'); ci = await allCases(w, rows, problem, slug, file); }
  await deep(w, rows, problem, slug, file, ci, opts);
  process.exit(0);
})().catch(e => { console.error(String(e).slice(0, 400)); process.exit(1); });
