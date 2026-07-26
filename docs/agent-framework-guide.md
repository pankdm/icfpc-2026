# Littleman solution framework: an agent's field guide

This guide explains how to turn a contest problem into a correct, measurable,
and optimizable `.man` program using this repository. Read `PROBLEM.md` first;
the language's pipe binding, display timing, and multi-man behavior are not
conventional.

The short version is:

1. Cache and understand the problem.
2. Write a reference model before designing the machine.
3. Build with the highest-level reusable layer that fits.
4. Verify semantics independently of the generated grid.
5. Grade with the Rust interpreter for iteration and WASM as the final oracle.
6. Profile before optimizing.
7. Keep every working variant and record official results in `tl`.

## 1. Start from evidence

Refresh the problem cache and inspect its real limits and public cases:

```bash
python3 tools/fetch_tests.py <slug>
jq '{tickCap, publicCases: (.publicTestData | length)}' tests/<slug>.json
python3 tools/status.py
```

Create an epic or attach work to the existing one. Keep correctness,
architecture, optimization, stress testing, and submission as separate tasks
when they can fail independently:

```bash
tl create "Solve <problem>" --priority 0 \
  --description "Correct general solver, public verification, optimization, submission"
tl create "<problem>: reference model and public verifier" \
  --parent <epic-id> --priority 0
tl claim <task-id>
tl note add <task-id> "Measured result, artifact, and conclusion"
tl close <task-id> --as done
```

Before writing a machine, determine:

- the complete input and output protocol, including multiple rounds;
- minimum and maximum sizes and values;
- whether output is integers or display frames;
- whether the score uses ticks, footprint only, or both;
- the tick cap and likely dominant case;
- invariants that private tests are likely to exercise.

Do not infer generality from the public examples. Explicitly test empty/minimum
inputs, maximum inputs, negatives, duplicates, repeated rounds, and persistent
state where the problem allows them.

## 2. Choose the right construction layer

The framework has four useful levels. Use the highest one that expresses the
algorithm without fighting it.

### Raw grid: `tools/littleman.py`

`Program` is the common output model. It places rooms, displays, instructions,
and pipes, renders only the non-space bounding box, and saves `.man` files.

```python
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

from littleman import Program

p = Program()
p.input_room(0, 0)
p.output_room(4, 0)
p.room(0, 5, 9, 4)
p.text(1, 6, "@rM*+Wv")
p.text(1, 7, "H.s/W2<")
p.pipe([(1, 3), (1, 4)])
p.pipe([(5, 4), (5, 3)])
p.save(os.path.join(HERE, "candidate.man"))
print(p.footprint())
```

Use this for small hand-designed programs and for stamping reusable gadgets.
Add broadly reusable patterns below `# === PATTERNS ===` in
`tools/littleman.py`; keep problem-specific logic in the problem builder.

### Collision-safe geometry: `tools/layout.py`

`Layout` wraps `Program` and rejects differing glyphs placed on the same cell.
It also provides a walking cursor, man corridors, explicit pipe routing, FIFO
rings, relay men, and automatic pipe routing.

Prefer it when geometry is the hard part:

```python
from layout import Layout

l = Layout()
l.room(0, 0, 12, 8)
l.goto(1, 1).emit("@rM1+").turn("S").emit("s")
l.save("solutions/<slug>/candidate.man")
```

Important distinction:

- `route(...)` creates a path walked by a man; its straight cells are spaces.
- `Program.pipe(...)`, `place_pipe(...)`, and `auto_pipe(...)` create value
  channels and must satisfy pipe endpoint and arrow rules.

For nontrivial routing, also see `tools/router.py` and
`docs/routing-requirements.md`.

### Generated control flow: `tools/flowgrid.py`

`Flow` represents labeled basic blocks containing ordinary glyphs plus named
ports, jumps, and three-way branches. `lay_cfg_controller` turns the graph into
a routed room.

```python
from flowgrid import Flow

f = Flow()
f.at("START").e("r", "M", "1", "+").br("POS", "ZERO", "NEG")
f.at("POS").e("s", "H")
f.at("ZERO").e("0", "s", "H")
f.at("NEG").e("N", "s", "H")
```

This layer is deliberately predictable rather than spatially optimal. Useful
layout switches include pooled edges, target coalescing, edge deduplication,
tight gaps, local fallthrough edges, and `code_x`. Always search the minimum
routable `code_x`; Pathfinder improved both ticks and footprint simply by
moving it from 380 to 60.

### Stateful display programs: `tools/stateflow.py`

`stateflow.Flow` adds macros for:

- scalar RAM: `load`, `store`, `loadv`, `storev`;
- 256-cell RAM: `cell_load`, `cell_store`;
- round input and scratch pipes;
- display address/data/commit;
- optional physical FIFO queue.

`stateflow.build_program(...)` compiles the controller and attaches the chosen
hardware:

```python
program = stateflow.build_program(
    build_flow(),
    scalar_size=32,
    scalar_belts=4,
    code_x=60,
    queue=True,
    fast_cell_ram=True,
    cell_belts=9,
    packed_cell=True,
)
```

