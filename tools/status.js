#!/usr/bin/env node
// Show live server standings per graded problem: the best (lowest) score on the
// board, how many teams fully solved it, and the true total case count (public +
// private, which the per-problem API masks). API-only, no auth needed.
//   node tools/status.js
const L = require('./lib.js');

(async () => {
  const probs = await L.listProblems();
  const graded = probs.filter(p => p.status !== 'practice')
    .sort((a, b) => (a.problemSetName || '').localeCompare(b.problemSetName || '') || (a.orderInSet || 0) - (b.orderInSet || 0));
  console.log('problem                     set          board-best   solvers   cases(pub→total)');
  console.log('-'.repeat(84));
  for (const p of graded) {
    const st = await L.problemStandings(p.id);
    let best = '—', solvers = 0, total = '?';
    if (st && Array.isArray(st.rows)) {
      const full = st.rows.filter(r => r.rank != null && r.score != null);
      solvers = full.length;
      if (full.length) best = Math.min(...full.map(r => r.score));
      if (st.rows.length) total = Math.max(...st.rows.map(r => r.casesTotal || 0));
    }
    const pub = '?'; // public count needs a per-problem fetch; omitted for speed
    console.log(
      `${(p.name || p.slug).padEnd(27)} ${(p.problemSetName || '').padEnd(12)} ` +
      `${String(best).padStart(9)}   ${String(solvers).padStart(5)}    →${total}`
    );
  }
  console.log('\n(best = lowest footprint²×ticks among full-solvers; total = public+private case count)');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
