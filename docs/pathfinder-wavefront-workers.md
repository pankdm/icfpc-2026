# Pathfinder wavefront worker backend

`solutions/pathfinder/verify_wavefront.py` proves the algorithm and tie order.
This document fixes the physical protocol for the RAM-free backend.

The core update has an executable oracle-sized proof in
`scratchpad/pathfinder_wave_workers.py`. It covers arbitrary signed i64 words,
overlapping U/R/D/L candidates, strict priority subtraction, broadcast to two
consumers, and the four-input NEXT OR barrier.

## Persistent state

There are four 64-bit lanes. Each lane owns eight persistent B-register workers:

- `OPEN`: immutable walkable cells for round reset;
- `UNVIS`: cells not reached in the current round;
- `FRONT`: current frontier;
- `NEXT`: next-frontier OR accumulator;
- `PU`, `PR`, `PD`, `PL`: cells whose chosen predecessor is U/R/D/L.

The 32 workers hold every BFS bitset directly. No encoded RAM may sit on this
path: `split_ram` assumes Memory-range values and routes arbitrary signed i64
bitsets into its sign-based command control.

## Layer protocol

`FRONT[i]` broadcasts its word once. Dedicated candidate workers compute:

```text
U[i] = (F[i] << 16) | (i ? F[i-1] >> 48 : 0)
R[i] = (F[i] >> 1) & ~COL15
D[i] = (F[i] >> 16) | (i<3 ? (F[i+1] & 0xffff) << 48 : 0)
L[i] = (F[i] << 1) & ~COL0
```

Each lane's `UNVIS` worker visits four distinct receive cells in strict U/R/D/L
order. For each candidate `C`, with `B=unvisited`:

```text
r &             A=take=C&B, B=old_unvisited
s_parent        send take to this direction's parent worker
s_next          send take to NEXT
W ~ W           B=old_unvisited XOR take, A=take
```

The XOR is subtraction because `take` is a subset of `unvisited`.

Each parent worker loops:

```text
r | M           B := B OR take
```

NEXT consumes four takes:

```text
r | M           repeated four times
s 0 M           send completed frontier to FRONT; clear accumulator
```

FRONT stores the word in B and broadcasts it to the candidate network. A
fourth short output goes to the robot-bit termination test.

## Synchronization

- Candidate pipes are separate; UNVIS uses nearest `r`, never `R`.
- Their receive cells appear physically in U/R/D/L order, so faster candidates
  cannot overtake a blocked earlier direction.
- NEXT receives exactly four values per layer. It is the lane barrier.
- The four completed NEXT words join through a four-input barrier before the
  next layer begins.
- Every pipe in the layer cycle must have fixed capacity; shortening is allowed
  only after the protocol passes adversarial idle and dense-layer tests.

## Round reset

OPEN sends its word to UNVIS. Parent workers receive zero. FRONT receives the
one-hot flag word (zero in the other lanes). Reset completes through the same
four-lane barrier before the first broadcast.

## Reconstruction

For the current robot index, a small selector requests the corresponding lane
and bit from PU/PR/PD/PL in U/R/D/L order. The first matching mask determines
the move. Only two display pixels and one SWAP are emitted per step.

## Budget

The worker core is 32 state workers plus roughly 16 candidate workers and four
barrier/selector workers. At 6x4–8x5 per small room, a square-packed core should
fit inside roughly 80–110 cells per side including the display and pipes.

A layer should cost tens, not thousands, of ticks: the critical UNVIS loop is
four seven-op updates plus short pipe latency. Even a conservative 100
ticks/layer and 100 layers/round leaves large headroom versus the current
~4,853 ticks per popped cell.
