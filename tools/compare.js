#!/usr/bin/env node
// Compare OUR best solution per problem against the OVERALL board-best, in a table.
//   node tools/compare.js            (all graded problems)
//   node tools/compare.js triangle   (one/few slugs)
// "Ours" = lowest score among solutions/<slug>/*.man that pass all PUBLIC cases,
// graded locally via the oracle (a public-case estimate; private cases affect the
// real avg-ticks). "Board" = lowest score among full-solvers on the live standings.
const { boot } = require('../sim/harness.js');
const L = require('./lib.js');
const fs = require('fs');
const path = require('path');

function loadSpec(slug) {
  const cached = path.join(L.REPO, 'tests', `${slug}.json`);
  if (fs.existsSync(cached)) { try { return JSON.parse(fs.readFileSync(cached, 'utf8')); } catch (_) {} }
  return null; // fall back to API below
}
async function spec(slug) { return loadSpec(slug) || await L.fetchProblem(slug); }

async function boardBest(id) {
  try {
    const st = await (await fetch(`${L.BASE}/standings/problems/${id}`)).json();
    const full = (st.rows || []).filter(r => r.rank != null && r.score != null);
    return { best: full.length ? Math.min(...full.map(r => r.score)) : null, solvers: full.length };
  } catch (_) { return { best: null, solvers: 0 }; }
}

function fmt(n) { return n == null ? '—' : (Number.isInteger(n) ? String(n) : n.toFixed(2)); }

(async () => {
  const slugs = process.argv.slice(2);
  const probs = (await (await fetch(`${L.BASE}/public/problems`)).json())
    .filter(p => p.status !== 'practice' && (slugs.length === 0 || slugs.includes(p.slug)))
    .sort((a, b) => (a.problemSetName || '').localeCompare(b.problemSetName || '') || (a.orderInSet || 0) - (b.orderInSet || 0));

  const w = await boot();
  const rows = [];
  for (const p of probs) {
    const problem = await spec(p.slug);
    const dir = path.join(L.REPO, 'solutions', p.slug);
    let ours = null, ourFile = null;
    if (fs.existsSync(dir)) {
      for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.man'))) {
        const g = L.gradeAll(w, L.manRows(L.readMan(path.join(dir, f))), problem);
        if (g.total > 0 && g.passed === g.total && g.score != null && (ours == null || g.score < ours)) { ours = g.score; ourFile = f; }
      }
    }
    const { best, solvers } = await boardBest(p.id);
    let verdict;
    if (ours == null) verdict = 'no solution';
    else if (best == null) verdict = 'LEAD (unsolved board)';
    else if (ours <= best) verdict = `LEAD (${(best / ours).toFixed(2)}× ahead)`;
    else verdict = `${(ours / best).toFixed(2)}× behind`;
    rows.push({ name: p.name || p.slug, set: p.problemSetName || '', ours, ourFile, best, solvers, verdict });
  }

  const H = ['problem', 'set', 'ours', 'board-best', 'ratio', 'solvers', 'verdict'];
  const data = rows.map(r => [
    r.name, r.set, fmt(r.ours), fmt(r.best),
    (r.ours != null && r.best != null) ? (r.ours / r.best).toFixed(2) : '—',
    String(r.solvers), r.verdict,
  ]);
  const wds = H.map((h, i) => Math.max(h.length, ...data.map(d => d[i].length)));
  const line = c => c.map((s, i) => s.padEnd(wds[i])).join('  ');
  console.log('\n' + line(H));
  console.log(wds.map(x => '-'.repeat(x)).join('  '));
  for (const d of data) console.log(line(d));
  console.log('\nours = best local solution passing all PUBLIC cases (private cases affect the real score);');
  console.log('board-best = lowest footprint²×ticks among full-solvers. Lower is better.');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
