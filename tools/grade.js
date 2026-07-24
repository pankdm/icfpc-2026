#!/usr/bin/env node
// Local grade a solution (or all solutions for a problem) against the public test
// cases, using the reference oracle. Reports pass/fail, footprint, ticks, score.
//   node tools/grade.js <slug> [file.man]
// With no file, grades every solutions/<slug>/*.man and ranks them.
const { boot } = require('../sim/harness.js');
const L = require('./lib.js');
const fs = require('fs');
const path = require('path');

(async () => {
  const [slug, file] = process.argv.slice(2);
  if (!slug) { console.error('usage: node tools/grade.js <slug> [file.man]'); process.exit(2); }
  const problem = await L.fetchProblem(slug);
  const dir = path.join(L.REPO, 'solutions', slug);
  const files = file ? [file]
    : (fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.man')).map(f => path.join(dir, f)) : []);
  if (!files.length) { console.error(`no .man files (looked in ${file || dir})`); process.exit(1); }

  const w = await boot();
  const graded = [];
  for (const f of files) {
    const g = L.gradeAll(w, L.manRows(L.readMan(f)), problem);
    graded.push({ f, g });
    console.log(`\n${path.basename(f)}  [${slug}, ${problem.scoring}]  ${g.passed}/${g.total} public`);
    for (const r of g.results)
      console.log(`   ${r.status === 'pass' ? '✓' : '✗'} ${(r.name || '').padEnd(22)} ${r.status}${r.reason ? ': ' + r.reason : ''}${r.settleTick != null ? `  (${r.settleTick}t)` : ''}`);
    const s = g.score != null ? `SCORE ${Math.round(g.score)}` : 'SCORE n/a (not all public pass)';
    console.log(`   footprint ${g.footprint.w}x${g.footprint.h} → box ${g.footprint.box}${g.avgTicks != null ? `  avgTicks ${g.avgTicks.toFixed(1)}` : ''}  ${s}`);
  }
  if (graded.length > 1) {
    graded.sort((a, b) => (b.g.passed - b.g.total) - (a.g.passed - a.g.total) || (a.g.score ?? 1e18) - (b.g.score ?? 1e18));
    console.log('\n=== ranking (all-public-pass first, then score asc) ===');
    graded.forEach((r, i) => console.log(`  ${i + 1}. ${path.basename(r.f).padEnd(20)} ${r.g.passed}/${r.g.total}  score ${r.g.score != null ? Math.round(r.g.score) : 'n/a'}`));
  }
  console.log('\nNote: PRIVATE cases exist and are NOT tested here — make sure the solution generalizes.');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
