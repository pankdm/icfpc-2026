// Run a .man on the oracle with a custom single-round input; report ticks + output.
// usage: node orun.js <file.man> "<space-separated ints>" [cap]
const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const fs = require('fs');
(async () => {
  const [file, inp, capRaw] = process.argv.slice(2);
  const cap = parseInt(capRaw || '20000000', 10);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, inp, '', ''));
  if (j.type === 'error') { console.log('LOADERROR', j.message); process.exit(1); }
  while (!j.halted && j.step < cap) {
    const nj = JSON.parse(w.stepN(s, 20000, false));
    if (nj.type === 'error') { console.log('ERR', nj.message); break; }
    if (nj.step === j.step) { j = nj; break; }
    j = nj;
  }
  w.closeSession(s);
  console.log('ticks', j.step, 'halted', j.halted, 'reason', j.reason || (j.fatal && j.fatal.reason), 'output', JSON.stringify(j.output));
})();
