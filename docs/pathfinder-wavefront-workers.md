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

Setup also needs no scalar RAM.  `pathfinder_setup_row_packer.py` keeps the
remaining cell count in BP and one row accumulator in B.  For every setup bit
it performs `B = 2*B + (1-wall)`, emits one unsigned word after sixteen cells,
and immediately starts the next row.  Four adversarial rows pass in one run:

```text
pathfinder_setup_row_packer.py  35×20  714 ticks/row
```

Packing all sixteen OPEN words is therefore about 11.4k ticks.  The wall/open
branch can also send display colors 7/0 before it rejoins the accumulator path,
so initial painting does not require rereading the board.

`pathfinder_parent_service.py` is the correctness fallback for the other
missing interface.  It gives one canonical 64-word ring three data-driven
commands: update a layer, query selected bits, and reset every parent word.
The standalone service passes mixed update/query/reset sequences at 86×49.
It is not the final hot-path architecture because it serializes sixteen rows;
its protocol should be sharded into the sixteen four-word forked rings above.
Keeping the central version is still useful as an executable oracle and as a
submit-first fallback if the sharded assembly slips.

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

### Hierarchical SMT floor-planning

The closed core is also a useful boundary case for the repository's two SMT
placers.  Feeding all 162 rooms and 178 pipes to `smtplace.py` timed out before
finding a first model.  Locking each lane's ten rooms into a rigid group still
timed out: the implementation retains one coordinate pair per original room,
so grouping removes constraints but not enough symmetry.

Modeling the same machine hierarchically closes quickly.  The reusable
`pathfinder_bitplane_floorplan.json` treats each complete lane as one 9×120
component, plus the 149×16 controller and 19×7 counter.  With the semantically
fixed row order supplied as a symmetry breaker, `smt_layout.py` solves in 3.5
seconds and packs the rigid envelopes into 149×143.  The 151×149 implementation
is therefore width-limited by pipe realization, not component area.

The inner-room solver gives the complementary result.  On the controller,
`smtrows.py` reports 12 physical op rows as built, while its boustrophedon
model requires 67 rows at the existing width.  This controller is already
more tightly hand-folded than that model can express; applying the generic
row placer would be a regression.

Finally, the 149×143 rectangle solution is not itself a routable Littleman
artifact.  An attempted in-box counter reply removed x=149..150, but the
lane-15 trigger must first leave its room perpendicular to the wall.  Its only
free turn channel crosses the long reply channel, so the trigger vanished
from the parsed topology and the counter died on `r`.  The general workflow
is:

1. collapse repeated room clusters into architectural modules;
2. add semantic ordering constraints to break identical-module symmetry;
3. use coarse SMT only to establish an envelope target;
4. materialize pipes and re-parse topology before calling the target feasible;
5. run inner-placement SMT only on rooms whose layout belongs to its model.

In short, SMT is valuable here as a lower-bound and decomposition tool.  It is
not a replacement for the direction-aware pipe router or for deliberately
shared hand-folded controller rows.

### A three-way parent protocol without touching persistent state

`scratchpad/pathfinder_parent_query.py` proves a row-local reconstruction
service.  Four persistent B registers retain U/R/D/L words and accept:

```text
[positive, U, R, D, L, state]  update and forward
[negative, mask, mask, mask, mask]  query and return four hits
[0]  clear all four parent words
```

The useful trick is to make the command tag's sign be the entire dispatch.
At one `X`, positive turns into the update lap, negative into the query lap,
and zero continues through a short `0 M` reset chord.  No arithmetic is
performed on the tag, so persistent B is never borrowed or saved.

An earlier two-negative-mode design tried to distinguish -1 from -2 by adding
one before a second `X`.  Loading the literal destroyed A, and `+` combined it
with the persistent parent in B; the first query walked into a wall.  The
positive/negative/zero protocol removes that state-preservation problem
entirely.  The 58×18 four-room proof passes 23 deterministic and randomized
update/query/reset streams on the Rust interpreter.

