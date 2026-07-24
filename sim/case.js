// Run a .man against an inline test case (rounds) and report output/ticks.
//   node sim/case.js <file.man> '<json-rounds>'
// json-rounds: [{"in":["4","1",...],"out":["51","23"]}, ...]
const { boot } = require('./harness.js');
const L = require('../tools/lib.js');
const fs = require('fs');

(async () => {
  const [file, casesJson] = process.argv.slice(2);
  const rows = L.manRows(L.readMan(file));
  const rounds = JSON.parse(casesJson);
  const tc = { rounds };
  const w = await boot();
  const r = L.gradeCase(w, rows, tc, 5_000_000);
  // also fetch raw output for debugging
  const { input, expected, framesJson } = L.buildCase(tc);
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, expected, framesJson));
  const cap = 5_000_000;
  while (!j.halted && !j.outputSettled && j.step < cap) {
    const nj = JSON.parse(w.stepN(s, 5000, false));
    if (nj.type === 'error') { j = nj; break; }
    if (nj.step === j.step) { j = nj; break; }
    j = nj;
  }
  w.closeSession(s);
  console.log(JSON.stringify({
    status: r.status, ticks: r.settleTick, reason: r.reason,
    output: j.output || [], expected,
  }));
  process.exit(0);
})().catch(e => { console.log(JSON.stringify({ error: String(e), stack: e.stack })); process.exit(1); });
