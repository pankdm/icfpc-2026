# Snake Y-worker architecture

The generic stateflow Snake is correct but architecturally far from the
leader: the official gap is roughly 18.4B versus 55.8M.  Coarse packing cannot
close that gap.  The replacement design uses `Y` to turn Littleman creation
order into a small parallel occupancy memory.

## Proven component

`scratchpad/snake_y_workers.py` builds a 16-worker farm:

1. One master forks exactly 16 clones at the same `Y`.
2. Clone `i` inherits `A=i`, copies it to `BP`, and traverses a four-bit
   H-tree into one leaf of a 4x4 grid.
3. Each leaf owns a distinct `r` cell but all 16 cells bind to the same input
   pipe.
4. Once every clone is blocked, a dense 16-word batch is delivered in
   creation order: word `i` is consumed by worker `i`.
5. Worker `i` stores a 16-bit occupancy mask in `B`, representing board cells
   `16*i .. 16*i+15`.

Worker commands are:

- `0`: no-op;
- positive mask: query, sending `1` iff `B & mask != 0`;
- negative mask: toggle the selected bit.

The oracle probe toggles bit 2 in worker 3, then queries it.  It emits `1` and
settles at tick 506.  `pipecheck` reports one unambiguous incoming and outgoing
pipe for all 32 worker `r`/`s` cells.

The long serpentine input pipe is only a probe barrier and is not part of the
intended Snake floorplan.  The integrated controller must emit a dense batch
with one `s` per tick after worker initialization.

## Snake integration

Keep the body order in a bounded FIFO pipe and use the worker farm only for
occupancy:

- split cell index with `/16`: quotient selects a worker, remainder selects a
  bit;
- build `mask = 1 << remainder`;
- emit 16 commands, placing the nonzero command at the quotient;
- ordinary tick: pop tail, toggle tail bit, query new-head bit, toggle new-head
  bit, then append new head;
- growth: query and toggle new head without popping the FIFO;
- collision: do not append; recolor the popped tail (if any) plus the FIFO
  contents red, then commit.

Head, direction, and fruit need only one-value loopbacks.  Display output is
delta-only as in the current solver.

The batch emitter should be unrolled or otherwise sustain one send per tick.
A relay loop with a long walk is invalid: the oldest worker returns before the
batch finishes and consumes later addresses again.

## Packing model

Treat the following as SMT components after the integrated logic passes:

- 4x4 Y-worker farm with typed dispatch/response pins;
- controller;
- body FIFO, with minimum capacity 50 (100-round bound);
- head/direction/fruit loopbacks;
- 18x18 display with typed top/left/bottom pins;
- input room.

The current 85x95 probe is deliberately loose.  Its H-tree spacings and worker
tile pitch are tunable; exact routing and collision checks, not rectangle
non-overlap alone, must accept the final placement.
