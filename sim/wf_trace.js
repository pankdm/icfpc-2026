// wf_trace.js — per-cell visit counts for one man on one case (walk-folding analysis).
//   node sim/wf_trace.js <slug> <file.man> <caseIdx> [manIdx] [--cap=N] [--seq=N]
const { boot } = require(__dirname + '/harness.js');
const fs = require('fs');
const path = require('path');

function buildCase(tc) {
  const rounds = tc.rounds || [{ in: tc.in || [], out: tc.out || [] }];
  return {
    input: rounds.map(r => (r.in || []).join(' ')).join(' / '),
    expected: rounds.map(r => (r.out || []).join(' ')).join(' / '),
  };
}

(async () => {
  const argv = process.argv.slice(2);
  const flags = argv.filter(a => a.startsWith('--'));
  const pos = argv.filter(a => !a.startsWith('--'));
  const slug = pos[0], file = pos[1], ci = parseInt(pos[2] || '0', 10);
  const mi = parseInt(pos[3] || '0', 10);
  const gf = n => { const f = flags.find(x => x.startsWith('--' + n + '=')); return f ? parseInt(f.split('=')[1], 10) : null; };
  const cap = gf('cap') || 400000;
  const seqN = gf('seq') || 0;

  const spec = JSON.parse(fs.readFileSync(path.join(__dirname + '/../tests', slug + '.json'), 'utf8'));
  const tc = spec.publicTestData[ci];
  const { input, expected } = buildCase(tc);
  const rows = fs.readFileSync(file, 'utf8').replace(/\r/g, '').replace(/\n+$/, '').split('\n');
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, expected, ''));
  const counts = new Map();
  const seq = [];
  let n = 0;
  while (!j.halted && n < cap) {
    const rs = (j.entities && j.entities.runners) || [];
    if (rs[mi]) {
      const k = rs[mi].pos[0] + ',' + rs[mi].pos[1];
      counts.set(k, (counts.get(k) || 0) + 1);
      if (seq.length < seqN) seq.push(k);
    }
    j = JSON.parse(w.step(s));
    n++;
  }
  const out = { steps: n, halted: !!j.halted, counts: Object.fromEntries(counts) };
  if (seqN) out.seq = seq;
  console.log(JSON.stringify(out));
  w.closeSession(s);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
