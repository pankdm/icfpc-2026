# history-lesson champion, 81x81 — a copy to poke at

`81x81.man` is a byte-for-byte copy of `solutions/history-lesson/best/81x81.man`
as of this commit.  It is here so experiments have something to read, diff and
mutate without touching the champion.  Regenerate the real one with:

```bash
python3 solutions/history-lesson/build_ring.py
```

Score is **footprint-only**: `max(w, h)^2 = 81^2 = 6561`.  It passes the sole
public case in 208,863 ticks on the organizer WASM, and the problem has **0
private tests**, so a local pass is definitive.  Ticks do not affect the score.

```bash
python3 tools/grade_fast.py history-lesson scratchpad/history-81x81/81x81.man
node tools/grade.js    history-lesson scratchpad/history-81x81/81x81.man
```

## Row budget

The whole layout is three stacked slabs.  Rows are the scarce resource; the
feeder dominates and everything else is a fixed 18-row tail.

| rows | what |
| --- | --- |
| 0–64 | feeder room: 63 rows of decimal literals + 2 walls |
| 65–72 | service band, 8 rows (UNPACK stacked over DECODER sets the height) |
| 73–80 | P1, the dictionary preload room, 8 rows |

`height(W) = feeder(W) + 18`, and the feeder costs exactly one row per column
removed (63/64/65 content rows at W = 81/80/79).  So `max(W, height)` is
minimised on the diagonal, at W=81 — which is why this build is square, and why
shifting the width alone can never improve it.  See the main README's
"width/height crossover" section.

## Rooms and pipes, as the loader sees them

Room ids are the interpreter's (`lm --inspect=0`).  Six little men run.

```text
  id 0  feeder      x0..80   y0..64     serpentine over the literal grid
  id 5  DECODER     x3..13   y69..72    repeated /92  -> base-92 symbols
  id 4  DISP        x50..72  y65..71    classify + dictionary ring lookup
  id 3  YEAR        x19..47  y65..71    emits "; YYYY: " on a 0 marker
  id 1  UNPACK      x1..12   y65..68    repeated /128 -> raw ASCII bytes
  id 2  output      x16..18  y65..67
  id 6  P1          x0..79   y73..80    preloads the ring, then pumps it

  feeder --(0,65)--> DECODER --(14,70)--> DISP --(49,66)--> YEAR
                                                --(18,68)--> UNPACK --> output
  DISP <==> P1   the dictionary ring, two legs in the strip x73..79
                 (73,66)->(78,72) out, (77,72)->(73,70) back; 26+13 = 39 cells
```

The ring legs' combined length is a **correctness** requirement, not a
preference: they must hold every ring word but one, or preload deadlocks.  39
cells against 35 words here, so there is very little slack — if you grow the
dictionary you must lengthen them, and note that *every pipe cell adjacent to a
room wall reads as an attachment*, so a serpentine that grazes P1's top wall
splits into several pipes.

## The dispatcher, if you only want to read one room

DISP is the interesting one — 21x5 interior at x51..71, y66..70:

```text
  row 0  v@<<s  <  <         <     return corridor; x=4 is the only send to YEAR
  row 1  >`17`Mr bX^         W     head: B=17, A=sym, BP=sym, then the zero test
  row 2   >`31`+^ -          s     +31 for raw ASCII; `-` drops to the 3-way
  row 3  vX~`92`M+X> mdrMs>rX^     ESC test (`92` reads back 29 *westward*)
  row 4  >rb       ^sr<   ^s<      ESC's second read; both loop undersides

  x=10..13  rotate BP-1 times      > _ m d  /  ^ s r <
  x=14..16  take the entry, keep it in B, put it straight back on the ring
  x=17..19  drain the rest until the 0 sentinel   > r X  /  ^ s <
  x=20      riser: send the sentinel, W the entry into A, walk home
```

Only two cells depend on the alphabet — the `17` threshold and the `92` ESC
constant — and both are two digits, so `build_ring.disp_compact_rows(t, e)`
can retune them without moving anything.

`scratchpad/history-disp/test_disp_p2.py` runs this grid standalone against a
scripted symbol stream and ring in under a second, using the interpreter's own
`(manhattan, attach_y, attach_x)` nearest-pipe tie-break.  Start there before
changing a glyph.
