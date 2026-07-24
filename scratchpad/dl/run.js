// Run a .man file against a custom input, report output + settle tick.
// usage: node run.js <file.man> "<input tokens>" "<expected tokens>"
const { boot } = require('../../sim/harness.js');
const fs = require('fs');
(async () => {
  const [file, input, expected] = process.argv.slice(2);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input || '', expected || '', ''));
  if (j.type === 'error') { console.log('LOAD ERROR:', j.message); process.exit(0); }
  const cap = 200000;
  let last = j;
  while (!j.halted && !j.outputSettled && j.step < cap) {
    const nj = JSON.parse(w.stepN(s, 2000, false));
    if (nj.type === 'error') { console.log('RUN ERROR:', nj.message, 'at step', last.step); j = nj; break; }
    if (nj.step === j.step) { j = nj; break; }
    j = nj; last = nj;
  }
  console.log('output:', JSON.stringify(j.output));
  console.log('halted:', j.halted, 'reason:', j.reason, j.fatal ? JSON.stringify(j.fatal) : '', 'outputSettled:', j.outputSettled);
  console.log('settleTick(step):', j.step);
  w.closeSession(s);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
