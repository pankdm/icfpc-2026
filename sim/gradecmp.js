// Compare `lm --grade` (Rust) against tools/lib.js gradeCase (oracle) for a fetched problem.
//   node sim/gradecmp.js <slug> <solution.man>
const { boot } = require('./harness.js');
const lib = require('../tools/lib.js');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const LM = path.join(__dirname, '..', 'interp', 'target', 'release', 'lm');

function buildCase(tc) { return lib.buildCase(tc); }

function rustGrade(rows, tc) {
  const { input, expected, isDisplay, framesJson } = buildCase(tc);
  const f = path.join(os.tmpdir(), `grcmp_${Date.now()}_${Math.random()}.man`);
  fs.writeFileSync(f, rows.join('\n'));
  const args = ['--grade', f];
  if (input) args.push(`--input=${input}`);
  if (expected) args.push(`--expected=${expected}`);
  if (isDisplay) { const ff = f + '.frames'; fs.writeFileSync(ff, framesJson); args.push(`--frames-file=${ff}`); }
  const out = execFileSync(LM, args, { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
  return JSON.parse(out.trim());
}

(async () => {
  const slug = process.argv[2];
  const solFile = process.argv[3];
  const w = await boot();
  const prob = await lib.fetchProblem(slug);
  const rows = fs.readFileSync(solFile, 'utf8').replace(/\r/g, '').split('\n');
  let ok = 0, bad = 0;
  for (const tc of (prob.publicTestData || [])) {
    const oracle = lib.gradeCase(w, rows, tc, prob.tickCap);
    let rust;
    try { rust = rustGrade(rows, tc); } catch (e) { rust = { status: 'RUSTERR', reason: e.message }; }
    const statusMatch = oracle.status === rust.status;
    const tickMatch = oracle.status !== 'pass' || oracle.settleTick === rust.settleTick;
    const good = statusMatch && tickMatch;
    if (good) ok++; else bad++;
    console.log(`${good ? 'OK ' : 'XX '} ${tc.name}: oracle=${oracle.status}@${oracle.settleTick} rust=${rust.status}@${rust.settleTick}${good ? '' : '  <<<'}`);
  }
  console.log(`\n${ok} ok, ${bad} mismatch`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
