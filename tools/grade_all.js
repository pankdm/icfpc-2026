#!/usr/bin/env node
// Batch regression harness: boots the reference oracle ONCE and grades many
// solutions against their problems' public cases. Prefers the cached spec in
// tests/<slug>.json (run tools/fetch_tests.py first); falls back to the API.
//
//   node tools/grade_all.js                 grade every solutions/<slug>/*.man
//   node tools/grade_all.js --slug triangle scope to one problem
//   node tools/grade_all.js --update-baseline   (re)write tests/baseline.json
//
// Prints a matrix (problem | file | passed/total | footprint | avgTicks | score)
// with the best candidate per problem marked '*'. Compares against an optional
// tests/baseline.json and exits non-zero if any previously-passing solution
// regressed (dropped a pass or got a worse score).
const { boot } = require('../sim/harness.js');
const L = require('./lib.js');
const fs = require('fs');
const path = require('path');

const TESTS = path.join(L.REPO, 'tests');
const SOLUTIONS = path.join(L.REPO, 'solutions');
const BASELINE = path.join(TESTS, 'baseline.json');

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? (process.argv[i + 1] || true) : null;
}

// Cached spec first (offline, fast), API as fallback.
async function loadProblem(slug) {
  const cached = path.join(TESTS, `${slug}.json`);
  if (fs.existsSync(cached)) {
    try { return JSON.parse(fs.readFileSync(cached, 'utf8')); } catch (_) { /* refetch */ }
  }
  return L.fetchProblem(slug);
}

function fmt(n, dp = 0) { return n == null ? '-' : (dp ? n.toFixed(dp) : String(Math.round(n))); }

(async () => {
  const only = arg('--slug');
  const updateBaseline = process.argv.includes('--update-baseline');

  // Which problems have candidate .man files?
  let slugs = fs.existsSync(SOLUTIONS)
    ? fs.readdirSync(SOLUTIONS).filter(d => {
        const p = path.join(SOLUTIONS, d);
        return fs.statSync(p).isDirectory() &&
          fs.readdirSync(p).some(f => f.endsWith('.man'));
      })
    : [];
  if (only && only !== true) slugs = slugs.filter(s => s === only);
  slugs.sort();
  if (!slugs.length) { console.error(`no solutions found${only ? ` for slug ${only}` : ''} in ${SOLUTIONS}`); process.exit(1); }

  const baseline = (!updateBaseline && fs.existsSync(BASELINE))
    ? JSON.parse(fs.readFileSync(BASELINE, 'utf8')) : {};

  const w = await boot();
  const rows = [];          // matrix rows
  const newBaseline = {};
  const regressions = [];

  for (const slug of slugs) {
    let problem;
    try { problem = await loadProblem(slug); }
    catch (e) { console.error(`skip ${slug}: ${e.message}`); continue; }
    const dir = path.join(SOLUTIONS, slug);
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.man')).sort();

    const graded = files.map(f => {
      const full = path.join(dir, f);
      const g = L.gradeAll(w, L.manRows(L.readMan(full)), problem);
      return { slug, file: f, g };
    });
    // Best = all public pass first, then lowest score, then fewest fails.
    const rank = (x) => [x.g.passed === x.g.total ? 0 : 1, x.g.score ?? 1e18, x.g.total - x.g.passed];
    const best = graded.slice().sort((a, b) => {
      const ra = rank(a), rb = rank(b);
      for (let i = 0; i < ra.length; i++) if (ra[i] !== rb[i]) return ra[i] - rb[i];
      return 0;
    })[0];

    for (const row of graded) {
      const key = `${slug}/${row.file}`;
      const g = row.g;
      const cur = { passed: g.passed, total: g.total, score: g.score };
      newBaseline[key] = cur;
      // Regression check against baseline.
      const prev = baseline[key];
      let flag = '';
      if (prev) {
        const wasFull = prev.passed === prev.total && prev.total > 0;
        const nowFull = g.passed === g.total && g.total > 0;
        if (wasFull && !nowFull) {
          flag = 'REGRESS(pass)';
          regressions.push(`${key}: passed ${prev.passed}/${prev.total} -> ${g.passed}/${g.total}`);
        } else if (wasFull && nowFull && prev.score != null && g.score != null && g.score > prev.score + 1e-6) {
          flag = 'REGRESS(score)';
          regressions.push(`${key}: score ${Math.round(prev.score)} -> ${Math.round(g.score)} (worse)`);
        }
      }
      rows.push({
        slug, file: row.file,
        mark: row === best ? '*' : ' ',
        passed: `${g.passed}/${g.total}`,
        footprint: g.footprint.box ? `${g.footprint.w}x${g.footprint.h}(${g.footprint.box})` : '-',
        avgTicks: g.avgTicks != null ? g.avgTicks.toFixed(1) : '-',
        score: g.score != null ? String(Math.round(g.score)) : 'n/a',
        flag,
      });
    }
  }
  w && (w.shutdown && w.shutdown());

  // Render matrix.
  const cols = [
    ['', r => r.mark],
    ['problem', r => r.slug],
    ['file', r => r.file],
    ['pass', r => r.passed],
    ['footprint', r => r.footprint],
    ['avgTicks', r => r.avgTicks],
    ['score', r => r.score],
    ['', r => r.flag],
  ];
  const widths = cols.map(([h, f]) => Math.max(h.length, ...rows.map(r => f(r).length)));
  const line = (cells) => cells.map((c, i) => c.padEnd(widths[i])).join('  ').replace(/\s+$/, '');
  console.log('\n' + line(cols.map(c => c[0])));
  console.log(widths.map(w2 => '-'.repeat(w2)).join('  '));
  let lastSlug = null;
  for (const r of rows) {
    if (lastSlug && lastSlug !== r.slug) console.log('');
    lastSlug = r.slug;
    console.log(line(cols.map(c => c[1](r))));
  }
  console.log('\n(* = best candidate per problem; PRIVATE cases are NOT tested here)');

  if (updateBaseline) {
    fs.writeFileSync(BASELINE, JSON.stringify(newBaseline, null, 2) + '\n');
    console.log(`\nbaseline written -> ${BASELINE} (${Object.keys(newBaseline).length} entries)`);
    process.exit(0);
  }

  if (regressions.length) {
    console.error(`\n${regressions.length} REGRESSION(S) vs baseline:`);
    regressions.forEach(r => console.error(`  - ${r}`));
    console.error('\n(run with --update-baseline to accept the new results as the baseline)');
    process.exit(1);
  }
  if (Object.keys(baseline).length) console.log('\nno regressions vs baseline.');
  else console.log('\n(no baseline yet — run with --update-baseline to record one)');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
