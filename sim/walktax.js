// walktax.js — measure man-ticks lost to WALKING (nop/glide) + TURN (routing) + STALL
// (blocked, idle) vs COMPUTE. Uses a real cached test case so the run settles correctly.
//   node sim/walktax.js <slug> <file.man> [caseIndex]
const { boot } = require(__dirname + '/harness.js');
const fs = require('fs');
const path = require('path');

const TURN = new Set(['<', '>', '^', 'v', 'V']);
const NOP = new Set([' ', '.', '']);
const cls = ch => TURN.has(ch) ? 'turn' : NOP.has(ch) ? 'nop' : 'op';

function buildCase(tc) {  // mirror tools/lib.js
  const rounds = tc.rounds || [{ in: tc.in || [], out: tc.out || [] }];
  return {
    input: rounds.map(r => (r.in || []).join(' ')).join(' / '),
    expected: rounds.map(r => (r.out || []).join(' ')).join(' / '),
    frames: rounds.map(r => r.frames || []),
  };
}

(async () => {
  const [slug, file, ci] = [process.argv[2], process.argv[3], parseInt(process.argv[4] || '0', 10)];
  const spec = JSON.parse(fs.readFileSync(path.join(__dirname + '/../tests', slug + '.json'), 'utf8'));
  const tc = spec.publicTestData[ci];
  const { input, expected, frames } = buildCase(tc);
  const isDisp = frames.some(f => f.length);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const cellAt = (x, y) => (rows[y] && rows[y][x]) || ' ';

  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, expected, isDisp ? JSON.stringify(frames) : ''));
  if (j.type === 'error') { console.log('LOAD ERROR:', j.message); process.exit(1); }

  const t = { op: 0, turn: 0, nop: 0, stall: 0 };
  let manTicks = 0;
  const prev = new Map(); // runner id -> "x,y,a,b,bp"
  const cap = spec.tickCap || 5_000_000;
  while (!j.halted && !j.outputSettled && j.step < cap) {
    for (const r of (j.entities?.runners || [])) {
      if (r.halted) continue;
      const key = `${r.pos},${r.a},${r.b},${r.backpack}`;
      if (prev.get(r.id) === key) t.stall++;        // unchanged since last tick = blocked/idle
      else t[cls(cellAt(r.pos[0], r.pos[1]))]++;
      prev.set(r.id, key);
      manTicks++;
    }
    const nj = JSON.parse(w.stepN(s, 1, false));
    if (nj.type === 'error' || nj.step === j.step) { j = nj; break; }
    j = nj;
  }
  w.closeSession(s);
  const tot = manTicks || 1;
  const p = k => (100 * t[k] / tot).toFixed(1) + '%';
  console.log(`${path.basename(file)} [${slug} case ${ci}] settle=${j.step} manTicks=${manTicks}`);
  console.log(`  COMPUTE ${t.op}(${p('op')})  TURN ${t.turn}(${p('turn')})  NOP/glide ${t.nop}(${p('nop')})  STALL/blocked ${t.stall}(${p('stall')})`);
  console.log(`  WASTED (turn+nop+stall) = ${(100 * (t.turn + t.nop + t.stall) / tot).toFixed(1)}%`);
  process.exit(0);
})().catch(e => { console.error(String(e).slice(0, 200)); process.exit(1); });
