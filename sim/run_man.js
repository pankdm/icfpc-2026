// node sim/run_man.js <file.man> "<input>" [steps] [--trace]
const { boot } = require('./harness.js');
const fs = require('fs');

const [file, input, stepsArg] = process.argv.slice(2);
const STEPS = Number(stepsArg) || 400;
const TRACE = process.argv.includes('--trace');
const dn = d => (d[0] === 1 ? '>' : d[0] === -1 ? '<' : d[1] === 1 ? 'v' : '^');

boot().then(w => {
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const s = w.newSession();
  const j0 = JSON.parse(w.load(s, rows, input || '', '', ''));
  if (j0.type === 'error') { console.log('LOAD ERROR:', j0.message, j0.pos); process.exit(1); }
  let last = j0;
  for (let i = 1; i <= STEPS; i++) {
    const j = JSON.parse(w.step(s));
    if (j.type === 'error') { console.log(`t${i}: STEP-ERROR`, j.message); break; }
    last = j;
    if (TRACE) {
      const rs = (j.entities.runners || []).map(r => `#${r.id}[${r.pos}]${dn(r.dir)}a${r.a}bp${r.backpack}`).join(' ');
      console.log(`t${i}: ${rs}${j.output ? ' out=[' + j.output + ']' : ''}`);
    }
    if (j.halted) { console.log(`END t${i} reason=${j.reason} ${JSON.stringify(j.fatal || {})}`); break; }
  }
  console.log('output:', JSON.stringify(last.output));
  process.exit(0);
});
