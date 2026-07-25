// Follow-up probes to sim/arb.js (which established: `s` contention = ascending id).
//
// P2b: does RECEIVE (`r`) contention follow the same law? 3 men park on `r` cells
//      on the same tick; input feeds 100,200,300. Which id gets 100?
// P3 : is `q` a broadcast? 3 men execute `q` on the same tick against one shared
//      incoming pipe -> do they all get the same BP, and is the pipe unconsumed?
// P5 : indefinite parking -- men blocked on `r` for many ticks with no data, then
//      woken by a late value.
const { boot } = require('./harness.js');

const dn = d => (d[0] === 1 ? '>' : d[0] === -1 ? '<' : d[1] === 1 ? 'v' : '^');
const brief = snap => ((snap.entities && snap.entities.runners) || [])
  .map(r => `#${r.id}[${r.pos}]${dn(r.dir)}a${r.a}bp${r.backpack}`).join(' ');
const pipes = snap => JSON.stringify((snap.entities && snap.entities.pipes) || []);

// Same fork skeleton as arb.js: id0 ends on row5, id4 on row1, id5 on row3.
// col6 is the "sync column" -- all three men execute it on tick 8.
function grid(syncOp, tail, right) {
  return [
    '+-------+' + ' '.repeat(right[0].length),
    '|  >1.' + syncOp + tail + '|' + right[0],
    '|  .    |' + right[1],
    '|@.Y>2' + syncOp + tail + '|' + right[2],
    '|  >Y   |' + ' '.repeat(right[0].length),
    '|   >3' + syncOp + tail + '|' + ' '.repeat(right[0].length),
    '+-------+' + ' '.repeat(right[0].length),
  ];
}

const IN = ['  +-+', '<<|I|', '  +-+'];

const SCENARIOS = [
  { name: 'P2b: receive contention (who gets 100?)', input: '100 200 300', steps: 16,
    rows: grid('r', 'H', IN) },
  { name: 'P5: park long, wake late (input arrives after a delay is impossible -- ' +
          'instead: only ONE value for three men)', input: '777', steps: 16,
    rows: grid('r', 'H', IN) },
  { name: 'P3: q broadcast (all three read pipe depth on the same tick)',
    input: '11 22 33 44 55', steps: 12,
    rows: grid('q', 'H', IN) },
];

async function main() {
  const w = await boot();
  for (const sc of SCENARIOS) {
    console.log(`\n=== ${sc.name} ===`);
    for (const r of sc.rows) console.log('   |' + r);
    const s = w.newSession();
    const j0 = JSON.parse(w.load(s, sc.rows, sc.input || '', '', ''));
    if (j0.type === 'error') { console.log('LOAD ERROR:', j0.message, j0.pos); w.closeSession(s); continue; }
    console.log('load:', brief(j0));
    for (let i = 1; i <= sc.steps; i++) {
      const j = JSON.parse(w.step(s));
      if (j.type === 'error') { console.log(`t${i}: STEP-ERROR`, j.message); break; }
      console.log(`t${i}: ${brief(j)}  pipes=${pipes(j)}${j.output ? ' out=[' + j.output + ']' : ''}${j.halted ? '  <<END ' + j.reason + '>>' : ''}`);
      if (j.halted) break;
    }
    w.closeSession(s);
  }
  process.exit(0);
}
main();
