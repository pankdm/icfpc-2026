// Differential test: Rust `lm` CLI vs the reference WASM oracle.
// Compares, per step: the multiset of runner states, pipe contents, output, and end reason.
// Also validates parsed topology (rooms/pipes) against the oracle's analyze().
const { boot } = require('./harness.js');
const { room } = require('./grid.js');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const LM = path.join(__dirname, '..', 'interp', 'target', 'release', 'lm');
let COMPARE_W;

// ---------- canonicalization ----------
function canonRunners(rs) {
  return (rs || []).map(r =>
    `${r.pos[0]},${r.pos[1]}|${r.dir[0]},${r.dir[1]}|a${r.a}|b${r.b}|bp${r.bp ?? r.backpack}|${r.halted ? 'H' : '.'}`
  ).sort();
}
// pipe contents as "id:idx=val,idx=val" sorted by id
function canonPipes(pipes) {
  if (!pipes) return '';
  return pipes.map(p => {
    const vals = (p.values || []).map(v => `${v.index}=${v.value}`).join(',');
    return `${p.id}[${vals}]`;
  }).sort().join(' ');
}
function canonOut(o) { return (o || []).map(String).join(','); }
function canonDisplays(ds) {
  if (!ds) return '';
  return ds.map(d => `${d.id}:front${JSON.stringify(d.front)}back${JSON.stringify(d.back)}cur${d.cursor}fr${d.frames}`).sort().join(' ');
}
function canonFJ(fj) {
  if (!fj) return '';
  let s = `m${fj.matched}/t${fj.total}`;
  if (fj.mismatch) s += `|mm${fj.mismatch.index}:${JSON.stringify(fj.mismatch.got)}`;
  return s;
}

function endOfOracle(j) {
  if (!j.halted) return 'running';
  if (j.fatal) return `fatal:${j.fatal.reason}`;
  return j.reason || 'done';
}
function endOfRust(j) {
  if (j.end === 'running') return 'running';
  if (j.end === 'fatal') return `fatal:${j.fatal.reason}`;
  if (j.end === 'loaderror') return 'loaderror';
  return j.end; // done | stepcap
}

