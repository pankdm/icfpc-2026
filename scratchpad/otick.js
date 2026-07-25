// Run a .man; report the tick at which output first reaches `wantN` tokens.
// usage: node otick.js <file.man> "<input ints>" <wantN> [cap]
const { boot } = require((__dirname + '/../sim/harness.js'));
const fs = require('fs');
(async () => {
  const [file, inp, wantRaw, capRaw] = process.argv.slice(2);
  const wantN = parseInt(wantRaw || '1', 10);
  const cap = parseInt(capRaw || '20000000', 10);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, inp, '', ''));
  if (j.type === 'error') { console.log('LOADERROR', j.message); process.exit(1); }
  let firstTick = null;
  while (j.step < cap) {
    const nj = JSON.parse(w.stepN(s, 2000, false));
    if (nj.type === 'error') { console.log('ERR', nj.message); break; }
    j = nj;
    if ((j.output || []).length >= wantN) { firstTick = j.step; break; }
    if (j.halted) break;
  }
  w.closeSession(s);
  console.log('outputTick', firstTick, 'output', JSON.stringify(j.output), 'halted', j.halted);
})();