`scratchpad/pathfinder_closed_query_wavefront.py` composes those services with
the complete fixed-64-layer kernel.  The correctness-first build uses a
13-column lane pitch and measures 218×188.  Both a dense asymmetric seed and a
sparse three-source seed finish all 64 layers with every U/R/L/D parent word
matching the Python reference.

Two ownership bugs appeared only after composition:

- Widening pitch 9→13 moved the D-append send from 4-vs-5 cells (previous
  packet wins) to 8-vs-5 (current packet wins).  Moving the send into the
  inter-lane gap restores a strict 6-vs-7 previous-packet win.
- Adding NEXT's leading mode-drop shifted the lowercase state send around its
  perimeter.  On row 15 it became one cell nearer the layer-trigger pipe than
  the ordinary return, so the counter advanced on state and the controller
  deadlocked waiting for the missing second return word.  Moving the ordinary
  return attachment beside the state send restores unambiguous ownership.

The dense seed hid the second bug for many layers; the sparse seed deadlocked
on layer three.  Always include a sparse wavefront when changing port pitch or
adding even one operation before a multi-pipe send.

### Persistent OPEN words without scalar RAM

`scratchpad/pathfinder_seed_store.py` closes the setup/round boundary for one
row.  One B register retains the immutable 16-bit OPEN mask and a sign-tagged
input stream selects all later behavior:

```text
[0, open]             setup: B := open
[-1, flag]            seed:  emit [open XOR flag, flag]
[1, state, frontier]  return: emit [state, frontier]
```

The negative branch uses two XORs around the first send.  With `A=flag` and
`B=OPEN`, the first `~` emits initial state and the second recovers the flag;
B is never modified.  The positive branch relays the two NEXT words, and the
zero branch is the only path containing `M`.  The Rust probe covers repeated
seeds, BFS returns, and re-setup in one run: 138 ticks, 22×18.

This means full-round integration does not need a 256-cell RAM or even a
mutable bitplane reset.  Setup packs sixteen canonical OPEN words once; every
round injects sixteen flag masks (fifteen zero, one selected column bit), and
the existing feedback loop supplies all later state/frontier pairs.

### Compact query kernel and its SMT floor

The first queryable composition was 218×188 because every row used the
spacious 10×18 proof service and the controller injected a positive mode
token between adjacent lanes.  SMT showed this was not a floorplanning
problem: nearest-port bands forced a 212-cell controller interior, hence a
216-cell overall width.  The hierarchical model could only repack it to
216×181, and inner-room SMT could only suggest 218→216.

Two local rewrites remove that width:

1. `pathfinder_parent_query_compact.py` drops the redundant literal zero on
   the reset path (`X` already guarantees A=0) and folds the service to 9×14.
   Its 22 deterministic/random streams all pass.
2. The D priority stage uses its two previously empty perimeter slots for
   `1,s`, producing `[1,U,R,L,D,state]` itself.  Controller-side mode
   injection disappears completely.

The resulting `pathfinder_closed_query_wavefront.py` compact build is
167×172 and passes both dense and sparse 64-layer parent-state comparisons.
Three composition traps were caught:

- a first pipe segment collapsed horizontally and created an orphan endpoint
  accepted by Rust but rejected by the oracle topology parser;
- the next lane's return highway overwrote the previous parent room's corner;
- at `tile0=2`, lane zero's compact D column landed on controller return
  column x=1, so every later lap skipped its two seed receives.

The shutdown gate also needs a real drain.  Lane 15 completing layer 64 does
not imply every earlier lane has retired its last packet.  The controller now
walks the otherwise empty bottom row, consuming final return pairs before H;
lane zero receives one extra pair drain for the measured two-packet skew.

SMT on the corrected artifact gives:

```text
exact rooms:       area lower bound side 143; no model before timeout
hierarchical:      167×172 implementation -> 164×165 rigid envelope
inner controller:  12 physical op rows as built; model needs 68
```

Thus only about 8% box remains in coarse floorplanning.  Applying `smtrows`
would regress the grid to 167×226.  The credible large win is completing the
round/setup/query/display shell around this low-tick kernel, then realizing
the 164×165 envelope; it is not further generic controller repacking.