Reusable state gadgets live in:

- `tools/belt_ram.py`: simple serial RAM;
- `tools/split_ram.py`: parallel banked RAM with the same command protocol;
- `tools/packed_ram_proxy.py`: fewer controller sends per cell request;
- stateflow's queue, scratch, input, and display wiring.

Keep service ownership explicit. An `r`, `s`, or `q` binds to the nearest pipe,
not the nearest ready pipe. A reply pipe has one destination room. Splitting a
controller into rooms therefore requires deliberate request multiplexing and
reply routing; drawing more rooms alone is not modularity.

## 3. Make the builder the source of truth

Put generated candidates under `solutions/<slug>/` and keep the builder beside
them:

```text
solutions/<slug>/
  build.py
  verify.py
  approach-a.man
  approach-a-compact.man
```

Builders should be deterministic, dependency-free, and callable from the repo
root. Expose architectural and geometry choices as command-line arguments and
encode them in the output filename. Never hand-edit a generated `.man`; change
the builder and regenerate it.

Keep every valid variant. A failed optimization is useful evidence, but do not
replace or delete the working champion. Put one-off probes and broken gadget
experiments in `scratchpad/` when they are not meaningful solution variants.

## 4. Verify the algorithm separately

A locally passing grid is necessary but it is a poor debugger. Write a
`verify.py` that:

1. implements a clear reference algorithm;
2. reproduces every public expected output/frame;
3. evaluates the generated `Flow` or protocol at a semantic level when
   practical;
4. generates adversarial cases around the problem's bounds.

Pathfinder's `verify_fifo.py` is a good example: reverse BFS and the generated
Flow are checked independently before spending interpreter ticks.

For supported problems, generate and use stress suites:

```bash
python3 tools/stress.py <slug>
node tools/grade_json.js <slug> solutions/<slug>/candidate.man \
  --cases tests/stress/<slug>.json
```

Test persistent multi-round behavior in one interpreter run. Restarting the
program between rounds hides stale queue, RAM, display-buffer, and epoch bugs.

## 5. Run the right interpreter

The Rust interpreter is the fast development engine:

```bash
cd interp
cargo build --release
cargo test --release
cd ..

node sim/rust_case.js <slug> solutions/<slug>/candidate.man "<case name>"
node sim/rust_case.js <slug> solutions/<slug>/candidate.man "<case name>" 1 15000000
```

It runs heavy cases without retaining WASM snapshots and can use the judge's
real tick cap. Use one heavy case per process when comparing candidates.

The organizer WASM remains the ground-truth final check:

```bash
bash sim/fetch-oracle.sh
node tools/grade.js <slug> solutions/<slug>/candidate.man
node tools/grade_json.js <slug> solutions/<slug>/candidate.man --failfast
```

If a heavy WASM run dies with `Go program has already exited`, rerun candidates
one at a time or use Rust for iteration. Do not reinterpret an oracle OOM as a
program failure.

When changing the Rust interpreter, run its unit tests and differential checks
against WASM. Interpreter speed is useful only while semantics remain in
parity.

## 6. Profile before optimizing

Score is normally:

```text
max(width, height)^2 * average ticks
```

The two factors call for different tools:

```bash
node sim/xray.js <slug> solutions/<slug>/candidate.man
node sim/profile.js <slug> solutions/<slug>/candidate.man
LM_PROFILE=1 node sim/rust_case.js \
  <slug> solutions/<slug>/candidate.man "<dominant case>"
```

The Rust profile reports glyph, room, room/glyph, and cell execution counts.
Interpret hot `r`/`s` cells as service stalls, hot blank cells as walking or
routed-corridor cost, and hot compute glyphs as an algorithm/protocol issue.
Profile exact cells: a glyph-wide count can mix one genuine bottleneck with
many harmless parked workers.

Use `xray.js` to answer:

- which dimension drives the scoring box;
- which case dominates average ticks;
- which man and corridor dominate travel;
- how much tick-cap headroom remains.

Optimization should follow the measured bottleneck:

| Observation | First experiments |
| --- | --- |
| One dimension dominates | fold or relocate rooms/components; shrink free margins |
| Hot blank cells/corridors | reorder hot CFG blocks; shorten return lanes; split phases |
| Hot reply `r` | shorten the pipe, bank the service, or batch independent requests |
| Hot sends/protocol | pack request fields; remove dependent round trips |
| Hot arithmetic | replace expensive classification/decoding with bit operations |
| One dominant case | optimize its algorithmic work before constant tuning |
| Near tick cap | prioritize latency/asymptotics over footprint until it passes |

## 7. Optimize in the right order

### Fold the scoring box

Footprint is the bounding box of non-space cells. Indentation, trailing spaces,
and blank lines are free, but a distant room or pipe endpoint is not.

Aim for a square. Reducing the shorter dimension does nothing while the longer
dimension still drives `max(width, height)^2`. Typical safe wins are:

