// Run a .man against SYNTHETIC display cases (rounds with in/frames) on the real oracle.
// Usage: node lllm_oracle.js <file.man> <cases.json>   (cases.json = [{name,rounds:[{in,frames}]}])
const { boot } = require('../../sim/harness.js');
const L = require('../../tools/lib.js');
const fs = require('fs');

(async () => {
  const [file, casesFile] = process.argv.slice(2);
  const rows = L.manRows(L.readMan(file));
  const cases = JSON.parse(fs.readFileSync(casesFile, 'utf8'));
  const w = await boot();
  let pass = 0;
  for (const tc of cases) {
    const r = L.gradeCase(w, rows, tc, 15_000_000);
    const ok = r.status === 'pass';
    pass += ok ? 1 : 0;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${tc.name || ''}  ${r.status}${r.reason ? ' ' + r.reason : ''}${r.settleTick != null ? ' (' + r.settleTick + 't)' : ''}`);
  }
  console.log(`\n${pass}/${cases.length} cases pass`);
  process.exit(pass === cases.length ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
