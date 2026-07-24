const { boot } = require('./harness.js');
const L = require('../tools/lib.js');
(async () => {
  const rows = L.manRows(L.readMan(process.argv[2]));
  const w = await boot();
  const s = w.newSession();
  const j = JSON.parse(w.load(s, rows, process.argv[3] || '', process.argv[4] || '', ''));
  console.log(j.type === 'error' ? 'LOAD ERROR: ' + j.message : 'LOAD OK');
  process.exit(0);
})().catch(e => { console.log('EXC ' + e); process.exit(1); });
