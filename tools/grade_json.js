#!/usr/bin/env node
// JSON grading bridge for the Python tooling (littleman.py, autotune.py). Grades one
// .man file against a problem's public cases via the reference oracle and prints one
// JSON line. Prefers the cached spec in tests/<slug>.json (offline); falls back to the API.
//   node tools/grade_json.js <slug> <file.man> [--cases extra.json]
// --cases appends extra test cases ({"cases":[{in:[],out:[]},…]} or a bare array) to the
// public ones — gate on a generality/stress suite, not just the public cases.
const { boot } = require('../sim/harness.js');
const L = require('./lib.js');
const fs = require('fs');
const path = require('path');

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : null;
}

async function loadProblem(slug) {
  const cached = path.join(L.REPO, 'tests', `${slug}.json`);
  if (fs.existsSync(cached)) {
    try { return JSON.parse(fs.readFileSync(cached, 'utf8')); } catch (_) { /* refetch */ }
  }
  return L.fetchProblem(slug);
}

(async () => {
  const [slug, file] = process.argv.slice(2);
  const problem = await loadProblem(slug);
  const extra = arg('--cases');
  if (extra) {
    const j = JSON.parse(fs.readFileSync(extra, 'utf8'));
    const cases = Array.isArray(j) ? j : (j.cases || []);
    problem.publicTestData = (problem.publicTestData || []).concat(cases);
  }
  const w = await boot();
  const g = L.gradeAll(w, L.manRows(L.readMan(file)), problem);
  console.log(JSON.stringify({
    passed: g.passed, total: g.total,
    footprint: g.footprint, avgTicks: g.avgTicks, score: g.score,
    results: g.results,
  }));
  process.exit(0);
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(1); });
