# History Lesson — ring dictionary build

`best/82x82.man` is the checked-in champion for this problem.  It has an
**82×82** non-space footprint, so its footprint-only score is **6,724**.
`build_ring.py` reproduces it byte-for-byte; the `.man` file is not a
hand-maintained second source of truth.

| Candidate | Footprint | Score |
| --- | ---: | ---: |
| `best/82x82.man` | 82×82 | 6,724 |
| `history-ring.man` | 83×83 | 6,889 |
| `history-lesson-with-year.man` | 84×84 | 7,056 |
| `history-lesson-v3.man` / `v4.man` | 85×85 / 85×84 | 7,225 |
| `history-lesson-v2.man` | 86×86 | 7,396 |

The program has no input.  It emits the byte sequence in
`icfp-history.txt`; consequently a slow, small decoder is the right tradeoff.
Its cached oracle check passes the sole public case in 352,318 ticks, but ticks
do not affect this problem's score.

## Encoding

`build_ring.py` is the source of truth for `best/82x82.man`.  It transforms the
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

## Reproducing the champion

From the repository root:

```bash
python3 solutions/history-lesson/build_ring.py
git diff --exit-code -- solutions/history-lesson/best/82x82.man
python3 scratchpad/history-ring/test_rooms.py
python3 scratchpad/history-ring/test_year.py
python3 scratchpad/history-ring/test_disp.py
node tools/grade_json.js history-lesson solutions/history-lesson/best/82x82.man \
  --cases tests/history-lesson.json --failfast
```

The first command deterministically runs the variable-width feeder DP and
overwrites `best/82x82.man`.  The second command is the strict reproduction
gate: no output and exit status zero means the generated file is byte-identical
to the checked-in champion.  Generation takes roughly 30 seconds on the
contest machine.

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
