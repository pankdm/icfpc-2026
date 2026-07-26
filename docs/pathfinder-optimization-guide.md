# Pathfinder optimization: measure service latency and controller geometry separately

This guide records the work that moved Pathfinder from the committed 17/18
scalar-banked solver to a materially faster, nearly square reflow.  The method
applies to the other large `stateflow` programs, especially Snake, LLM, and
LLLM.

## Result

Baseline:

```text
solutions/pathfinder/reverse-bfs-fifo-b9-s4-x60.man
footprint 381x496, box 246016
public ticks 4.003M 5.448M 3.791M 3.699M 4.978M 5.103M 2.904M
average 4.275M
official 17/18 (one private step-cap)
```

Reflow:

```text
solutions/pathfinder/reverse-bfs-fifo-b9-s4-reflow-cx0-o0.man
footprint 321x306, box 103041
public ticks 3.204M 4.386M 3.007M 2.949M 3.991M 4.098M 2.276M
average 3.416M
Rust 7/7; organizer WASM 7/7, one fresh process per case
```

The reflow reduces average ticks by 20.1%, the scoring box by 58.1%, and the
public footprint-tick score by 66.5%.  It preserves the same algorithm,
services, command protocols, queue capacity, and scalar/cell bank counts.

## The two bottlenecks are different

Pathfinder has two optimization objectives:

1. Passing the final private case requires fewer ticks.
2. Improving rank after correctness requires a smaller `max(width,height)^2`.

A geometry-only change can solve both when the controller spends significant
time walking.  It cannot remove serialized RAM dependencies.  Keep the two
measurements separate and do not infer tick-cap headroom from score.

On `a cluttered field`, the s7 controller room executed approximately:

```text
blank cells  2.517M
receive r    2.176M
total ticks  4.929M
```

After reflow, s4 executed:

```text
blank cells  1.227M
receive r    2.562M
total ticks  3.991M
```

The reflow removed about half the controller's blank travel.  That exposed
serialized receive latency as the next bottleneck.  Aggregate glyph profiles
are misleading because parked RAM workers execute `r` every tick; inspect the
controller room and exact cells.

## What worked

### Preserve the logical machine and replace only the CFG layouter

`stateflow.build_program` now accepts an optional `lay_fn`.  The
boustrophedon layouter in `tools/boustro.py`:

- uses east- and west-heading rows for real operations;
- places each `r`/`s` only inside the Voronoi band of its intended port;
- interval-colors control-flow returns onto shared west-side corridors;
- keeps the service floor and its relative pipe geometry unchanged.

This is safer than moving rooms after assembly.  The Flow graph remains the
semantic source, and the physical builder still owns RAM, queue, scratch,
input, and display routing.

### Remove empty goto aliases before layout

Operation-free goto blocks add entries and long returns without doing work.
Resolve their targets transitively and remove them before placement.  Do not
merge blocks that carry register state or service operations.

### Search the minimum controller origin

The first port-safe reflow used `code_x=30`:

```text
351x306, average 3.628M
```

Moving the same layout to `code_x=0` produced:

```text
321x306, average 3.416M
```

The smaller origin shortened hot rows and made the whole machine almost
square.  `op_slack=0` is the current minimum useful operation width.  Always
sweep the origin again after changing ports or the CFG.

### Verify binding intent, not only parse validity

The reflow builder records the intended port for every emitted `r`/`s`.
After assembly it recovers actual pipe attachments from the organizer
analyzer and checks Manhattan-nearest ownership for all 704 controller port
operations.

Large grids exposed two validator bugs:

- padded program JSON can exceed the OS argument-size limit;
- `process.exit()` can truncate analyzer JSON at 64 KiB.

`tools/pipecheck.py` now sends rows over stdin and waits for stdout to flush.

### Use Rust for iteration and isolate final WASM cases

All layout sweeps, profiles, and seven-case grading use the release Rust
interpreter.  The organizer WASM recorder can exceed 4 GB when several heavy
cases run in one process.  `tools/grade_json.js --case-index N` makes the final
oracle gate reliable by running each public case in a fresh process.