- move the controller to the minimum routable origin;
- place independent components beside each other instead of in one column;
- tuck I/O rooms and relays into dead margins;
- shorten pipes and pull room walls inward;
- delete globally empty rows and columns only after checking routing.

Useful tools:

```bash
python3 tools/compact_man.py <file.man>
python3 tools/roomfit.py <slug> <file.man> --dry-run
python3 tools/lift.py <file.man>
python3 tools/place.py <slug> <file.man> --dry-run
```

The lift/place pipeline is experimental. Treat oracle verification as the
correctness gate for any mechanically relocated program.

### Cut walking and control-flow routing

The generated CFG spends space so routes cannot collide. Once correct:

- put common fallthrough blocks adjacent;
- put the hottest loop in a compact band;
- pool non-overlapping route intervals;
- coalesce equal branch targets;
- duplicate a tiny cold block if that removes a long hot return;
- split setup, compute, and playback only when state handoff is explicit.

For multi-room modules, write down at each boundary:

- values sent and their order;
- which room owns each mutable service;
- which man may issue the next request;
- how replies are associated with requesters;
- which A/B/BP values must survive the handoff.

### Reduce protocol work

Count physical operations, not source-level macros. One logical RAM access may
include several scalar loads, scratch sends, pipe traversals, and reply stalls.
Useful transformations include:

- packed command words;
- negative address markers for writes;
- epoch tags instead of clearing a whole memory;
- a physical FIFO instead of linked-list pointer traffic;
- delta display writes instead of repainting all 256 cells.

### Add parallelism only where work is independent

`Y` is safe, but it does not make dependent requests independent. Define job
ownership and reply association first. A replicated memory can be slower when
every write must be broadcast to all replicas.

Pathfinder is the cautionary example:

- four mirrored cell RAMs made the heavy case slower because of broadcast and
  routing overhead;
- four scalar banks improved public average ticks by 35% at no footprint cost,
  and improved the official result from 13/18 to 17/18;
- eight scalar banks were slightly worse over full cases because setup and
  routing overhead exceeded the additional contention reduction.

Benchmark complete multi-round cases, not only one round.

### Tune constants last

Once architecture and geometry are sound:

```bash
python3 tools/autotune.py <slug> solutions/<slug>/build.py --dry-run
python3 tools/autotune.py <slug> solutions/<slug>/build.py \
  --jobs 8 --budget 1200
```

See `tools/AUTOTUNE.md`. Autotuning can find a few percent; it will not repair
an algorithm that is several times slower than the board leader.

## 8. Diagnose failures locally

Classify the failure before editing:

- `wrong-frames` / wrong output: inspect the first divergent frame/value and
  the state transition that emitted it;
- `step-cap`: profile the dominant case and estimate the required percentage
  reduction;
- load error: inspect the reported room, pipe, or glyph coordinate;
- deadlock: inspect pipe endpoints and values, then check nearest-pipe binding;
- wall/bad-op: inspect the failing man, position, and heading;
- public pass/private fail: audit generality and worst-case work, not the public
  expected values.

For display problems, use a small hand-written case:

```bash
node sim/case.js solutions/<slug>/candidate.man '<json-rounds>'
```

The Rust inspector includes pipe endpoint and room metadata, which is especially
useful when two incoming pipes accidentally bind to the same `r`.

## 9. Submit and preserve the result

Before submission:

```bash
python3 solutions/<slug>/verify.py
# Run every public case under Rust.
node tools/grade.js <slug> solutions/<slug>/candidate.man
git diff --check
git add solutions/<slug>/build.py solutions/<slug>/candidate.man
git commit -m "<slug> <variant>: <measured improvement>"
```

Commit the exact generated artifact before submitting it. The contest API does
not provide a way to download submitted program text, so git is the only
durable record of what the grader ran.

Then:

```bash
python3 tools/submit.py <slug> solutions/<slug>/candidate.man
```

Submission needs `API_KEY` in `.env`. At most five submissions may be pending.
A later submission cannot lower the stored best score, so submit a materially
faster, fully verified variant while continuing local optimization.

Record:

- artifact filename and commit;
- footprint, per-public-case ticks, and local score;
- submission ID;
- official passed/total split and score;
- the conclusion, including negative experiments.

```bash
tl note add <task-id> \
  "Submission <id>: 17/18; 7/7 public + 10/11 private; one private step-cap"
```

Commit messages should identify the problem, variant, measured change, and
official result when known:

```text
pathfinder scalar-s4: split hot state service, 13/18->17/18
```

## 10. Handoff checklist

Before another agent takes over, leave:

- a committed builder and every meaningful working `.man` variant;
- the exact champion filename;
- local per-case ticks and footprint;
- latest official result and submission ID;
- current bottleneck backed by profiler output;
- failed experiments and why they failed;
- open `tl` tasks with notes;
- reusable semantics or gadget lessons in `docs/`.

The best handoff is not “try to optimize it.” It is “this exact reply cell
accounts for 22% of the dominant round; four banks remove most of that wait,
and the remaining cost is the controller's BFS return corridors.”
