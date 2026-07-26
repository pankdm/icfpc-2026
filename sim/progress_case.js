#!/usr/bin/env node
// Stream tick/frame progress for a heavy cached public case in one WASM session.
// The last printed checkpoint remains useful when the Go recorder exhausts RAM.
//
//   node sim/progress_case.js <slug> <file.man> <case-name> [round-count]
const fs = require('fs');
const path = require('path');
const { boot } = require('./harness.js');
const lib = require('../tools/lib.js');

(async () => {
  const [slug, file, caseName, roundCountText] = process.argv.slice(2);
  if (!slug || !file || !caseName) {
    console.error(
      'usage: node sim/progress_case.js <slug> <file.man> <case-name> [round-count]'
    );
    process.exit(2);
  }
  const problem = JSON.parse(fs.readFileSync(
    path.join(lib.REPO, 'tests', `${slug}.json`), 'utf8'
  ));
  const original = problem.publicTestData.find(testCase => testCase.name === caseName);
  if (!original) throw new Error(`unknown case ${JSON.stringify(caseName)}`);
  const roundCount = roundCountText == null ? original.rounds.length : Number(roundCountText);
  const testCase = {...original, rounds: original.rounds.slice(0, roundCount)};
  const { input, expected, framesJson } = lib.buildCase(testCase);
  const rows = lib.manRows(lib.readMan(file));
  const wasm = await boot();
  const session = wasm.newSession();
  let state = JSON.parse(wasm.load(session, rows, input, expected, framesJson));
  if (state.type === 'error') {
    console.log(JSON.stringify(state));
    process.exit(1);
  }
  let nextReport = 500_000;
  const cap = problem.tickCap || 50_000_000;
  while (!state.halted && !state.outputSettled && state.step < cap) {
    state = JSON.parse(wasm.stepN(session, 5000, false));
    if (state.type === 'error') break;
    if (state.step >= nextReport) {
      console.log(JSON.stringify({
        step: state.step,
        frames: state.frameJudge && state.frameJudge.matched,
        totalFrames: state.frameJudge && state.frameJudge.total,
        mismatch: state.frameJudge && state.frameJudge.mismatch,
      }));
      nextReport += 500_000;
    }
    if (state.frameJudge && state.frameJudge.mismatch) break;
  }
  console.log(JSON.stringify({
    final: true,
    step: state.step,
    halted: state.halted,
    outputSettled: state.outputSettled,
    reason: state.reason || state.message,
    frameJudge: state.frameJudge,
  }));
  wasm.closeSession(session);
  process.exit(0);
})().catch(error => {
  console.error(error);
  process.exit(1);
});
