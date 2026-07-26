# History Lesson — ring dictionary build

`history-ring.man` is the smallest checked-in solution for this problem.  It
has an **83×83** non-space footprint, so its footprint-only score is **6,889**.
The submitted artifact currently recorded in `submitted/history-lesson.man` is
the older `history-lesson-with-year.man` at 84×84 (7,056).  The ring build is
therefore the repository champion, but this document does not claim it has
been submitted.

| Candidate | Footprint | Score |
| --- | ---: | ---: |
| `history-ring.man` | 83×83 | 6,889 |
| `history-lesson-with-year.man` | 84×84 | 7,056 |
| `history-lesson-v3.man` / `v4.man` | 85×85 / 85×84 | 7,225 |
| `history-lesson-v2.man` | 86×86 | 7,396 |

The program has no input.  It emits the byte sequence in
`icfp-history.txt`; consequently a slow, small decoder is the right tradeoff.
Its cached oracle check passes the sole public case in 215,585 ticks, but ticks
do not affect this problem's score.

## Encoding

`build_ring.py` is the source of truth for `history-ring.man`.  It transforms
the target text into a compact stream with these base-92 symbols:

| Symbol | Meaning |
| --- | --- |
| `0` | Emit the next `; YYYY: ` prefix (2000 through 2026). |
| `1..16` | A short dictionary entry; `13` means `, `. |
| `17..91` | Ordinary ASCII stored as `symbol + 31`. |
| `29, k` | Escape pair selecting ring position `k` for a longer phrase. |

The encoder greedily replaces recurring phrases when the saved feeder space is
larger than the decimal literal needed to preload the phrase.  Dictionary
values are raw ASCII packed little-endian in base 128; a phrase is at most nine
bytes so it fits in a signed 64-bit literal.  The final base-92 symbol stream is
packed little-endian into as many literals as each feeder slot can hold.

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

The physical layout folds the feeder above P1 and puts the decoder, lookup,
year, unpacker, and output in the lower bands.  Two slim vertical pipes at the
right close the P1/DISP loop.  The layout is square on purpose: the problem
scores only `max(width, height)^2`.

## Rebuild and verify

```bash
python3 solutions/history-lesson/build_ring.py
python3 scratchpad/history-ring/test_rooms.py
python3 scratchpad/history-ring/test_year.py
python3 scratchpad/history-ring/test_disp.py
node tools/grade_json.js history-lesson solutions/history-lesson/history-ring.man \
  --cases tests/history-lesson.json --failfast
```

The room tests check the dense pieces independently: base-92 tagging,
dictionary rotation/restoration, year-boundary generation, and dispatch.
