// profile.js — unified per-cell + per-man profiler for littleman solutions.
// Runs a real cached test case to settle, then attributes every man-tick to a
// grid cell and a class (compute / turn / nop-glide / stall), so you can see
// exactly where a solution burns ticks: long walks, stall hotspots, dead cells.
//
//   node sim/profile.js <slug> <file.man> [caseIdx] [--cap=N] [--json]
//
// Output: per-man table (find the critical-path man), global class split,
// stall attribution (empty-recv vs full-send), hottest cells, and two ASCII
// heatmaps overlaid on the program grid (ACTIVITY = total visits, STALL = blocks).
const { boot } = require(__dirname + '/harness.js');
const lib = require(__dirname + '/../tools/lib.js');
const fs = require('fs'), path = require('path');

const TURN = new Set(['<', '>', '^', 'v', 'V']);
const NOP = new Set([' ', '.', '']);
const clsGlyph = ch => TURN.has(ch) ? 'turn' : NOP.has(ch) ? 'nop' : 'op';
const RAMP = ' .:-=+*o%#@';                       // visit-count heat ramp (log-scaled)
const heat = (v, max) => v === 0 ? ' ' :
  RAMP[Math.min(RAMP.length - 1, 1 + Math.floor((RAMP.length - 2) * Math.log(1 + v) / Math.log(1 + max)))];
const pct = (k, tot) => (100 * k / (tot || 1)).toFixed(0) + '%';

