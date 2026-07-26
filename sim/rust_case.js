#!/usr/bin/env node
// Grade one cached public case with the fast Rust interpreter.
//
// Unlike the editor WASM harness this interpreter does not retain per-tick
// snapshots, so it can run to the judge's real tick cap without exhausting a
// 4 GiB recorder heap.
//
//   node sim/rust_case.js <slug> <file.man> <case-name> [round-count] [cap]
const fs = require('fs');
const os = require('os');
const path = require('path');
const {execFileSync} = require('child_process');
const lib = require('../tools/lib.js');

const LM = path.join(lib.REPO, 'interp', 'target', 'release', 'lm');

(() => {
  const [slug, file, caseName, roundCountText, capText] = process.argv.slice(2);
  if (!slug || !file || !caseName) {
    console.error(
      'usage: node sim/rust_case.js <slug> <file.man> <case-name> [round-count] [cap]'
    );
    process.exit(2);
  }
  const problem = JSON.parse(fs.readFileSync(
    path.join(lib.REPO, 'tests', `${slug}.json`), 'utf8'
  ));
  const original = problem.publicTestData.find(testCase => testCase.name === caseName);
  if (!original) throw new Error(`unknown case ${JSON.stringify(caseName)}`);
  const roundCount = roundCountText == null ? original.rounds.length : Number(roundCountText);
  if (!Number.isInteger(roundCount) || roundCount < 1 || roundCount > original.rounds.length) {
    throw new Error(`round-count must be within 1..${original.rounds.length}`);
  }
  const cap = capText == null ? (problem.tickCap || 50_000_000) : Number(capText);
  if (!Number.isInteger(cap) || cap < 0) throw new Error('cap must be non-negative');
  const testCase = {...original, rounds: original.rounds.slice(0, roundCount)};
  const {input, expected, isDisplay, framesJson} = lib.buildCase(testCase);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'littleman-rust-case-'));
  const framesFile = path.join(temp, 'frames.json');
  try {
    const args = ['--grade', path.resolve(file), `--cap=${cap}`];
    if (input) args.push(`--input=${input}`);
    if (expected) args.push(`--expected=${expected}`);
    if (isDisplay) {
      fs.writeFileSync(framesFile, framesJson);
      args.push(`--frames-file=${framesFile}`);
    }
    const output = execFileSync(LM, args, {
      encoding: 'utf8',
      maxBuffer: 256 * 1024 * 1024,
    });
    const result = JSON.parse(output.trim());
    console.log(JSON.stringify({
      slug,
      file,
      case: caseName,
      rounds: roundCount,
      tickCap: cap,
      ...result,
    }));
    process.exitCode = result.status === 'pass' ? 0 : 1;
  } finally {
    fs.rmSync(temp, {recursive: true, force: true});
  }
})();
