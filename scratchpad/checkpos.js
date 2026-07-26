// checkpos.js <file.man> <addr0,addr1,...>  -> for each addr, run "0 <addr>"? no,
// just feed the addr as a single input token, run to halt, print final runner pos.
const { boot } = require((__dirname + '/../sim/harness.js'));
const fs = require('fs');
(async () => {
  const [file, addrs] = process.argv.slice(2);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  for (const a of addrs.split(',')) {
    const s = w.newSession();
    let j = JSON.parse(w.load(s, rows, String(a), '', ''));
    if (j.type === 'error') { console.log(a, 'LOADERR', j.message); w.closeSession(s); continue; }
    let steps = 0;
    while (!j.halted && steps < 2000) { j = JSON.parse(w.stepN(s, 1, false)); steps++; if (j.type==='error') break; }
    const r = (j.entities && j.entities.runners) ? j.entities.runners.find(x=>x.halted) || j.entities.runners[0] : null;
    console.log('addr', a, 'halted', j.halted, 'pos', r? JSON.stringify(r.pos):'?', 'reason', j.reason, j.fatal?JSON.stringify(j.fatal):'');
    w.closeSession(s);
  }
  process.exit(0);
})();
