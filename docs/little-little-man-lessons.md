# Little Little Man: solver engineering lessons

This note records the techniques that took `little-little-man` from diagnostic
programs that timed out or drew wrong frames to a general 28/28 solver. It is
intended as working context for agents building the other stateful Semester-4
programs, especially Snake and Pathfinder.

## Result and reusable artifacts

The current champion is:

```
solutions/little-little-man/pipe-io-banked-dedup.man
```

Its official submission passed 28/28 cases with score
`44,914,230,264,086.86`. The corresponding builder and shared infrastructure
are more important than the generated grid:

- `solutions/little-little-man/build_pipe_io.py` is the end-to-end compiler and
  physical-layout example.
- `tools/flowgrid.py` is the control-flow/grid compiler. It keeps semantic
  labels and branches separate from physical routing.
- `tools/belt_ram.py` contains reusable indexed-memory building blocks.
- `tools/grade_fast.py` runs public cases with the Rust interpreter in
  parallel, reports progress, and fails quickly.
- `sim/rust_case.js` runs one cached or hand-written case.
- `sim/rust_inspect.js` exposes checkpoints, man state, registers, pipe
  occupancy, input position, committed frames, and failure state.
- `sim/profile.js` and `sim/xray.js` identify hot cells, stalls, corridors, and
  the footprint dimension that drives score.

Generated `.man` files are products, not source. Preserve every working
variant and make changes in its builder.

## Separate semantic correctness from physical correctness

The LLM compiler first reached 14/14 in its Flow-level verifier while the
physical program still hit the step cap. These are different bugs:

1. The semantic model answers whether the algorithm emits the right frames.
2. The physical model answers whether men can traverse the placed control
   flow, bind to the intended pipes, and finish within the tick cap.

Do not debug both layers at once. For a new solver:

1. Write a host-language reference model for every public case and important
   edge case.
2. Verify the generated control-flow program against that model.
3. Run the smallest physical case in Rust.
4. Only then run fail-fast public grading.

A physically stuck program often has a correct algorithm. Treat a timeout as a
geometry or synchronization failure until checkpoints show otherwise.

## Rust checkpoints are the primary debugger

The WASM oracle remains the judge-compatible reference, but its recorder can
consume roughly 4 GB and die on a long trace. That is an instrumentation/OOM
failure, not evidence of a contest tick cap. The cached problem metadata's
`tickCap` is authoritative.

Use the Rust interpreter for the inner loop:

```bash
python3 tools/grade_fast.py <slug> <candidate.man> --jobs 4 --progress
node sim/rust_case.js <candidate.man> '<json-rounds>'
node sim/rust_inspect.js <slug> <candidate.man> --case 0
```

When a case stalls:

1. Note the stopped man's exact `(x,y)`, direction, `A`, `B`, `BP`, and room.
2. Map the cell back to the builder's Flow label.
3. Inspect nearby pipe occupancy and remaining input values.
4. Check committed-frame count before changing algorithm logic.

This localized two serious LLM failures immediately: one `s` instruction had
bound to the display-address pipe, and one `r` instruction had bound to the
scalar-memory reply pipe. Both looked like generic timeouts from the outside.

## Nearest-pipe binding is part of the program

`r`, `s`, and `q` permanently target the nearest compatible pipe by Manhattan
distance, with reading order breaking ties. A visually nearby pipe is not
necessarily the selected pipe, and a busy intended pipe does not make the
instruction try another.

Physical validation must therefore compute the Voronoi owner of every pipe
instruction from the actual final attachment coordinates. Run this check after
every compaction or reroute. Moving a room by one cell can silently change the
program even when no pipes overlap.

For new builders, assign each functional pipe family a deliberate attachment
zone:

- input,
- display address/value/control,
- scalar-memory request/reply,
- cell-memory request/reply,
- queue/frontier transport.

Do not rely on a long pipe's visible route; binding distance is to its room
attachment.

## Memory: split by access pattern

The successful LLM program did not use one uniform 320-cell store. It used:

- a 64-slot scalar/state belt for frequently accessed metadata, and
- a 256-slot cell belt for the emulated grid.

This matters because a belt access costs distance. Put hot scalar state in a
small bank and large, colder indexed state in another. Keep a stable logical
address API so the layout can change without rewriting the algorithm.

For Snake:

- scalar bank: head, direction, fruit, alive/growing state, queue pointers;
- 256-cell bank: occupancy;
- FIFO: body positions.

For Pathfinder:

- scalar bank: robot, flag, queue pointers, current cell/direction;
- 256-cell bank: walls plus BFS distance/visited state;
- FIFO: BFS frontier.

