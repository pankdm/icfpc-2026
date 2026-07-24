// Node harness for littleman.wasm
require('./wasm_exec.js');
const fs = require('fs');

async function boot() {
  const go = new Go();
  const buf = fs.readFileSync(__dirname + '/littleman.wasm');
  const { instance } = await WebAssembly.instantiate(buf, go.importObject);
  go.run(instance); // runs async; Go program blocks on channel
  // wait for global
  const t0 = Date.now();
  while (!globalThis.littlemanWasm) {
    if (Date.now() - t0 > 10000) throw new Error('wasm global never appeared');
    await new Promise(r => setTimeout(r, 10));
  }
  return globalThis.littlemanWasm;
}

function parse(s) {
  const r = JSON.parse(s);
  if (r.type === 'error') { const e = new Error(r.message); e.pos = r.pos; throw e; }
  return r;
}

module.exports = { boot, parse };

if (require.main === module) {
  boot().then(w => {
    console.log('API keys:', Object.keys(w));
    console.log('validOps:', JSON.stringify(w.validOps()));
    console.log('structuralGlyphs:', JSON.stringify(w.structuralGlyphs()));
  }).catch(e => { console.error(e); process.exit(1); });
}
