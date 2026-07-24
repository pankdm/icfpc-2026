// Fast local debug: boots oracle once, grades a .man against cached memory spec,
// and can run a single custom input with optional per-tick trace.
//   node scratch_dbg.js <file.man>                 grade all public cases
//   node scratch_dbg.js <file.man> "0 3"           run one input, show output/ticks
//   node scratch_dbg.js <file.man> "0 3" trace 60  trace first 60 ticks
const { boot } = require('./sim/harness.js');
const L = require('./tools/lib.js');
const fs = require('fs');

const spec = JSON.parse(fs.readFileSync('./tests/memory.json', 'utf8'));

function runInput(w, rows, inStr, trace, nsteps) {
  const s = w.newSession();
  const raw = w.load(s, rows, inStr, '', '');
  let j = JSON.parse(raw);
  if (j.type === 'error') { console.log('LOAD ERROR:', j.message, j.pos||''); w.closeSession(s); return; }
  const cap = 3000000;
  if (trace) {
    for (let i = 0; i < (nsteps||60); i++) {
      const rr = w.step(s); const jj = JSON.parse(rr);
      if (jj.type === 'error') { console.log(`t${i+1}: ERR ${jj.message}`); break; }
      const rs = (jj.entities&&jj.entities.runners)||[];
      const rb = rs.map(r=>`[${r.pos}]a${r.a}b${r.b}bp${r.backpack}${r.halted?'H':''}`).join(' ');
      console.log(`t${jj.step}: ${rb}${jj.output&&jj.output.length?' out='+JSON.stringify(jj.output):''}`);
      j = jj; if (jj.halted) { console.log('HALTED'); break; }
    }
  } else {
    while (!j.halted && j.step < cap) {
      const nj = JSON.parse(w.stepN(s, 5000, false));
      if (nj.type === 'error') { j = nj; break; }
      if (nj.step === j.step) break;
      j = nj;
    }
    if (j.type === 'error') console.log('ERR', j.message);
    else console.log('output=', JSON.stringify(j.output||[]), 'ticks=', j.step, 'halted=', j.halted, j.reason||'');
  }
  w.closeSession(s);
}

(async () => {
  const file = process.argv[2];
  const inStr = process.argv[3];
  const trace = process.argv[4] === 'trace';
  const nsteps = parseInt(process.argv[5]||'60');
  const rows = L.manRows(L.readMan(file));
  const w = await boot();
  if (inStr !== undefined) { runInput(w, rows, inStr, trace, nsteps); process.exit(0); }
  const g = L.gradeAll(w, rows, spec);
  for (const r of g.results) console.log(`  ${r.status.padEnd(7)} ${r.settleTick||''} ${r.reason||''}  :: ${r.name}`);
  console.log(`passed ${g.passed}/${g.total} footprint ${g.footprint.w}x${g.footprint.h}(${g.footprint.box}) avgTicks ${g.avgTicks} score ${g.score}`);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