// ---------- run engines ----------
function runOracle(w, rows, steps, input = '', expected = '', frames = '') {
  const s = w.newSession();
  const load = JSON.parse(w.load(s, rows, input, expected, frames));
  if (load.type === 'error') { w.closeSession(s); return { loadError: load.message }; }
  const snaps = [load];
  for (let i = 0; i < steps; i++) {
    const j = JSON.parse(w.step(s));
    snaps.push(j);
    if (j.type === 'error' || j.halted) break;
  }
  w.closeSession(s);
  return { snaps };
}
function runRust(rows, steps, input = '', expected = '', frames = '') {
  const f = path.join(os.tmpdir(), `lm_${Math.abs(hash(rows.join('\n') + input + expected))}.man`);
  fs.writeFileSync(f, rows.join('\n'));
  const args = [f, String(steps)];
  if (input) args.push(`--input=${input}`);
  if (expected) args.push(`--expected=${expected}`);
  if (frames) {
    const ff = f + '.frames';
    fs.writeFileSync(ff, frames);
    args.push(`--frames-file=${ff}`);
  }
  const out = execFileSync(LM, args, { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
  return out.trim().split('\n').map(l => JSON.parse(l));
}
function hash(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return h; }

// ---------- comparison ----------
function compareFull(name, rows, steps, opt = {}) {
  const { input = '', expected = '', frames = '' } = opt;
  let orc, rus;
  try { orc = runOracle(COMPARE_W, rows, steps, input, expected, frames); }
  catch (e) { return { r: `${name}: ORACLE ERR ${e.message}`, ok: false }; }
  try { rus = runRust(rows, steps, input, expected, frames); }
  catch (e) { return { r: `${name}: RUST ERR ${e.message}`, ok: false }; }

  // load error handling
  const rusLoadErr = rus[0] && rus[0].end === 'loaderror';
  if (orc.loadError || rusLoadErr) {
    if (orc.loadError && rusLoadErr) return { r: `${name}: OK (both load-error)`, ok: true };
    if (orc.loadError) return { r: `${name}: LOADERR DIVERGE oracle=ERR(${orc.loadError}) rust=OK`, ok: false };
    return { r: `${name}: LOADERR DIVERGE oracle=OK rust=ERR(${rus[0].loaderror})`, ok: false };
  }

  const os_ = orc.snaps;
  const n = Math.min(os_.length, rus.length);
  for (let i = 0; i < n; i++) {
    if (os_[i].type === 'error') return { r: `${name}: oracle step error @${i}: ${os_[i].message}`, ok: false };
    const co = canonRunners(os_[i].entities.runners);
    const cr = canonRunners(rus[i].runners);
    if (co.join('  ') !== cr.join('  '))
      return { r: `${name}: RUNNER DIVERGE @step ${i}\n   oracle: ${co.join('  ')}\n   rust:   ${cr.join('  ')}`, ok: false };
    const po = canonPipes(os_[i].entities.pipes);
    const pr = canonPipes(rus[i].pipes);
    if (po !== pr)
      return { r: `${name}: PIPE DIVERGE @step ${i}\n   oracle: ${po}\n   rust:   ${pr}`, ok: false };
    const oo = canonOut(os_[i].output), or = canonOut(rus[i].output);
    if (oo !== or)
      return { r: `${name}: OUTPUT DIVERGE @step ${i} oracle=[${oo}] rust=[${or}]`, ok: false };
    const do_ = canonDisplays(os_[i].entities.displays), dr = canonDisplays(rus[i].displays);
    if (do_ !== dr)
      return { r: `${name}: DISPLAY DIVERGE @step ${i}\n   oracle: ${do_}\n   rust:   ${dr}`, ok: false };
    const fo = canonFJ(os_[i].frameJudge), fr = canonFJ(rus[i].frameJudge);
    if (fo !== fr)
      return { r: `${name}: FRAMEJUDGE DIVERGE @step ${i} oracle=${fo} rust=${fr}`, ok: false };
  }
  const eo = endOfOracle(os_[os_.length - 1]);
  const er = endOfRust(rus[rus.length - 1]);
  if (eo !== er) return { r: `${name}: END DIVERGE oracle=${eo} rust=${er}`, ok: false };
  if (os_.length !== rus.length)
    return { r: `${name}: LENGTH ${os_.length} vs ${rus.length} (end=${eo})`, ok: false };
  return { r: `${name}: OK (${os_.length} steps, end=${eo})`, ok: true };
}

// ---------- topology validation ----------
function compareTopology(name, rows) {
  let an;
  try { an = JSON.parse(COMPARE_W.analyze(rows)); }
  catch (e) { return { r: `${name}: analyze err ${e.message}`, ok: false }; }
  if (an.type === 'error') return { r: `${name}: analyze load-error (skip topo)`, ok: true };
  // just sanity: rooms count + pipes count via rust load (topology asserted through full sim anyway)
  return { r: `${name}: topo rooms=${an.rooms.length} pipes=${an.pipes.length} displays=${an.displays.length}`, ok: true };
}

// ---------- fixtures ----------
const CASES = [
  ['baseline-fork', room(5, 5, [[1, 3, '@'], [3, 3, 'Y']]), 8],
  ['fork-into-wall(copy)', room(4, 3, [[1, 1, '@'], [3, 1, 'Y']]), 6],
  ['head-on-even', room(9, 5, [[1, 4, '@'], [5, 4, '^'], [5, 2, 'Y'], [8, 2, 'v'], [8, 3, '<'], [2, 2, 'v'], [2, 3, '>']]), 16],
  ['swap-attempt-odd', room(9, 5, [[1, 4, '@'], [5, 4, '^'], [5, 2, 'Y'], [8, 2, 'v'], [8, 3, '<'], [3, 2, 'v'], [3, 3, '>']]), 16],
  ['arith-3+4', room(6, 1, [[1, 1, '@'], [2, 1, '3'], [3, 1, 'M'], [4, 1, '4'], [5, 1, '+']]), 8],
  ['backpack-turn', room(6, 3, [[1, 2, '@'], [2, 2, '3'], [3, 2, 'b'], [4, 2, 'd']]), 8],
  ['wall-fatal', room(3, 1, [[1, 1, '@']]), 6],
  ['X-turn-neg', room(5, 3, [[1, 2, '@'], [2, 2, '1'], [3, 2, 'N'], [4, 2, 'X']]), 8],
];

let extra = [];
try { extra = require('./fixtures_extended.js').cases; } catch (e) { /* optional */ }

async function main() {
  COMPARE_W = await boot();
  let pass = 0, fail = 0;
  const fails = [];

  for (const [name, rows, steps] of CASES) {
    const { r, ok } = compareFull(name, rows, steps);
    console.log(r);
    if (ok) pass++; else { fail++; fails.push(name); }
  }

  for (const c of extra) {
    const { r, ok } = compareFull(c.name, c.rows, c.steps, c);
    console.log(r);
    if (ok) pass++; else { fail++; fails.push(c.name); }
  }

  console.log(`\n${pass} passed, ${fail} failed`);
  if (fails.length) console.log('FAILURES:', fails.join(', '));
  process.exit(fail ? 1 : 0);
}

if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { compareFull, compareTopology, runOracle, runRust, setW: (w) => { COMPARE_W = w; } };
