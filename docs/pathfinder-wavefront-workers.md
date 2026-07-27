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

The notation above uses logical right shifts. Littleman's `}` is arithmetic:
the physical U cross-word contribution must mask to 16 bits, and the local D
contribution must mask to 48 bits. `scratchpad/pathfinder_candidate_workers.py`
exercises the former with negative words; omitting the mask turns `-1 >> 48`
into `-1` instead of `65535`.

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

`scratchpad/pathfinder_lane_ports.py` proves the receive geometry. A single
UNVIS man walks across five physically separated ports (reset, U, R, D, L);
repeating `r` at one coordinate is invalid because lowercase reads stay locked
to the nearest pipe even after that pipe becomes empty. The probe also exposed
a fanout rule for setup/controller streams: every branch must drain every
broadcast token, even if it discards most of them, or a short unused branch
fills and backpressures the broadcaster.

An alternative, more modular topology is proven by
`scratchpad/pathfinder_stage_ring.py`: the shrinking UNVIS word travels through
four U→R→D→L rooms. Each stage accepts its direction's candidate, emits the
accepted subset, and forwards the reduced word. This gives every direction its
own output namespace and avoids lowercase-read multiplexing entirely. The
unfolded proof is 104×28 and reaches correct UNVIS/NEXT state in 88 ticks; it
should be folded 2×2 for the real four-lane floorplan.

The probe now runs persistently for consecutive layers. NEXT must visit its
four direction pipes in order: an earlier `R`-based any-ready loop mixed a late
take from one layer with an early take from the next. With ordered sites, two
different adversarial layers pass; the unfolded layout produces the first
result at tick 133 and the second at tick 303 (170-tick issue interval). Most
of that interval is the deliberately long return corridor, so folding is also
a latency optimization.

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

## Score-informed alternative: sixteen unsigned row strips

The four-word design pays real physical complexity for signed cross-word
shifts.  A sixteen-lane design stores one unsigned 16-bit word per board row:

- U and D candidates are direct broadcasts from the adjacent row;
- R and L are one-cell shifts of the local word;
- overflow is harmless because the problem guarantees a wall border;
- all values stay in `0..65535`, so arithmetic right-shift sign extension
  disappears.

Arrange the sixteen rows as narrow vertical strips, not sixteen square tiles.
Each strip stacks OPEN, FRONT, the U/R/D/L priority stages, NEXT, and the
parent-ring processor.  U/D pipes then run only to the adjacent strip.
A strip pitch near nine cells gives a natural width near 144 cells before
edge services.

That number is independently interesting because three leading Pathfinder
scores admit this coherent 18-case decomposition:

```text
141² × 160,382.667 = 3,188,567,796
154² × 160,078.167 ≈ 3,796,413,801
138² × 214,044.222 = 4,076,258,168
```

The first two have nearly identical ticks but a 19.3% box difference.  This is
not proof of their dimensions, but it is consistent with related lane
architectures separated mainly by strip pitch and routing.

The final-board leader later moved to `2,535,477,804.67`.  Of the plausible
integer sides, 146 gives an essentially exact 18-case decomposition:

```text
146² × 118,947.1667 = 2,535,477,804.67
18-case tick sum = 2,141,049
```

That still is not proof of its box, but the integer tick sum and the independent
146-column fork-hall construction make it the strongest working target.  By
comparison, the live per-cell build is 151×174 at 768,688 server ticks.  Even
perfectly folding it to 152 square and removing every controller glide has only
about a `1.31× × 1.7×` optimistic ceiling, far short of the `9.18×` score gap.
Reflow is useful for rank, but reaching the leader requires the row-bitplane
backend.

### Delete four parent accumulators per row

Parent words are updated once per layer and queried once per path step in the
same U/R/D/L order.  They therefore belong in one canonical four-word ring per
row, not four separately routed accumulator rooms.

The priority stages produce TAKE values sequentially.  A row-local collector
can:

1. receive TAKE in U/R/D/L order;
2. OR it into NEXT;
3. forward it to one parent-ring processor;
4. after four values, send the completed NEXT word to FRONT.

The processor rotates the matching parent word, ORs TAKE, and returns it to
the ring.  During reconstruction it rotates the same four words, returns each
unchanged, and tests it against the selected robot bit.  This is the
Pathfinder analogue of Snake's scratch-ring deletion: canonical order removes
four rooms and several broadcast pipe pairs without serializing unrelated
rows.

The remaining synchronization rule is strict: FRONT may announce a row ready
only after both its NEXT word and that row's four parent updates have
completed.  A global ready barrier may then release all FRONT words together;
otherwise adjacent U/D rows can mix consecutive BFS layers.

