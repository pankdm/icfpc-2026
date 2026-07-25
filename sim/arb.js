// Probe: arbitration order when several men contend for ONE outgoing pipe.
//
// Three men reach `s` on the SAME tick, in three different rows, with known
// ids and known values. The four candidate laws predict four distinct outputs.
//
//   id1 = original (@), ends on row 5, A=3
//   id2 = clone of fork #1,   row 1, A=1
//   id3 = clone of fork #2,   row 3, A=2
//
//   ascending id      -> [3,1,2]
//   descending id     -> [2,1,3]
//   reading order     -> [1,2,3]
//   reverse reading   -> [3,2,1]
const { boot } = require('./harness.js');

const GRID = [
  '+-------+     ',
  '|  >1.sH|  +-+',
  '|  .    |>>|O|',
  '|@.Y>2sH|  +-+',
  '|  >Y   |     ',
  '|   >3sH|     ',
  '+-------+     ',
];

function brief(snap) {
  const rs = (snap.entities && snap.entities.runners) || [];
  const dn = d => (d[0] === 1 ? '→' : d[0] === -1 ? '←' : d[1] === 1 ? '↓' : '↑');
  return rs.map(r => `#${r.id}[${r.pos}]${dn(r.dir)}a${r.a}`).join(' ');
}

async function main() {
  const w = await boot();
  const s = w.newSession();
  const j0 = JSON.parse(w.load(s, GRID, '', '', ''));
  for (const r of GRID) console.log('   |' + r);
  if (j0.type === 'error') { console.log('LOAD ERROR:', j0.message, j0.pos); process.exit(1); }
  console.log('load:', brief(j0));
  for (let i = 1; i <= 20; i++) {
    const j = JSON.parse(w.step(s));
    if (j.type === 'error') { console.log(`t${i}: STEP-ERROR`, j.message); break; }
    console.log(`t${i}: ${brief(j)}${j.output ? '  out=[' + j.output + ']' : ''}${j.halted ? '  <<END ' + j.reason + '>>' : ''}`);
    if (j.halted) break;
  }
  process.exit(0);
}
main();
