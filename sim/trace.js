// Multi-man interaction probe harness for the reference littleman.wasm oracle.
const { boot } = require('./harness.js');

function runnersBrief(snap) {
  const rs = (snap.entities && snap.entities.runners) || [];
  return rs.map(r => `#${r.id}[${r.pos}]${dirName(r.dir)}${r.halted ? 'H' : ''}${r.a||r.b||r.backpack ? `(a${r.a} b${r.b} bp${r.backpack})` : ''}`).join('  ');
}
function dirName(d) {
  if (!d) return '?';
  const [x, y] = d;
  if (x === 1 && y === 0) return '→';
  if (x === -1 && y === 0) return '←';
  if (x === 0 && y === 1) return '↓';
  if (x === 0 && y === -1) return '↑';
  return `[${d}]`;
}

// scenario: { name, rows, input='', expected='', steps=12, dumpFinal=false }
async function scenario(w, sc) {
  const s = w.newSession();
  const raw = w.load(s, sc.rows, sc.input || '', sc.expected || '', '');
  const j0 = JSON.parse(raw);
  console.log(`\n=== ${sc.name} ===`);
  for (const r of sc.rows) console.log('   |' + r);
  if (j0.type === 'error') { console.log('LOAD ERROR:', j0.message); w.closeSession(s); return; }
  console.log(`load: ${runnersBrief(j0)}${j0.output ? ' out=' + j0.output : ''}`);
  let last = j0;
  const N = sc.steps || 12;
  for (let i = 0; i < N; i++) {
    const rr = w.step(s);
    const jj = JSON.parse(rr);
    if (jj.type === 'error') { console.log(`t${i + 1}: STEP-ERROR ${jj.message}`); last = jj; break; }
    const out = jj.output ? ` out=[${jj.output}]` : '';
    console.log(`t${i + 1}: ${runnersBrief(jj)}${out}${jj.halted ? '  <<HALTED>>' : ''}`);
    last = jj;
    if (jj.halted) break;
  }
  if (sc.dumpFinal) console.log('FINAL RAW:', JSON.stringify(last));
  w.closeSession(s);
}

async function main(scenarios) {
  const w = await boot();
  for (const sc of scenarios) await scenario(w, sc);
  process.exit(0);
}

module.exports = { main };
