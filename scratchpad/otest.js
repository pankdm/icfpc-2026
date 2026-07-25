// Quick oracle runner for a raw .man file.
//   node otest.js <file.man> "<input rounds, ' / ' separated>" [maxsteps] [--trace]
const { boot } = require('../sim/harness.js');
const fs = require('fs');

(async () => {
  const [file, input = '', maxStr = '20000'] = process.argv.slice(2).filter(a => a !== '--trace');
  const trace = process.argv.includes('--trace');
  const rows = fs.readFileSync(file, 'utf8').replace(/\r/g, '').split('\n');
  const max = parseInt(maxStr, 10);
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, '', ''));
  if (j.type === 'error') { console.log('LOADERROR:', j.message); process.exit(0); }
  let last = j;
  while (!j.halted && j.step < max) {
    const nj = JSON.parse(w.stepN(s, trace ? 1 : 2000, false));
    if (nj.type === 'error') { console.log('RUNTIME ERROR:', nj.message); last = nj; break; }
    if (trace) {
      const r = (nj.runners || nj.entities && nj.entities.runners || []);
      console.log(`step ${nj.step} out=${JSON.stringify(nj.output)} runners=${JSON.stringify(r.map(x=>({p:x.pos,d:x.dir,a:x.a,b:x.b,bp:x.backpack,h:x.halted})))}`);
    }
    if (nj.step === j.step) { j = nj; break; }
    j = nj; last = nj;
  }
  console.log('END:', last.end, last.fatal ? JSON.stringify(last.fatal) : '', 'step=', last.step, 'halted=', last.halted);
  console.log('OUTPUT:', JSON.stringify(last.output));
  w.closeSession(s);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
