#!/usr/bin/env node
// Inspect one cached case at a specific tick without retaining tick history.
//
//   node sim/rust_inspect.js <slug> <file.man> <case-name> <ticks> [round-count]
const fs = require('fs');
const os = require('os');
const path = require('path');
const {execFileSync} = require('child_process');
const lib = require('../tools/lib.js');

const [slug, file, caseName, ticksText, roundCountText] = process.argv.slice(2);
if (!slug || !file || !caseName || !ticksText) {
  console.error(
    'usage: node sim/rust_inspect.js <slug> <file.man> <case-name> <ticks> [round-count]'
  );
  process.exit(2);
}
const ticks = Number(ticksText);
const problem = JSON.parse(fs.readFileSync(
  path.join(lib.REPO, 'tests', `${slug}.json`), 'utf8'
));
const original = problem.publicTestData.find(testCase => testCase.name === caseName);
if (!original) throw new Error(`unknown case ${JSON.stringify(caseName)}`);
const roundCount = roundCountText == null ? original.rounds.length : Number(roundCountText);
const testCase = {...original, rounds: original.rounds.slice(0, roundCount)};
const {input, expected, isDisplay, framesJson} = lib.buildCase(testCase);
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'littleman-rust-inspect-'));
try {
  const args = [`--inspect=${ticks}`, path.resolve(file), `--cap=${ticks}`];
  if (input) args.push(`--input=${input}`);
  if (expected) args.push(`--expected=${expected}`);
  if (isDisplay) {
    const framesFile = path.join(temp, 'frames.json');
    fs.writeFileSync(framesFile, framesJson);
    args.push(`--frames-file=${framesFile}`);
  }
  const lm = path.join(lib.REPO, 'interp', 'target', 'release', 'lm');
  const output = execFileSync(lm, args, {encoding: 'utf8', maxBuffer: 256 * 1024 * 1024});
  console.log(output.trim());
} finally {
  fs.rmSync(temp, {recursive: true, force: true});
}
