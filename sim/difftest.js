// Differential test: Rust `lm` CLI vs the reference WASM oracle.
// Compares, per step, the multiset of runner states, plus the end reason.
const { boot } = require('./harness.js');
const { room } = require('./grid.js');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const LM = path.join(__dirname, '..', 'interp', 'target', 'release', 'lm');

function canonRunners(rs) {
  return rs.map(r =>
    `${r.pos[0]},${r.pos[1]}|${r.dir[0]},${r.dir[1]}|a${r.a}|b${r.b}|bp${r.bp ?? r.backpack}|${r.halted ? 'H' : '.'}`
  ).sort();
}
function endOfOracle(j) {
  if (!j.halted) return 'running';
  if (j.fatal) return `fatal:${j.fatal.reason}`;
  return j.reason || 'done';
}
function endOfRust(j) {
  if (j.end === 'running') return 'running';
  if (j.end === 'fatal') return `fatal:${j.fatal.reason}`;
  return j.end; // done | stepcap
}

function runOracle(w, rows, steps) {
  const s = w.newSession();
  const snaps = [JSON.parse(w.load(s, rows, '', '', ''))];
  for (let i = 0; i < steps; i++) {
    const j = JSON.parse(w.step(s));
    snaps.push(j);
    if (j.type === 'error' || j.halted) break;
  }
  w.closeSession(s);
  return snaps;
}
function runRust(rows, steps) {
  const f = path.join(os.tmpdir(), `lm_${Math.abs(hash(rows.join('\n')))}.man`);
  fs.writeFileSync(f, rows.join('\n'));
  const out = execFileSync(LM, [f, String(steps)], { encoding: 'utf8' });
  return out.trim().split('\n').map(l => JSON.parse(l));
}
function hash(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return h; }

function compare(name, rows, steps) {
  const w = COMPARE_W;
  let orc, rus;
  try { orc = runOracle(w, rows, steps); } catch (e) { return `${name}: ORACLE ERR ${e.message}`; }
  try { rus = runRust(rows, steps); } catch (e) { return `${name}: RUST ERR ${e.message}`; }
  // skip programs the milestone can't handle yet (pipes/literals -> rust 'fatal:unimpl')
  if (rus.some(j => j.end === 'fatal' && j.fatal && j.fatal.reason === 'unimpl'))
    return `${name}: SKIP (uses unimplemented op)`;
  const n = Math.min(orc.length, rus.length);
  for (let i = 0; i < n; i++) {
    if (orc[i].type === 'error') return `${name}: oracle load/step error: ${orc[i].message}`;
    const co = canonRunners(orc[i].entities.runners).join('  ');
    const cr = canonRunners(rus[i].runners).join('  ');
    if (co !== cr) return `${name}: DIVERGE @step ${i}\n   oracle: ${co}\n   rust:   ${cr}`;
  }
  const eo = endOfOracle(orc[orc.length - 1]);
  const er = endOfRust(rus[rus.length - 1]);
  if (eo !== er) return `${name}: END DIVERGE oracle=${eo} rust=${er}`;
  if (orc.length !== rus.length) return `${name}: LENGTH ${orc.length} vs ${rus.length} (end=${eo}) — states matched up to min`;
  return `${name}: OK (${orc.length} steps, end=${eo})`;
}

let COMPARE_W;
const CASES = [
  ['baseline-fork', room(5, 5, [[1,3,'@'],[3,3,'Y']]), 8],
  ['fork-into-wall(copy)', room(4, 3, [[1,1,'@'],[3,1,'Y']]), 6],
  ['head-on-even', room(9,5,[[1,4,'@'],[5,4,'^'],[5,2,'Y'],[8,2,'v'],[8,3,'<'],[2,2,'v'],[2,3,'>']]), 16],
  ['swap-attempt-odd', room(9,5,[[1,4,'@'],[5,4,'^'],[5,2,'Y'],[8,2,'v'],[8,3,'<'],[3,2,'v'],[3,3,'>']]), 16],
  ['arith-3+4', room(6,1,[[1,1,'@'],[2,1,'3'],[3,1,'M'],[4,1,'4'],[5,1,'+']]), 8], // no H: runs to wall; checks a=7 en route
  ['backpack-turn', room(6,3,[[1,2,'@'],[2,2,'3'],[3,2,'b'],[4,2,'d']]), 8],
  ['wall-fatal', room(3,1,[[1,1,'@']]), 6],
  ['X-turn-neg', room(5,3,[[1,2,'@'],[2,2,'1'],[3,2,'N'],[4,2,'X']]), 8],
];

(async () => {
  COMPARE_W = await boot();
  let pass = 0, fail = 0, skip = 0;
  for (const [name, rows, steps] of CASES) {
    const r = compare(name, rows, steps);
    console.log(r);
    if (r.includes(': OK')) pass++; else if (r.includes('SKIP')) skip++; else fail++;
  }
  console.log(`\n${pass} passed, ${fail} failed, ${skip} skipped`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