### Physical closure of the nine-column strip

The score-informed strip is no longer only a budget.  Three Rust-interpreter
probes close its critical geometry:

```text
pathfinder_row_tile.py       109×64  two persistent layers, full state protocol
pathfinder_stage_band.py     144×16  16 distinct lanes at pitch 9
pathfinder_serial_bands.py   143×53  U/R/D/L priority bands and stream order
```

The first probe joins circulating UNVIS, ordered TAKE, NEXT, and the
four-word parent ring.  The second proves that sixteen adjacent nine-wide
rooms bind distinct state/candidate/output pipes correctly.  An attempted
shared room was load-invalid because a room may contain only one initial `@`;
using a shared hall would require a runtime `Y` splitter.

That shared-hall requirement is now closed.  The zero-cost fork work exposed
a useful Pathfinder-specific floor-plan primitive:
`scratchpad/pathfinder_fork_relay_hall.py` uses one initial man and a diagonal
`Y` runway to create sixteen permanent, column-aligned `r -> s` relays in one
room.  Every north copy continues to the next fork one row higher; every south
copy falls into an independent eight-tick relay lap.  Sixteen round-trip
testers prove strict nearest-port ownership in the Rust interpreter:

```text
pathfinder_fork_relay_hall.py   146×37  16/16 shared-room relays
```

The relay hall itself is 146×25; the remaining twelve rows are test fixtures.
This removes the one-`@` reason for sixteen parent-ring relay rooms while
preserving the nine-column row pitch.  It does not remove the BFS layer
dependency, and it should not introduce a central ring: the intended use is
one row-local four-word ring per relay, all sixteen updating concurrently.
The other promising Pathfinder fork is the independently addressable setup
stream (OPEN packing and initial display painting), where producer and
consumer can run ahead without the pointer-chase failure that killed the LLM
experiment.

The diagonal runway is useful but not height-optimal.  A binary fork tree
splits disjoint horizontal intervals on four consecutive rows:

```text
pathfinder_fork_tree_relay_hall.py  146×18  16/16 relays
                                         146×8   core hall
pathfinder_fork_parent_rings.py     146×44  16 concurrent U/R/D/L rings
```

At each level, a south-facing `Y` sends children west and east to the centres
of the two half-intervals; each child turns south and splits again on the next
row.  The leaf relay laps are mirrored to preserve their arrival directions.
This is a general floor-plan result: a linear `Y` runway costs one row per
worker, while a non-crossing binary fork tree costs one row per doubling.

The parent-ring proof broadcasts two four-HIT layers and a zero-query rotation
to all sixteen row updaters.  Every ring finishes in canonical U/R/D/L order
with `[17,34,68,136]`.  Thus four parent bands can be replaced by one updater
band plus the eight-row shared hall without serializing unrelated rows.  In
the solver, the updater's completed send should also be broadcast as an ACK;
NEXT must drain four ACKs before releasing the next row pair so parent updates
cannot lag into the following layer.

The third probe deletes the separate TAKE pipes.  Each stage forwards the
earlier TAKE prefix, applies its candidate, and appends its own TAKE plus the
reduced state:

```text
U: [U, state]
R: [U, R, state]
D: [U, R, D, state]
L: [U, R, D, L, state]
```

One pipe pair per row now carries both UNVIS and all four priority results.
The first version used eight-wide rooms on a nine-column pitch and occupied
143×53.  Closing the state loop exposed a constraint the open band did not:
one blank column between rooms cannot contain a legal horizontal pipe, because
a pipe must have at least two cells.  Narrowing every room to seven columns
and adding one perimeter row where necessary preserves the nine-column pitch
while leaving two routing columns.  The persistent Rust probe
`pathfinder_cyclic_bands.py` now runs all sixteen lanes indefinitely at
143×82; first-layer parent bits persist after many later zero layers.

The canonical stream also admits a stronger next step.  Candidate values do
not need separate vertical pipes.  A packet can enter the priority stack as
`[state,U,R,D,L]`; each stage consumes its adjacent state/candidate pair and
emits `[earlier TAKEs, reduced state, later candidates]`.  L therefore still
finishes with `[U,R,D,L,state]`.  A single top or bottom driver can construct
the next packet from the sixteen returned frontier/state pairs.

There is a register-cheap streaming construction for that driver.  Process
rows left-to-right with each return pipe ordered `[state,frontier]`.  At row
`i`, emit state and the U/R/L prefix for packet `i`; when row `i+1` is read,
append its frontier as D to packet `i`.  Put packet `i`'s port at the boundary
between the two row columns, so both send sites bind the same pipe.  This
avoids a 16-word frontier RAM and turns the global barrier into the driver's
natural sweep.  The remaining build risk is physical placement of the
two-sided send sites, not the BFS algorithm.