### Query/reset demux and the tick target

The old NEXT room understood only positive BFS packets.  A reset token would
fall into the four-word reducer and permanently desynchronize the lane, while
a negative parent query reply had no route to reconstruction.  The compact
`pathfinder_next_demux.py` service closes that protocol:

```text
positive [1,U,R,L,D,state]  -> [next_state,next_frontier]
negative [-1,hU,hR,hL,hD]  -> reconstruction output unchanged
zero     [0]                -> consumed
```

The 9×21 fold uses height rather than lane pitch for the nineteen-operation
positive lap.  Its mixed update/query/reset trace passes both Rust and the
organizer WASM (272 ticks in the standalone two-output probe).  Folded into
all sixteen lanes, the closed kernel is 167×194 and still reproduces both
dense and sparse parent states.  The organizer loads and executes 100,000
ticks of the composition without error.

The feature is almost free in time despite the extra height.  At tick 80,000,
the old 167×172 kernel has three of 64 layers left and the demux kernel has
four.  Profile counts explain the difference: the new path adds one `X` per
row packet (1,040 total in the probe) and 7,200 blank steps, roughly seven
extra walking cells per packet.  It does **not** add a pipe-latency stall.

The dominant tick mistake is now the fixed 64-layer gate.  Public Pathfinder
rounds have shortest-path lengths:

```text
count 24, mean 15.83, min 1, max 49
```

Stopping when the reverse wavefront first contains the robot therefore has a
public-case ceiling near `64 / 15.83 = 4.04x`, before any walking improvement.
This is more valuable than shaving the demux lap or its 22 rows.

`scratchpad/pathfinder_target_hit.py` proves the persistent primitive
independently on both engines.  Its 9×10 B register accepts target replacement,
frontier test, and clear packets; the mixed trace takes 113 ticks.  Sixteen
copies would work, but a cheaper composition uses the canonical-order rule:

1. Keep the sixteen target row masks in one FIFO ring.
2. Use one currently blank controller glide cell per lane to send that lane's
   frontier to a shared hit worker.
3. Give the worker sixteen equal-length vertical input pipes.  Controller
   sends are serial and about 48 ticks apart, while the worker cycle is under
   ten cells, so only one input can be ready and `R` preserves row order.
4. The hot worker loop is `R M r s & X`: receive frontier, receive and return
   the next mask, test, and signal only on a non-zero hit.

This retains the controller's cross-row B state and adds essentially one real
operation per row.  A completion token may arrive mid-sweep, so stopping
immediately is unsafe: latch it until lane 15 retires, then use the existing
final-pair drain before parent queries and reconstruction.

After early termination, the remaining throughput limiter is the shared
controller sweep, about 1,250–1,300 ticks per layer.  A credible second
architecture replaces it with sixteen row-local assemblers: each returned
frontier is broadcast by `S` to its own R/L calculator and its two neighbours,
and all rows form `[state,U,R,L,D]` concurrently.  This removes the serial
serpentine without speculative prefetch or random-access RAM.  It needs a
measured gadget before integration; merely forking the current controller
does not work because its B register carries the previous row frontier across
the split boundary.

The measured gadgets now support that replacement:

- `pathfinder_row_assembler.py` is the tight arithmetic loop.  Four complete
  packets take 88 ticks on both engines: **22 ticks/row/layer**.
- `pathfinder_row_assembler_ports.py` proves five independent nearest-input
  bindings (state, U, self-R, self-L, D) and the exact output packet on both
  engines.  Its intentionally spacious binding rig settles in 51 ticks.
- The broadcaster is the already-proven `@rS` relay: one received frontier is
  delivered atomically to the two neighbours and two self inputs.

This matches the profile that localized 78.1% of all stall to the sixteen lane
receive cells: the workers were 99.5% idle, so optimizing their arithmetic
cannot matter.  Replacing the serial feed changes the expected layer issue
interval from roughly 1,250 ticks to the 22–34 tick assembler/broadcast lap;
the priority/parent stages then become the next measured bottleneck.
