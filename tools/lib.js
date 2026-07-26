// Shared infra for local grading + submission of littleman solutions.
// Local grading replicates the reference editor's runCase() exactly, judged by the
// same littleman.wasm the server grades with, so local PASS ⇒ public-case PASS.
const fs = require('fs');
const path = require('path');

const BASE = 'https://icfpcontest2026.com/api/v1';
const REPO = path.join(__dirname, '..');

function apiKey() {
  const envPath = path.join(REPO, '.env');
  if (fs.existsSync(envPath)) {
    for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
      const m = line.match(/^\s*API_KEY\s*=\s*(.+?)\s*$/);
      if (m) return m[1].replace(/^["']|["']$/g, '');
    }
  }
  return process.env.API_KEY || null;
}

async function fetchProblem(slug) {
  const r = await fetch(`${BASE}/public/problems/${slug}`);
  if (!r.ok) throw new Error(`fetch ${slug}: HTTP ${r.status}`);
  return r.json();
}
async function listProblems() {
  const r = await fetch(`${BASE}/public/problems`);
  if (!r.ok) throw new Error(`list problems: HTTP ${r.status}`);
  return r.json();
}
async function problemStandings(problemId) {
  const r = await fetch(`${BASE}/standings/problems/${problemId}`);
  if (!r.ok) return null;
  return r.json();
}

function readMan(file) {
  return fs.readFileSync(file, 'utf8');
}
function manRows(text) {
  return text.replace(/\r/g, '').split('\n');
}

// Footprint = max(width,height)^2 over the bounding box of NON-SPACE cells.
function footprint(rows) {
  let minx = 1e9, miny = 1e9, maxx = -1, maxy = -1;
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      if (row[x] !== ' ') { if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; }
    }
  });
  if (maxx < 0) return { w: 0, h: 0, box: 0 };
  const w = maxx - minx + 1, h = maxy - miny + 1, m = Math.max(w, h);
  return { w, h, box: m * m };
}

// A test case -> the strings the oracle's load() wants: '/'-separated rounds for
// input/expected, a flat expected token list for comparison, and a frames JSON.
function buildCase(tc) {
  const rounds = tc.rounds || [{ in: tc.in || [], out: tc.out || [] }];
  const input = rounds.map(r => (r.in || []).join(' ')).join(' / ');
  const expected = rounds.map(r => (r.out || []).join(' ')).join(' / ');
  const expectedFlat = [].concat(...rounds.map(r => (r.out || []).map(String)));
  // Frames must be grouped per round (rounds × frames × rows) — the oracle rejects
  // a flat frame list with a load error.
  const perRoundFrames = rounds.map(r => r.frames || []);
  const isDisplay = perRoundFrames.some(fr => fr.length > 0);
  return { input, expected, expectedFlat, isDisplay, framesJson: isDisplay ? JSON.stringify(perRoundFrames) : '' };
}

// Streaming prefix compare (matches the reference Ps()).
function judgeOutput(output, expectedFlat) {
  const o = output.map(String);
  for (let i = 0; i < o.length; i++) {
    if (i >= expectedFlat.length) return 'extra';
    if (o[i] !== expectedFlat[i]) return 'diverged';
  }
  return o.length === expectedFlat.length ? 'match' : 'pending';
}

// Grade one case against the oracle. Returns {status, settleTick, reason?}.
function gradeCase(w, rows, tc, tickCap) {
  const { input, expected, expectedFlat, isDisplay, framesJson } = buildCase(tc);
  const s = w.newSession();
  let j;
  try {
    j = JSON.parse(w.load(s, rows, input, expected, framesJson));
    if (j.type === 'error') return { status: 'loaderror', reason: j.message };
    const cap = tickCap || 5_000_000;
    while (!j.halted && !j.outputSettled && j.step < cap) {
      const nj = JSON.parse(w.stepN(s, 5000, false));
      if (nj.type === 'error') { j = nj; break; }
      if (nj.step === j.step) { j = nj; break; }
      j = nj;
    }
  } finally {
    w.closeSession(s);
  }
  if (j.type === 'error') return { status: 'crash', reason: j.message };
  const out = j.output || [];
  const fj = j.frameJudge || null;
  const tick = j.step;
  if (fj && fj.mismatch) return { status: 'fail', settleTick: tick, reason: `frame ${fj.mismatch.index + 1}/${fj.total} wrong` };
  const l = judgeOutput(out, expectedFlat);
  const framesOk = !fj || fj.matched >= fj.total;
  if (l === 'match' && framesOk) return { status: 'pass', settleTick: tick };
  if (l === 'diverged' || l === 'extra') return { status: 'fail', settleTick: tick, reason: l };
  if (j.halted && j.reason !== 'done') return { status: 'crash', settleTick: tick, reason: (j.fatal && j.fatal.reason) || j.reason };
  if (j.halted) return { status: 'fail', settleTick: tick, reason: isDisplay ? `missing frames (${fj ? fj.matched : 0}/${fj ? fj.total : '?'})` : 'missing output' };
  return { status: 'timeout', settleTick: tick, reason: `no verdict after ${tick} ticks` };
}

// Grade a program (rows) against all public cases of a fetched problem.
// opts.stopOnFail: abandon the run at the first non-passing case. A candidate that fails
// any case can never be accepted, so grading the rest is pure cost (used by autotune).
function gradeAll(w, rows, problem, opts) {
  const cases = problem.publicTestData || [];
  const fp = footprint(rows);
  const results = [];
  for (const tc of cases) {
    const r = { name: tc.name || '(case)', ...gradeCase(w, rows, tc, problem.tickCap) };
    results.push(r);
    if (opts && opts.stopOnFail && r.status !== 'pass') break;
  }
  const passed = results.filter(r => r.status === 'pass');
  const ticks = passed.map(r => r.settleTick);
  const avgTicks = ticks.length ? ticks.reduce((a, b) => a + b, 0) / ticks.length : null;
  const footprintOnly = problem.scoring === 'footprint';
  const score = passed.length === results.length && results.length
    ? (footprintOnly ? fp.box : (avgTicks != null ? fp.box * avgTicks : null))
    : null;
  return { results, passed: passed.length, total: results.length, footprint: fp, avgTicks, score, footprintOnly };
}

module.exports = { BASE, REPO, apiKey, fetchProblem, listProblems, problemStandings, readMan, manRows, footprint, buildCase, judgeOutput, gradeCase, gradeAll };