(async () => {
  const argv = process.argv.slice(2);
  const flags = argv.filter(a => a.startsWith('--'));
  const pos = argv.filter(a => !a.startsWith('--'));
  const [slug, file, ciRaw] = pos;
  const ci = parseInt(ciRaw || '0', 10);
  const capF = flags.find(f => f.startsWith('--cap='));
  const maxTicks = capF ? parseInt(capF.split('=')[1], 10) : 80000;   // cap 1-tick stepping (big cases repeat)
  const asJson = flags.includes('--json');

  const problem = JSON.parse(fs.readFileSync(path.join(__dirname + '/../tests', slug + '.json'), 'utf8'));
  const tc = problem.publicTestData[ci];
  if (!tc) { console.log(`no case ${ci} for ${slug}`); process.exit(1); }
  const { input, expected, framesJson } = lib.buildCase(tc);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const W = Math.max(...rows.map(r => r.length)), H = rows.length;
  const glyph = (x, y) => (rows[y] && rows[y][x]) || ' ';
  const idx = (x, y) => y * W + x;
  const fp = lib.footprint(rows);

  const w = await boot(); const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, expected, framesJson));
  if (j.type === 'error') { console.log('LOAD ERROR:', j.message); process.exit(1); }

  const V = new Int32Array(W * H), ST = new Int32Array(W * H);       // visits, stalls per cell
  const per = new Map();                                             // manId -> class counts
  const prev = new Map();
  const kind = { recv: 0, send: 0, other: 0 };
  const cap = Math.min(problem.tickCap || 5e6, maxTicks);
  let truncated = false;

  while (!j.halted && !j.outputSettled && j.step < cap) {
    for (const r of (j.entities?.runners || [])) {
      if (r.halted) continue;
      const [x, y] = r.pos, g = glyph(x, y), i = idx(x, y);
      if (!per.has(r.id)) per.set(r.id, { op: 0, turn: 0, nop: 0, stall: 0, send: 0, recv: 0 });
      const p = per.get(r.id);
      const key = `${r.pos},${r.a},${r.b},${r.backpack}`;
      V[i]++;
      if (prev.get(r.id) === key) {                                 // unchanged => blocked
        ST[i]++; p.stall++;
        if ('rRU'.includes(g)) { kind.recv++; p.recv++; }
        else if ('sS'.includes(g)) { kind.send++; p.send++; }
        else kind.other++;
      } else {
        const c = clsGlyph(g);
        p[c]++;
        if (c === 'op' && 'sS'.includes(g)) p.send++;
      }
      prev.set(r.id, key);
    }
    const nj = JSON.parse(w.stepN(s, 1, false));
    if (nj.type === 'error' || nj.step === j.step) { j = nj; break; }
    j = nj;
  }
  if (!j.halted && !j.outputSettled && j.step >= cap) truncated = true;
  w.closeSession(s);

  // ---- aggregate ----
  const G = { op: 0, turn: 0, nop: 0, stall: 0 };
  for (const p of per.values()) { G.op += p.op; G.turn += p.turn; G.nop += p.nop; G.stall += p.stall; }
  const manTicks = G.op + G.turn + G.nop + G.stall;
  const men = [...per.entries()].map(([id, p]) => ({ id, ...p, tot: p.op + p.turn + p.nop + p.stall }))
    .sort((a, b) => b.op - a.op);
  const crit = men[0];                                              // most-compute man ~ critical path

  if (asJson) {
    console.log(JSON.stringify({ slug, file, ci, settle: j.step, truncated, box: fp.box, W, H, global: G, manTicks, men,
      stallKind: kind, cells: [...V].map((v, i) => ({ x: i % W, y: (i / W | 0), g: glyph(i % W, i / W | 0), v, stall: ST[i] })).filter(c => c.v) }));
    process.exit(0);
  }

  const hot = [...V].map((v, i) => [v, i]).filter(a => a[0]).sort((a, b) => b[0] - a[0]).slice(0, 10);
  const stallCells = [...ST].map((v, i) => [v, i]).filter(a => a[0]).sort((a, b) => b[0] - a[0]).slice(0, 8);
  const maxV = Math.max(1, ...V), maxST = Math.max(1, ...ST);

  console.log(`\n=== ${path.basename(file)}  [${slug} case ${ci}: ${(tc.rounds ? tc.rounds[0] : tc).in?.slice(0, 3).join('x') || '?'}] ===`);
  console.log(`settle=${j.step}${truncated ? ` (TRUNCATED at cap ${cap}; pattern repeats)` : ''}  box=${fp.box} (${fp.w}x${fp.h})  manTicks=${manTicks}`);
  console.log(`GLOBAL  compute ${G.op}(${pct(G.op, manTicks)})  turn ${G.turn}(${pct(G.turn, manTicks)})  nop/glide ${G.nop}(${pct(G.nop, manTicks)})  stall ${G.stall}(${pct(G.stall, manTicks)})`);
  console.log(`WASTED (turn+nop+stall) = ${pct(G.turn + G.nop + G.stall, manTicks)}`);
  console.log(`\nPER-MAN (critical path = most compute):`);
  for (const m of men) console.log(`  man#${m.id}${m.id === crit.id ? ' *' : '  '} tot ${String(m.tot).padStart(7)}  op ${pct(m.op, m.tot).padStart(4)} [send ${m.send}]  turn ${pct(m.turn, m.tot).padStart(4)}  nop ${pct(m.nop, m.tot).padStart(4)}  stall ${pct(m.stall, m.tot).padStart(4)} [recv ${m.recv}/send ${m.send}]`);
  console.log(`\nSTALL kind: RECV(empty upstream) ${pct(kind.recv, G.stall)}  SEND(full downstream) ${pct(kind.send, G.stall)}  OTHER ${pct(kind.other, G.stall)}`);
  console.log(`STALL hotspots:`); stallCells.forEach(([v, i]) => console.log(`  ${String(v).padStart(7)}  (${i % W},${(i / W | 0)}) '${glyph(i % W, i / W | 0)}'`));
  console.log(`HOT cells (most man-ticks):`); hot.forEach(([v, i]) => console.log(`  ${String(v).padStart(7)}  (${i % W},${(i / W | 0)}) '${glyph(i % W, i / W | 0)}'`));

  const render = (arr, mx, label) => {
    console.log(`\n${label} heatmap  (ramp "${RAMP.trim()}" low->high):`);
    for (let y = 0; y < H; y++) {
      let line = '';
      for (let x = 0; x < W; x++) line += arr[idx(x, y)] ? heat(arr[idx(x, y)], mx) : (glyph(x, y) === ' ' ? ' ' : '·');
      if (line.trimEnd()) console.log(line.replace(/\s+$/, ''));
    }
  };
  render(V, maxV, 'ACTIVITY (visits; · = structural but never executed)');
  render(ST, maxST, 'STALL (blocked ticks)');
  process.exit(0);
})().catch(e => { console.error(String(e).slice(0, 400)); process.exit(1); });
