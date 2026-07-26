# History Lesson — ring dictionary build

`best/81x81.man` is the checked-in champion.  It has an **81×81** non-space
footprint, so its footprint-only score is **6,561**.  The default builder
invocation reproduces it; `--legacy 82` and `--narrow` still reproduce the
previous champion and the constant-tail candidate byte-for-byte.

| Candidate | Footprint | Score |
| --- | ---: | ---: |
| `best/81x81.man` | 81×81 | **6,561** |
| `best/82x82.man` | 82×82 | 6,724 |
| `candidates/81x82.man` | 81×82 | 6,724 |
| `history-ring-p1west-82x80.man` | 82×80 | 6,724 |
| `history-ring.man` | 83×83 | 6,889 |
| `history-lesson-with-year.man` | 84×84 | 7,056 |
| `history-lesson-v3.man` / `v4.man` | 85×85 / 85×84 | 7,225 |
| `history-lesson-v2.man` | 86×86 | 7,396 |

The program has no input.  It emits the byte sequence in
`icfp-history.txt`; consequently a slow, small decoder is the right tradeoff.
The organizer WASM passes the sole public case in 208,863 ticks (214,833 before
the dispatcher rebuild below), but ticks do not affect this problem's score.

## Encoding

`build_ring.py` is the source of truth for `best/81x81.man`.  It transforms the
target text into a compact stream with these base-92 symbols:

| Symbol | Meaning |
| --- | --- |
| `0` | Emit the next `; YYYY: ` prefix (2000 through 2026). |
| `1..16` | A short dictionary entry; `13` means `, `. |
| Unescaped `17..91` (except `29`) | Ordinary ASCII stored as `symbol + 31`. |
| `29, k` | Escape pair selecting ring position `k` for a longer phrase. |

The encoder greedily replaces recurring phrases when the saved feeder space is
larger than the decimal literal needed to preload the phrase.  Dictionary
values are raw ASCII packed little-endian in base 128; a phrase is at most nine
bytes so it fits in a signed 64-bit literal.  The final base-92 symbol stream is
packed little-endian into as many literals as each feeder slot can hold.

### Current dictionary and symbol fill

This is the exact generated table for the checked-in `history-ring.man`.
`␠` denotes an ASCII space.  Positions 1–16 are direct symbols; positions
17–35 are reached only by an escape pair (`29, position`).  The two count
columns show how many times the corresponding reference appears in the final
2,042-symbol stream.

| Position | Expansion | Direct | Escape target |
| ---: | --- | ---: | ---: |
| 1 | `␠` | 181 | — |
| 2 | `and␠` | 21 | — |
| 3 | `"` | 17 | — |
| 4 | `"␠(` | 20 | — |
| 5 | `on` | 37 | — |
| 6 | `an` | 37 | — |
| 7 | `or` | 32 | — |
| 8 | `er` | 31 | — |
| 9 | `(` | 1 | — |
| 10 | `)` | 14 | — |
| 11 | `,␠USA` | 11 | — |
| 12 | `in` | 29 | — |
| 13 | `,␠` | 64 | — |
| 14 | `-` | 9 | — |
| 15 | `.` | 5 | — |
| 16 | `en` | 24 | — |
| 17 | `ed␠` | — | 5 |
| 18 | `burg` | — | 4 |
| 19 | `␠Peyt` | — | 5 |
| 20 | `bstract` | — | 3 |
| 21 | `␠program` | — | 2 |
| 22 | `Dimitrio` | — | 2 |
| 23 | `o␠Russo` | — | 2 |
| 24 | `␠type` | — | 3 |
| 25 | `Sim` | — | 7 |
| 26 | `'` | — | 1 |
| 27 | `0` | — | — |
| 28 | `cti` | — | 6 |
| 29 | `␠the␠` | — | 3 |
| 30 | `David␠` | — | 3 |
| 31 | `(virtual` | — | 2 |
| 32 | `Haskell` | — | 4 |
| 33 | `);␠199` | — | 3 |
| 34 | `ada␠"` | — | 3 |
| 35 | `es)` | — | 6 |

The rest of the stream is filled as follows:

| Symbol form | Count | Meaning |
| --- | ---: | --- |
| `0` | 27 | Stateful YEAR marker: emit the next `; YYYY: ` prefix. |
| Direct dictionary symbols `1..16` | 533 | Expanded through the first 16 rows above. |
| Escape controls `29` | 64 | Consume the following symbol as a dictionary position 17–35. |
| Escape target symbols | 64 | The second half of those escape pairs. |
| Raw shifted ASCII | 1,354 | Any other unescaped symbol is decoded as `symbol + 31`. |