## What did not work, or no longer pays

- Scalar banks 4 to 7 improved public average by only about 1%; both remained
  17/18 officially.
- Small bank-count and port-band tuning is below the remaining private-case
  requirement.
- More mirrored cell RAMs were slower because writes and routing were
  replicated while the controller still issued dependent reads serially.
- Pure footprint compaction improves score but cannot clear a step cap unless
  it also shortens walked paths or pipes.
- Splitting setup/BFS/playback into rooms without explicit service ownership
  is unsafe.  Replies have one destination, and nearest-pipe instructions do
  not dynamically choose a ready service.

## Reusable workflow for Snake, LLM, and LLLM

1. Regenerate the champion and prove it is byte-identical.
2. Run the complete public suite with release Rust and record per-case ticks.
3. Profile the dominant case by room and exact cell.
4. Separate controller blank travel, controller service stalls, and parked
   worker stalls.
5. Inventory every port and write down service ownership and reply
   destination.
6. Try a controller-only boustrophedon reflow through `lay_fn`.
7. Sweep `code_x` and operation slack, stopping on the first failed case.
8. Verify every intended nearest-pipe binding after final assembly.
9. Compare width, height, max-dimension box, every public tick count, and
   footprint-tick score.
10. Use the organizer WASM only for the final candidate, one heavy case per
    process when necessary.

For Snake, the immediate target is its tall controller: fold it toward a
square without moving FIFO/RAM/display ownership.  For LLM and LLLM, first
measure whether height comes from executable CFG rows, return corridors, or
service placement.  Reflow only the part that drives the box; after blank
travel falls, switch to protocol or algorithm work if exact controller
`r`/`s` cells dominate.

## Snake application

Applying the same layouter to Snake's existing compact service floor produced:

```text
baseline linked-compact-cx60-cb8.man
  220x347, avg 237548, local score 28.603B

reflow linked-compact-reflow-cx10-o0.man
  170x253, avg 186425, local score 11.933B
```

All five public cases pass in both Rust and the organizer WASM.  The reflow
cuts average ticks by 21.5%, the scoring box by 46.8%, and local score by
58.3%.  The minimum binding-safe controller origin is `code_x=10`; `code_x=0`
cannot reach the first receive port's Voronoi band.  Increasing operation
slack from 0 through 100 did not reduce controller height because port bands,
not the general operation limit, force the row wraps.

On `the long game`, the reflow controller executes about 376k receives and
212k blanks in 626k total ticks.  As in Pathfinder, geometry exposed serialized
service receives as the next bottleneck.  Further square-folding requires
fewer CFG rows or a more compact service protocol, not extra horizontal slack.

## LLM application

LLM uses `solutions/little-little-man/build_subset.py` rather than
`tools/stateflow.py`, but it has the same controller-over-services shape.  An
optional `lay_fn` hook there allows the banked/deduplicated Flow to reuse the
same boustrophedon layouter.

```text
baseline pipe-io-banked-dedup.man
  612x1768, avg 13.377M, local score 41.81T

reflow pipe-io-banked-dedup-boustro-cx45-o0.man
  277x1137, avg 10.893M, local score 14.08T
```

The reflow passes all 14 public cases under release Rust, reduces average
ticks by 18.6%, and reduces local score by 66.3%.  The minimum tested
binding-safe origin is `code_x=45`; widening operation slack did not reduce
the 994-row controller because service-port bands force the wraps.

Representative ticks:

```text
first steps  5.121M -> 4.375M
grand tour  19.389M -> 16.147M
```

On reflowed `grand tour`, controller room 0 executes about 13.18M receives and
2.60M blanks in 16.15M ticks.  LLM is therefore now much more service-latency
bound than geometry-latency bound.  Another layout pass should target the
remaining 1137-row box; another tick pass must reduce RAM transactions or
their latency.
