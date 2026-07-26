// Run a .man on an input token list to settle. Usage: node run_ss.js file.man "4 3 5 2 6 8" [cap]
const { boot } = require((__dirname + '/../sim/harness.js'));
const fs = require('fs');
(async () => {
  const file = process.argv[2];
  const input = process.argv[3] || '';
  const cap = parseInt(process.argv[4] || '15000000', 10);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, '', ''));
  if (j.type === 'error') { console.log('LOAD ERR', j.message, j.pos||''); process.exit(0); }
  let lastOut = null, settleTick = null;
  while (!j.halted && !j.outputSettled && j.step < cap) {
    j = JSON.parse(w.stepN(s, 20000, false));
    if (j.type === 'error') { console.log('STEP ERR', j.message); break; }
  }
  console.log('output:', JSON.stringify(j.output));
  console.log('settled:', j.outputSettled, 'halted:', j.halted, 'reason:', j.reason||'', 'ticks:', j.step);
  process.exit(0);
})();