`29` occurs 67 times in the raw physical stream: 64 times as the escape
control and three times as the target selecting dictionary position 29.  The
table is generated from `build_ring.py`; regenerate it if the input text or
phrase-selection rules change.

Two details are intentional rather than cosmetic:

- A zero never terminates a base-92 literal: the repeated division decoder
  cannot recover a most-significant zero.
- Feeder rows alternate direction.  The westbound decimal spelling is reversed
  so that Littleman's direction-sensitive backtick literals retain the same
  numeric value.

## The 81x81 tail (`west_first`)

Two independent lines of work reached width 81.  `--narrow` keeps the 10-row
P1 and buys its feeder rows with three extra dictionary entries carried in the
pump rows; it lands at 81×82.  The champion instead takes three folds that
together remove a row from each of the feeder, P1, and the ring's column
budget, landing at 81×81.  The two are alternatives, not composable: the
margin pump needs the very rows the constant tail uses.

- **An odd feeder.**  The feeder is walked in two-row bands because both rows
  of a band must put their backticks in the same columns.  The *last* band may
  be a single eastbound row: the oracle only constrains what sits between two
  backticks in a column, so a lone trailing tick merely opens a literal that
  is never closed, and earlier bands are unaffected because the odd row is
  last.  `optimize_feeder` now scores rows rather than bands.  At width 81 the
  baseline stream needs 64 rows in whole bands but only 63 with a half band.
- **The pump in P1's margin.**  Walking P1 west-first makes its last data row
  end on the right, so the pump becomes a six-cell loop in the two columns
  between the turn column and the right wall instead of two rows of its own.
  P1 goes from 10 rows to 8.
