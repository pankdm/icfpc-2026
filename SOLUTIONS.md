# Working on solutions (team guide)

Solutions live under `solutions/<problem-slug>/`. Drop as many candidate `.man`
files as you like — one per approach/variant. Name them freely (`p2.man`,
`alice-loop.man`, `golf-v3.man`). Multiple people can add files in parallel;
different filenames never conflict.

## Setup (once)
```
bash sim/fetch-oracle.sh          # downloads the reference interpreter (gitignored)
```
Node 20+ required. No npm install needed.

## Dev loop
```
# grade one file against the public test cases (local, via the reference oracle):
node tools/grade.js triangle solutions/triangle/p2.man

# grade + rank every candidate for a problem:
node tools/grade.js triangle

# submit to the real grader (needs API_KEY in .env):
python3 tools/submit.py triangle solutions/triangle/p2.man

# live server standings — best score to beat + #solvers + true case counts:
python3 tools/status.py
```

`grade.js` reports pass/fail per public case, footprint `max(w,h)²`, average ticks,
and the estimated score (`footprint² × avg ticks`, or just `footprint²` for
footprint-scored problems). **Lower score is better.**

## Rules of thumb
- **Private cases exist** (the public API hides the count; `status.py` shows the real
  total). Local PASS only covers public cases — make solutions *generalize*, never
  hardcode public answers, or you won't pass private cases (and you need ≥1 private
  pass to score).
- **Score = `max(width,height)² × avg ticks`.** Make layouts square, not long/thin;
  keep pipes short; fewer ticks. A few problems are footprint-only.
- **`Y` (fork) may be rejected by the grader** right now (the `split_released` flag) —
  it runs locally but test-submit before relying on it.
- Best-per-problem is just "lowest score that passes all cases" — pick the winner from
  `grade.js` ranking and submit it. Submitting never lowers your score (best counts).

## Layout
```
solutions/<slug>/*.man     candidate solutions
tools/grade.js             local grader (Node — needs the WASM oracle)
tools/submit.py            submit + poll (Python, API-only)
tools/status.py            live standings (Python, API-only)
tools/lib.js               shared: fetch/grade/footprint
sim/                       reference oracle + differential harness
docs/                      reverse-engineered language semantics
interp/                    fast Rust interpreter (WIP; see docs)
```