That risk is now closed by two more Rust probes:

```text
pathfinder_stream_driver.py   149×32  exact [state,U,R,L,D] packets
pathfinder_packet_stages.py   149×88  driver plus four priority bands
```

The controller uses a nine-column meander per row.  State and U/R/L sends are
physically closest to the current packet pipe; the current frontier's D send
is closest to the previous packet pipe.  To retain the frontier with only A
and B after computing both shifts, it reconstructs the original from the
right-shift quotient and remainder: `frontier = 2*q + remainder`.

All four priority rooms are now identical 7×9 blocks with fifteen operations.
Their packet sequence is:

```text
[state,U,R,L,D]
[U,state,R,L,D]
[U,R,state,L,D]
[U,R,L,state,D]
[U,R,L,D,state]
```

The composed probe matches a Python reference in every lane, including both
zero borders.  The remaining solver work is to replace the final passive
sinks with persistent UNVIS/parent/NEXT state and feed `[state,frontier]`
back to the driver.

That feedback loop is now physically closed in
`pathfinder_closed_wavefront.py`: 149×110 for sixteen rows, including seed/
return merges, the streaming driver, all four packet stages, persistent
parent summaries, NEXT, and the return pipes.  Four distinct seed patterns
match the bitplane reference after 5,000 Rust ticks.

The multi-seed check caught a subtle row-wrap bug that the symmetric first
seed hid.  After appending the zero D boundary for row 15, the controller must
also reset B to zero before its next lap; otherwise row 15's frontier becomes
row 0's U candidate on every layer after the first.  The reset is one `M`
placed on the driver's existing return corridor.  This is another reason to
validate stateful gadgets across multiple layers rather than only checking a
single packet.

The architectural unknowns are now outside the BFS core:

1. construct the sixteen OPEN words and goal frontier from the input raster;
2. expose the stored parent words to reconstruction;
3. stop on target discovery and run parent-guided reconstruction;
4. connect the existing display/output protocol.

The parent-summary placeholder has been removed.  Four serial 7×8 accumulator
bands per row now store the complete U/R/L/D parent planes.  Each band forwards
the five-word stream unchanged and ORs only its own TAKE into persistent B.
This expands the closed core from 149×110 to 149×140, which is still the same
149² scoring box.  All four direction planes match the reference across the
four asymmetric multi-layer seeds.

This is an important layout rule in its own right: when width already drives
the square, spend unused height on the simplest correct state representation.
The four accumulator bands use 64 men instead of sixteen elegant four-word
rings, but they currently cost zero score and make reconstruction state
explicit.  Compress them only after setup/display pushes height beyond 149.

### Setup packing and a bounded completion gate

`scratchpad/pathfinder_setup_packer.py` converts the 256 setup wall tokens
into the same sixteen unsigned OPEN words used by the strip core.  The hot
loop needs no scratch ring.  With the current row accumulator in B and the
input wall bit in A, it evaluates:

```text
r - N + W 1 + M
```

which is `2*acc + (1-wall)`.  A separate BP=16 acknowledger returns 1 after
rows 0..14 and 0 after row 15, so the packer changes to coordinate mode before
it can consume `rx ry` as a seventeenth row.  The 56×38 probe passes all-open,
all-wall, alternating, and twenty deterministic random boards.

The assignment guarantees every shortest path is at most 64 moves.  The first
complete backend can therefore run exactly 64 wavefront layers instead of
routing sixteen activity taps through an already full strip.  Row 15 NEXT
broadcasts its completed frontier to both the ordinary return pipe and a
BP=64 countdown worker.  That worker replies only after the last row has
actually completed, preserving the global barrier; replies 1..1,0 run exactly
64 layers and then enter reconstruction.

The resulting bounded probe is 151×149 and passes four asymmetric 64-layer
Rust tests with all 64 parent words intact.  The two-cell width increase is
the outside reply pipe, not computation, and should be reclaimed when setup,
display, and reconstruction receive their final shared floorplan.

One failed floorplan is worth recording.  Putting a 149-wide activity room
immediately below NEXT made the existing y=139 return highway run one cell
outside that room's top wall.  The loader consequently claimed those return
pipes as ports of the new room.  A visually blank separator row is not always
optional: a pipe parallel to a wall at distance one attaches to that room.
Inspect source/destination room IDs after adding any room beside an existing
highway, not only after moving the highway itself.

This is direct physical evidence for the large-factor interpretation of the
competitor scores, rather than proof that the competitors use the same
design.