- **A rebuilt DISP and a shifted band.**  With every service room slid one
  column left, a narrower dispatcher widens the strip east of DISP to the
  columns the ring's 35 cells need, while still leaving DISP → YEAR a
  two-column gap — a one-cell pipe is rejected by the loader, verified directly
  against the oracle.  Each room keeps its position *relative* to its own
  attachments, so DISP's nearest-pipe bindings survive the slide.  This was
  originally a 26-column trim of the 6-row grid (its last inner column is
  entirely blank); DISP is now the 23×7 `DISP_COMPACT_ROWS` build described
  under [the dispatcher rebuild](#the-dispatcher-rebuild) below.

That is 65 feeder rows + 8 service + 8 P1 = 81, with the ring at 26+13 = 39
cells against a 35-word floor.  Note the service band is 8 rows because UNPACK
and DECODER *stack* to 8, not because of DISP: shrinking DISP to 7 rows leaves
row 72 free but does not shorten the program.

Measured dead ends, recorded so they are not retried:

- Rooms may not share a wall row; a two-room probe crashes with reason
  `wall`.
- Dropping the YEAR room costs more than it saves.  The `; YYYY: ` prefixes go
  from 27 single symbols to inline text: 2,042 → 2,140 symbols, and the feeder
  at width 81 goes 64 → 66 rows.  It frees 29 *columns* but no rows, because
  DISP, not YEAR, sets the service band's height.
- Re-selecting phrases for symbol count rather than grid cells is worse
  (2,035–2,061 vs 2,042) once P1's width cap is enforced.  2,010 symbols would
  buy 62 feeder rows; the constrained search plateaus well above that, which
  is what `--narrow` sidesteps by adding entries instead.

## Runtime pipeline

```text
serpentine feeder
  decimal literals (base-92 bundles)
      │
      ▼
DECODER ── repeated divmod 92 ──► DISP ──► YEAR ──► UNPACK ──► output
                                      │               divmod 128
                                      └── P1 dictionary ring ──┘
```

1. **Feeder** walks its rectangular literal grid once and sends packed base-92
   chunks to `DECODER`.
2. **DECODER** repeatedly divides each chunk by 92, producing least-significant
   symbols first, which is the original stream order.
3. **DISP** classifies a symbol.  Ordinary values get `+31`; zero goes to
   `YEAR`; references select a packed dictionary value from P1.
4. **P1 and the ring** start by serially preloading every packed dictionary
   entry and a final `-1` sentinel into a loop pipe.  For a lookup, DISP rotates
   values through the loop until the requested position, forwards that value,
   then continues through the sentinel.  This restores the original order, so
   every lookup uses stable positions without RAM.
5. **YEAR** emits a packed `; YYYY: ` value for each zero marker.  It starts at
   2000, adds a five-byte base-128 increment each time, and applies a correction
   after each decimal carry decade.
6. **UNPACK** repeatedly divides every packed value by 128.  Its remainders are
   the raw ASCII bytes sent to the output room.

The physical layout uses 62 feeder rows plus its two borders, puts all five
service rooms directly beneath the feeder, and places P1 in the final ten
rows.  Two slim vertical pipes at the right close the P1/DISP loop.  The
layout is square on purpose: the problem scores only `max(width, height)^2`.

## Pipe-length requirements

A Littleman pipe of `L` cells is both an `L`-word FIFO and a transport with
`L-1` ticks of latency.  Every pipe must contain at least two cells.  Longer
pipes can delay values and absorb more back-pressure; they do not change FIFO
order.

There are two different kinds of pipe in this program:

- The five ordinary pipeline links are blocking streaming connections.  Their
  producers safely park on `s` when a pipe is full, and their consumers safely
  park on `r` when it is empty.  Consequently they have no
  correctness-required capacity beyond the language minimum: each may be
  shortened to **two cells** if the rooms can be placed and routed that close.
- The two P1/DISP links form the dictionary storage ring.  Their capacities
  must be considered together and cannot both be minimized independently.

The checked-in layout has these parsed pipe lengths:

| Pipe | Current cells | Semantic requirement |
| --- | ---: | --- |
| feeder → DECODER | 8 | at least 2 |
| DECODER → DISP | 43 | at least 2 |
| DISP → YEAR | 2 | at least 2 |
| YEAR → UNPACK | 7 | at least 2 |
| UNPACK → output | 3 | at least 2 |
| P1 → DISP | 2 | at least 2; coupled with the return pipe |
| DISP → P1 | 33 | at least 2; coupled with the forward pipe |

The dictionary contains 35 entries and one `-1` sentinel, for 36 circulating
words.  During rotation one word can be held by a runner between its `r` and
`s`, so the exact capacity condition for the current table is:

```text
len(P1 → DISP) >= 2
len(DISP → P1) >= 2
len(P1 → DISP) + len(DISP → P1) >= 35
```

More generally, the sum must be at least
`dictionary entries + sentinel - 1`.  This is a correctness requirement, not
just a throughput preference.  P1 starts preloading while DISP can already
begin a lookup.  The return leg must retain the prefix that DISP rotates out
until the sentinel arrives and P1 enters its steady pump loop.  With too little
combined capacity, P1 blocks before sending the sentinel while DISP blocks
trying to return the prefix: neither can create the space needed by the other.

Capacity-only interpreter tests confirm the boundary:

- every tested division totaling 35 cells passed, including `2+33`, `5+30`,
  `20+15`, `30+5`, and `33+2`;
- `2+32` (34 total cells) deadlocked after five output bytes;
- all five ordinary links shortened to two cells at once still passed when the
  ring was `2+33`.

The current ring has `2+33=35` cells: exactly the semantic capacity floor,
with no slack.  Moving either ring attachment or shortening either route
therefore requires lengthening the other leg by the same amount.

These are *semantic* minima.  A concrete route may need to be longer because
its endpoints are farther apart or because it must avoid rooms and other
pipes.  With fixed endpoint cells, a route needs at least the Manhattan
distance between its first and last pipe cells plus one cell, and possibly
more for endpoint direction or obstacle detours.  If an optimization moves an
attachment rather than merely rerouting between the same attachments, recheck
nearest-pipe ownership: DISP has multiple incoming and outgoing pipes, and its
`r`/`s` instructions select by distance to the attachment cell.  Also preserve
the final arrowhead pointing into the destination wall.

History Lesson is footprint-only, so shorter latency does not directly improve
its score.  It still affects the tick cap and may change how much time is spent
blocked; after any pipe reflow, run the complete oracle case rather than
validating only the topology.

## Variable-width feeder experiment

`optimize_feeder.py` replaces the feeder's one fixed slot-width tuple with a
different tuple for each two-row band.  Backtick columns still match within
each adjacent row pair, as required by the literal parser, but need not match
between pairs.  It uses an interval dynamic program to choose chunk boundaries
and paired decimal widths, then a shortest-path dynamic program to minimize
the number of row pairs.

At width 82 the optimized feeder takes 62 rows instead of the fixed feeder's
64.  The intermediate `history-ring-variable-82.man` was 82×83.  The champion
keeps that feeder byte-for-byte, then manually folds the service tail from 19
rows to 18 and tightens the dictionary ring from `12+71` cells to its `2+33`
minimum.  That final fold reaches 82×82.

For the encoding-only analysis of adding more dictionary entries, using
multiword entries, and minimizing feeder literal count independently of
layout, see [`FEEDER-DICTIONARY.md`](FEEDER-DICTIONARY.md).

## Narrow constant-tail variant

`candidates/81x82.man` uses the two old pump rows twice:

- the steady `>>rsv` / ` ^<<<` pump is moved to the far right;
- the first pump row preloads `Baltim`, `iotis, `, and `, Italy`, followed by
  the ring sentinel;
- aligned, unsent zero literals on the second row preserve vertical backtick
  pairing.

Those three phrases are the unique best remaining choices by immediate
base-92 symbol reduction: each occurs twice and replaces six tokens with an
escape pair, saving eight symbols.  Together they reduce the stream from
2,042 to 2,018 symbols.  The width-81 feeder DP then fits in the same 62 rows,
using 294 literals rather than the old width-82 plan's 304.

The P1 room shrinks from 80 to 79 columns.  DISP drops its unused rightmost
interior column, which frees the two-cell P1→DISP return pipe at x=77.  The
other ring leg folds down a second time above P1: it has 45 cells, so the two
legs provide 47 cells of capacity for the 38 dictionary entries plus sentinel.
The organizer WASM passes the complete public output in 255,288 ticks.

## The dispatcher rebuild

DISP — the room holding the `17`, `31` and `92` literals — was rebuilt from six
interior rows to **five**, and from 24 (champion) or 23 (vertical) columns to
**21**.  Both live builds now carry it:

| Build | DISP room before | after | cells |
| --- | --- | --- | ---: |
| `best/81x81.man` (`DISP_COMPACT_ROWS`) | 26×8 | **23×7** | 208 → 161 |
| `candidates/81x90-vertical-p2.man` | 25×11 | **23×7** | 275 → 161 |

Neither program's footprint changes: in the champion the service band is 8 rows
because UNPACK and DECODER stack to 8, and in the vertical build DISP sits
inside P1's row span.  This is headroom, not score.

Three independent things paid for the shrink; the first applies only to the
vertical line, the other two to both.

- **The 81-lap countdown was not load-bearing.**  `build_vertical_p1` spends
  DISP's top three rows on a delay loop, added on the theory that DISP must not
  start rotating before P1 finishes its (slower, vertical) preload.  It isn't
  so: the two ring legs carry 118 cells against a 44-entry dictionary plus
  sentinel, far above the `entries + sentinel − 1` capacity floor, so DISP simply
  blocks on `r` until P1 catches up.  Deleting the loop passes and is ~800 ticks
  faster.  Three rows, for free.
- **`b` moved up into the classifier head**, stashing the raw symbol in `BP`
  *before* subtracting 17.  The `v ≤ 16` branch then already holds its rotation
  count, which deletes the `+`/`b` pair that used to rebuild the count from
  `v − 17` — and, in the vertical build which has no zero marker to test for,
  the `-` cell that needed a row of its own as well.  Two columns.
- **The sentinel return folded into a riser column.**  The old grid spent a
  whole sixth row walking west from the ring send back to the `W` swap.  Putting
  the drain loop's `X` *before* its turn lets the 0 sentinel fall out of the loop
  travelling east, so `s` (send the sentinel) and `W` (lift the saved entry back
  into `A`) stack vertically in the last column and rejoin the ordinary return
  corridor on row 0.  One row.

The champion's 21×5 interior, with the ring machinery annotated.  The vertical
build's grid is the same except that its head reads `` > `17` M r b - v `` — no
zero marker exists once YEAR is gone, so the `-` and the drop collapse into the
head and the `+31` riser moves from x=7 to x=10.

```text
        row 0  v@<<s  <  <         <     return corridor; x=4 is the only YEAR send
        row 1  >`17`Mr bX^         W     head: B=17, A=sym, BP=sym, then zero test
        row 2   >`31`+^ -          s     +31 for raw ASCII; `-` drops to the 3-way
        row 3  vX~`92`M+X> mdrMs>rX^     ESC test (`92` reads back 29 westward)
        row 4  >rb       ^sr<   ^s<      ESC's second read; underside of both loops

        x=10..13  rotate BP-1 times   > _ m d  /  ^ s r <
        x=14..16  take the entry, keep it in B, put it straight back on the ring
        x=17..19  drain the rest until the 0 sentinel   > r X  /  ^ s <
        x=20      riser: send the sentinel, W the entry into A, walk home
```

`b` sits at x=8 rather than x=7 specifically to leave x=7 clear for the `+31`
riser to pass through on its way to the row-0 corridor.

Ports had to move with the walls, because `s` and `r` bind to the *nearest*
pipe.  In the champion both ring legs now attach squarely to DISP's east wall at
x=73 (rows +1 and +5) instead of reaching around the old room corner at x=76,
which also widens the ring strip from five columns to eight; the leg lengths are
unchanged at 26+13 = 39 cells.  In the vertical build, DISP → UNPACK moved from
x=74 to x=76 and DISP → P1 from x=78 to x=77.  Every send and receive wins its
nearest-pipe contest by at least one cell.

`scratchpad/history-disp/test_disp_p2.py` runs all four grids — champion and
vertical, before and after — standalone against a scripted symbol stream and
dictionary ring, using the same `(manhattan, attach_y, attach_x)` tie-break the
interpreter uses.  A future port move that flips a binding fails there in under
a second rather than in a 200k-tick oracle run.

Still on the table for this block: the `+31` path and the ESC path each need
their own row, which is what holds the interior at five rows rather than four.

## Vertical-P1 line

`build_vertical_p1.py` is a different tail experiment: it drops the YEAR room
entirely (the year prefixes become ordinary stream text, spelled by two
repurposed dictionary slots and raw shifted ASCII digits) and stands P1 up as a
tall 52×20 preload room instead of a wide one.  It produces
`candidates/81x90-vertical-p1.man`.  At 81×90 it is **not** competitive with
the 81×81 champion — the point of the line is that a shorter, squarer service
tail becomes reachable once YEAR is gone.

`build_vertical_p2.py` is that program with the rebuilt dispatcher above, and
nothing else changed.  The four rows DISP gave back sit directly above the four
rows of ring routing at y=86..89; re-anchoring DISP at y=75 and routing both
ring legs through y=82..85 would take that program to 81×86 (score 7,396).

## Reproducing the champion

From the repository root:

```bash
python3 solutions/history-lesson/build_ring.py --narrow
git diff --exit-code -- solutions/history-lesson/candidates/81x82.man
python3 solutions/history-lesson/build_ring.py
git diff --exit-code -- solutions/history-lesson/best/82x82.man
python3 scratchpad/history-ring/test_rooms.py
python3 scratchpad/history-ring/test_year.py
python3 scratchpad/history-ring/test_disp.py
python3 scratchpad/history-disp/test_disp_p2.py
node tools/grade_json.js history-lesson solutions/history-lesson/candidates/81x82.man \
  --cases tests/history-lesson.json --failfast
node tools/grade.js history-lesson solutions/history-lesson/best/81x81.man
```

`test_disp.py` covers the 6-row dispatcher that `--legacy` and `--narrow` still
use; `test_disp_p2.py` covers the rebuilt 5-row one the champion now uses.  The
two `--legacy`/`--narrow` reproduction gates above are what pin the rebuild to
the champion only: `DISP_ROWS` is untouched, so those two files stay
byte-identical.

The vertical-P1 line reproduces the same way:

```bash
python3 solutions/history-lesson/build_vertical_p1.py
git diff --exit-code -- solutions/history-lesson/candidates/81x90-vertical-p1.man
python3 solutions/history-lesson/build_vertical_p2.py
git diff --exit-code -- solutions/history-lesson/candidates/81x90-vertical-p2.man
python3 scratchpad/history-disp/test_disp_p2.py
node tools/grade.js history-lesson solutions/history-lesson/candidates/81x90-vertical-p2.man
```

The two builder commands deterministically run the variable-width feeder DP.
Each following `git diff` is a strict reproduction gate: no output and exit
status zero means the generated file is byte-identical to the checked-in
artifact.  Each generation takes roughly 30 seconds on the contest machine.

Two DSL details are load-bearing:

- `Program` records every room rectangle so `audit_vertical_ticks()` scopes
  vertical-literal checks to one room.  Backticks in vertically stacked rooms
  are unrelated because the intervening walls terminate literal parsing.
- `Program.pipe(..., end_direction="E|W|N|S")` expresses a pipe whose final
  cell turns into the destination wall.  The compact DECODER→DISP and both
  ring routes use such corner-ended pipes; replacing them with ordinary
  last-segment arrows changes the topology.

The old layouts remain reproducible for comparison:

```bash
python3 solutions/history-lesson/build_ring.py --legacy
python3 solutions/history-lesson/build_ring.py --legacy 82 --variable
```

## Rebuild and verify

```bash
python3 solutions/history-lesson/optimize_feeder.py 82 83
```

This standalone command reports feeder alternatives without writing a
solution.  The room tests in the reproduction recipe check the dense pieces
independently: base-92 tagging, dictionary rotation/restoration, year-boundary
generation, and dispatch.
