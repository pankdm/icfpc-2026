#!/usr/bin/env node
// Compare OUR solutions against the board, breaking out size vs runtime.
//   node tools/compare.js                 table: our best (box, ticks, score) vs board score
//   node tools/compare.js triangle        scope to one/few slugs
//   node tools/compare.js --pareto <slug> pareto frontier of our candidates (size vs ticks)
//
// NOTE: the board only exposes the COMPOSITE score (max(w,h)^2 * avgTicks) per team —
// there is no per-team footprint/ticks breakdown, and other teams' programs aren't
// public. So board size/runtime can't be shown; the pareto frontier is over OUR
// candidate solutions (where we know both dimensions).
const { boot } = require('../sim/harness.js');
const L = require('./lib.js');
const fs = require('fs');
const path = require('path');

function spec(slug) {
  const cached = path.join(L.REPO, 'tests', `${slug}.json`);
  if (fs.existsSync(cached)) { try { return JSON.parse(fs.readFileSync(cached, 'utf8')); } catch (_) {} }
  return null;
}
async function getSpec(slug) { return spec(slug) || await L.fetchProblem(slug); }

// Grade every candidate for a problem -> [{file, box, ticks, score, pass}]
function candidates(w, slug, problem) {
  const dir = path.join(L.REPO, 'solutions', slug);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(f => f.endsWith('.man')).map(f => {
    const g = L.gradeAll(w, L.manRows(L.readMan(path.join(dir, f))), problem);
    return { file: f, box: g.footprint.box, dim: `${g.footprint.w}x${g.footprint.h}`, ticks: g.avgTicks, score: g.score, pass: g.total > 0 && g.passed === g.total };
  });
}
// Non-dominated passing candidates (lower box AND lower ticks = dominant).
function pareto(cands) {
  const p = cands.filter(c => c.pass && c.score != null);
  return p.filter(a => !p.some(b => b !== a && b.box <= a.box && b.ticks <= a.ticks && (b.box < a.box || b.ticks < a.ticks)));
}
async function boardBest(id) {
  try {
    const st = await (await fetch(`${L.BASE}/standings/problems/${id}`)).json();
    const full = (st.rows || []).filter(r => r.rank != null && r.score != null);
    return { best: full.length ? Math.min(...full.map(r => r.score)) : null, solvers: full.length };
  } catch (_) { return { best: null, solvers: 0 }; }
}
const fmt = n => n == null ? '—' : (Number.isInteger(n) ? String(n) : n.toFixed(2));
function tbl(head, data) {
  const wds = head.map((h, i) => Math.max(h.length, ...data.map(d => String(d[i]).length)));
  const line = c => c.map((s, i) => String(s).padEnd(wds[i])).join('  ');
  console.log('\n' + line(head));
  console.log(wds.map(x => '-'.repeat(x)).join('  '));
  for (const d of data) console.log(line(d));
}

(async () => {
  const args = process.argv.slice(2);
  const paretoIdx = args.indexOf('--pareto');
  const w = await boot();

  if (paretoIdx >= 0) {
    const slug = args[paretoIdx + 1];
    const cands = candidates(w, slug, await getSpec(slug)).filter(c => c.pass);
    const front = new Set(pareto(cands).map(c => c.file));
    console.log(`\nPareto frontier — ${slug} (our passing candidates; * = non-dominated):`);
    tbl(['', 'file', 'box', 'ticks', 'score'],
      cands.sort((a, b) => a.score - b.score).map(c => [front.has(c.file) ? '*' : ' ', c.file, `${c.dim}(${c.box})`, fmt(c.ticks), fmt(c.score)]));
    console.log('\n* = pareto-optimal (no other candidate is both smaller and faster).');
    process.exit(0);
  }

  const probs = (await (await fetch(`${L.BASE}/public/problems`)).json())
    .filter(p => p.status !== 'practice' && (args.length === 0 || args.includes(p.slug)))
    .sort((a, b) => (a.problemSetName || '').localeCompare(b.problemSetName || '') || (a.orderInSet || 0) - (b.orderInSet || 0));

  const data = [];
  for (const p of probs) {
    const cands = candidates(w, p.slug, await getSpec(p.slug)).filter(c => c.pass);
    const best = cands.sort((a, b) => a.score - b.score)[0] || null;
    const { best: board, solvers } = await boardBest(p.id);
    let verdict;
    if (!best) verdict = 'no solution';
    else if (board == null) verdict = 'LEAD';
    else if (best.score <= board) verdict = `LEAD ${(board / best.score).toFixed(2)}×`;
    else verdict = `${(best.score / board).toFixed(2)}× behind`;
    data.push([
      p.name || p.slug, p.problemSetName || '',
      best ? best.dim : '—', best ? fmt(best.ticks) : '—', best ? fmt(best.score) : '—',
      fmt(board), String(solvers), verdict,
    ]);
  }
  tbl(['problem', 'set', 'our-size', 'our-ticks', 'our-score', 'board-score', 'solvers', 'verdict'], data);
  console.log('\nour-size/ticks/score = our best (lowest-score) solution passing all PUBLIC cases.');
  console.log('board-score = lowest composite (size²×ticks) among full-solvers; board size/ticks not exposed.');
  console.log('run `--pareto <slug>` for the size↔ticks frontier of our candidates.');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
