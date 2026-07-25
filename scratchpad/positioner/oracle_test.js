// Confirm the positioner on the littleman.wasm ORACLE (ground truth).
// usage: node oracle_test.js <file.man> <numSlots>
const fs = require('fs');
const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');

async function main() {
  const file = process.argv[2];
  const n = parseInt(process.argv[3], 10);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  const results = [];
  for (let k = 0; k < n; k++) {
    const s = w.newSession();
    JSON.parse(w.load(s, rows, String(k), '', ''));
    let last = null, halted = false, step = 0;
    for (let i = 0; i < 400; i++) {
      const jj = JSON.parse(w.step(s));
      last = jj; step = i + 1;
      if (jj.type === 'error') { console.log(`k=${k} STEP-ERROR ${jj.message}`); break; }
      if (jj.halted) { halted = true; break; }
    }
    const r = (last.entities.runners || [])[0] || {};
    results.push({ k, col: r.pos ? r.pos[0] : null, row: r.pos ? r.pos[1] : null, halted, step });
    w.closeSession(s);
  }
  for (const r of results) console.log(`k=${String(r.k).padStart(2)} col=${String(r.col).padStart(2)} row=${r.row} halted=${r.halted} step=${r.step}`);
  const cols = results.map(r => r.col);
  console.log(`distinct cols: ${new Set(cols).size}/${n}  span=${Math.max(...cols) - Math.min(...cols) + 1}`);
  process.exit(0);
}
main();
