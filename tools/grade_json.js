#!/usr/bin/env node
// JSON grading bridge for the Python DSL (littleman.py). Grades one .man file
// against a problem's public cases via the reference oracle and prints one JSON line.
//   node tools/grade_json.js <slug> <file.man>
const { boot } = require('../sim/harness.js');
const L = require('./lib.js');

(async () => {
  const [slug, file] = process.argv.slice(2);
  const problem = await L.fetchProblem(slug);
  const w = await boot();
  const g = L.gradeAll(w, L.manRows(L.readMan(file)), problem);
  console.log(JSON.stringify({
    passed: g.passed, total: g.total,
    footprint: g.footprint, avgTicks: g.avgTicks, score: g.score,
    results: g.results,
  }));
  process.exit(0);
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
