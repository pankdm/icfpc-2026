// Probe opcode semantics. Usage: node probe.js "OPS" [input] [nsteps]
// Places a man at left of a room interior, ops running east. Prints a/b/bp/pos/dir each tick.
const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
(async () => {
  const ops = process.argv[2] || '';
  const input = process.argv[3] || '';
  const N = parseInt(process.argv[4] || '20', 10);
  const w = await boot();
  // build a room: width enough for ops + margins. interior row = row 1.
  const W = ops.length + 6;
  const top = '+' + '-'.repeat(W - 2) + '+';
  const mid = '|@' + ops + ' '.repeat(W - 3 - ops.length) + '|';
  const bot = '+' + '-'.repeat(W - 2) + '+';
  const rows = [top, mid, bot];
  const s = w.newSession();
  const raw = w.load(s, rows, input, '', '');
  let j = JSON.parse(raw);
  if (j.type === 'error') { console.log('LOAD ERR', j.message); process.exit(0); }
  const brief = (jj) => {
    const r = (jj.entities.runners || [])[0];
    if (!r) return 'no-runner';
    return `pos${r.pos} dir[${r.dir}] a=${r.a} b=${r.b} bp=${r.backpack}${r.halted?' H':''}`;
  };
  console.log('t0:', brief(j), 'out=', j.output);
  for (let i = 0; i < N; i++) {
    j = JSON.parse(w.step(s));
    if (j.type === 'error') { console.log(`t${i+1}: ERR ${j.message}`); break; }
    // which op cell is the runner on?
    const r = (j.entities.runners||[])[0];
    let cell = '';
    if (r) { const c = r.pos[0]-1; cell = (c>=1 && c-1<ops.length)?ops[c-1]:'.'; }
    console.log(`t${i+1}: [${cell}] ${brief(j)}${j.output?' out='+j.output:''}${j.halted?' <<HALT '+j.reason+'>>':''}`);
    if (j.halted) break;
  }
  process.exit(0);
})();