If a cell needs both immutable and per-search data, either pack fields into one
integer or keep two banks. Epoch-tagged visitation can avoid clearing all 256
cells between searches, but only if the extra unpacking is cheaper than the
clear pass.

## Queue direction can remove an entire reversal phase

Choose the search direction to match output order.

For Pathfinder, BFS from the flag, not from the robot. Store a distance for
each reachable cell. Starting at the robot, choose the first neighbor in
`up, right, down, left` order whose distance is one less. This emits the
required shortest path directly and implements the stated tie-break without a
path stack or reverse pass.

The older `scratchpad/snake/build_snake*.py` experiments validate a useful
serpentine multi-lane FIFO/reversal pattern. They solve reverse-a-list rather
than the Snake problem, but demonstrate:

- right-aligned lane filling,
- FIFO behavior of ready incoming pipes,
- a count/barrier pipe,
- a compact two-column readout loop.

Prefer a true FIFO for a live Snake body and a Pathfinder frontier. Use the
multi-lane pattern only when a bounded materialized queue is cheaper than
indexed head/tail pointers.

## Emit display deltas, and understand round gating

The interpreter advances rounds based on committed frames. A round that
expects no frame (for example a Snake direction change) must unlock without a
display commit. The Rust interpreter was fixed to match this behavior; old
local results from before that fix are not trustworthy.

Avoid repainting 256 cells every frame:

- Snake setup: draw one green head cell and commit.
- Fruit: draw one red fruit cell and commit.
- Normal tick: clear the old tail, draw the new head, commit.
- Growth tick: clear the fruit by overwriting it with the green head, commit.
- Collision: do not move; recolor every occupied snake cell red, then commit.
- Pathfinder setup: paint walls and the robot once.
- Pathfinder move: clear the old robot cell, preserve the flag as needed, draw
  the new robot cell, and commit. The final cell overwrites the flag.

Because a display commit is the semantic boundary, ensure all writes belonging
to a frame have reached the display before the commit control value. Short,
dedicated display pipes are safer than sharing a long transport path.

## Route control flow as intervals, not as one highway per edge

The first general LLM placement gave every control-flow edge its own large
highway. It worked semantically but created enormous empty space. The useful
compaction sequence was:

1. Treat routed vertical spans as intervals.
2. Color non-overlapping intervals onto a shared lane.
3. Give branch arms distinct horizontal exit rows so they cannot collide.
4. If both arms have the same target, merge them before the long route.
5. Deduplicate identical branch targets in the compiler.
6. Tighten room gaps only after pipe-binding validation.

This reduced the official LLM score from roughly 74.06T to 49.84T and then
44.91T. The large blank regions in an early grid were routing lanes, not
required algorithmic space.

## A reliable validation ladder

Run the cheapest discriminator first:

1. Parse/render validation and collision checks.
2. Host reference-model tests, including edge cases.
3. Flow-level frame verification.
4. Pipe-binding/Voronoi verification.
5. One tiny Rust case with checkpoints.
6. Public Rust grading with parallel jobs and progress.
7. WASM confirmation when practical.
8. Submission and polling.

Stop on the first failed public case and investigate it immediately. A
twenty-minute full run that repeats the same early failure is wasted contest
time.

Useful adversarial shapes:

- minimum and maximum input sizes,
- empty or length-one state,
- repeated updates without a frame,
- movement into a just-vacated tail cell,
- wall/self collision,
- shortest-path ties at the first move and after a shared prefix,
- long narrow corridors and open rooms,
- repeated Pathfinder targets that require revisiting old cells,
- maximum public/private-style round counts.

## Optimize the measured bottleneck

The score is `max(width,height)^2 * average ticks`. After correctness:

1. Use `sim/xray.js` to identify the box-driving dimension and dominant case.
2. Use `sim/profile.js` to distinguish compute, turns, glides, and pipe stalls.
3. Fold the longer dimension toward a square before micro-optimizing.
4. Shorten frequently traversed loops and hot RAM/queue pipes.
5. Preserve the previous passing candidate before every transformation.

Large leaderboard scores are compatible with a 15M tick cap because footprint
is squared. Never infer the tick budget from the score alone.

## Checklist for Snake and Pathfinder

- Keep a host reference simulator beside each builder.
- Reuse `flowgrid.py` and the banked-memory interfaces, but specialize the
  physical layout to the much smaller state machines.
- Add queue helpers below the reusable-pattern marker rather than embedding a
  one-off queue in each builder.
- Validate every pipe instruction's owner after placement.
- Use delta display writes and exact frame-count assertions.
- Keep one-case Rust checkpoint commands in the builder's module docstring or
  a nearby README.
- Record local box/ticks and official score/case count in `tl` notes and the
  commit message.

