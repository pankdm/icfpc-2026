#!/usr/bin/env node
// Grade one cached public case in a fresh WASM process.
//
// Heavy generated programs can exhaust the Go oracle when several cases share
// one process. This isolates both memory and failures:
//   node sim/grade_one_case.js <slug> <file.man> <case-name> [round-count]
const fs = require('fs');
const path = require('path');
const { boot } = require('./harness.js');
const lib = require('../tools/lib.js');

(async () => {
  const [slug, file, caseName, roundCountText] = process.argv.slice(2);
  if (!slug || !file || !caseName) {
    console.error(
      'usage: node sim/grade_one_case.js <slug> <file.man> <case-name> [round-count]'
    );
    process.exit(2);
  }
  const specPath = path.join(lib.REPO, 'tests', `${slug}.json`);
  const problem = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  const originalCase = problem.publicTestData.find(tc => tc.name === caseName);
  if (!originalCase) {
    console.error(`unknown case ${JSON.stringify(caseName)}`);
    process.exit(2);
  }
  const roundCount = roundCountText == null ? null : Number(roundCountText);
  if (roundCount != null && (!Number.isInteger(roundCount) || roundCount < 1)) {
    console.error('round-count must be a positive integer');
    process.exit(2);
  }
  const testCase = roundCount == null
    ? originalCase
    : {...originalCase, rounds: originalCase.rounds.slice(0, roundCount)};
  const wasm = await boot();
  const rows = lib.manRows(lib.readMan(file));
  const result = lib.gradeCase(wasm, rows, testCase, problem.tickCap);
  console.log(JSON.stringify({
    slug,
    file,
    case: caseName,
    rounds: testCase.rounds.length,
    tickCap: problem.tickCap,
    ...result,
  }));
  process.exit(result.status === 'pass' ? 0 : 1);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
