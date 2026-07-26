# Prototype: integer year → ASCII, written into a pipe

Answers: *what happens to history-lesson if the year prefix is produced by an
ASCII converter instead of the packed base-128 accumulator?*

## What is here

`build_year_ascii.py` emits two graded-clean prototypes.

| file | year source | footprint | tested |
| --- | --- | --- | --- |
| `year-ascii.man` | year arrives on the input pipe after a `0` escape | 25×18 | 1996–2026, 1000, 9999 |
| `year-ascii-counter.man` | free-running counter room, stream carries only `0` | 37×18 | 30 consecutive years 1997–2026 |

Both emit the full 8-byte prefix `"; YYYY: "` and pass raw bytes through
untouched. Escape protocol: input `0` means "emit the next year"; every other
value is an ASCII byte emitted as-is.

```bash
python3 scratchpad/year-ascii/build_year_ascii.py
node sim/case.js scratchpad/year-ascii/year-ascii.man \
  '[{"in":["0","1999","88","0","2000"],"out":["59","32","49","57","57","57","58","32","88","59","32","50","48","48","48","58","32"]}]'
```

## The gadget

```
Z = Y + 48000
repeat 4:                      # BP counts the passes
    q, rem = divmod(Z, 1000)   # q == 48 + digit, i.e. already ASCII
    send q
    Z = rem * 10 + 48000
```

Two tricks make this fit in one room with only `A`, `B` and `BP`:

- **Bias by `48 * 1000`.** Integer division carries the bias straight into the
  quotient, so the digit leaves the divider already shifted into ASCII and no
  separate `+48` stage (which would need a third live value, i.e. a second
  room) is required. The remainder is untouched by the bias.
- **Rescale the remainder instead of shrinking the divisor.** `1000` stays a
  single constant, so the digit loop is one straight 17-cell run rather than
  four unrolled steps with four different literals.

Digits come out most-significant first, so they go straight into the pipe — no
base-128 packing and no `UNPACK` round trip. (Raw single bytes survive a
`/128` unpacker unchanged, so the converter can also sit in front of the
existing `UNPACK` room untouched.)

The counter variant keeps the year in `A` of a 4-glyph loop `s M 1 +` and
pushes years into a pipe until it blocks; blocked men park for free, and the
converter just does an ordinary `r`. The converter's two `r`s are separated by
14 cells so the nearest-pipe rule keeps the stream `r` on the input pipe and
the year `r` on the counter pipe.

## Why this does not (yet) help the score

Measured against the current champions, **after** the variable-width feeder
landed on `main`:

| build | footprint | score | bound by |
| --- | --- | ---: | --- |
| `history-ring.man` (fixed feeder, W=83) | 83×83 | 6,889 | both |
| `history-ring-variable-82.man` (W=82) | 82×83 | 6,889 | **height** |

Width is already down to 82; only **height** is still 83. One row off the
height is worth 6,889 → 6,724. That makes band *columns* worthless and band
*rows* and feeder *digits* the only currencies. Against that ruler:

- **The band cannot get shorter from here.** It is 8 rows tall because `DISP`
  is 27×8 outer; `year_rows` is already only 29×**7**. The converter is 25×8
  outer / 67 glyphs (vs. 82 glyphs) — it frees 4 band columns, which buy
  nothing, and adds no rows, which gains nothing.
- **The counter room has nowhere to go.** CTR is 10×5 outer, and at W=82 the
  bottom band is full (`UNPACK`/`DECODER` x2..14, `O` x17..19, year x20..48,
  `DISP` x52..78, ring 79..81). Net effect of the swap is **+6 columns** of
  band width the band does not have.
- **Stream savings are real but small.** The packed accumulator cannot cross
  1999 → 2000 (`STEP`/`CORR` only carry the units and tens digits), which is
  why `FIRST_YEAR = 2000` and 1996–1999 are spelled out. The converter makes
  1997–2026 markable — re-running the encoder gives **2,042 → 2,033 symbols**,
  ~18 feeder digit cells, well under a third of the one feeder row that
  `optimize_feeder.py` still needs to find at width 82. The dictionary already
  compresses `"; 199X: "` well, so the century carry buys little.

## What it is actually good for

- **Correctness headroom.** The converter is oblivious to decade and century
  carries and to `FIRST_YEAR`; the current room hard-codes a 17-digit packed
  seed, an 11-digit `STEP` and a 12-digit `CORR`, all of which must stay valid
  i64 read in *both* directions.
- **A shelf item, not a win.** Swapping it in on its own costs band width and
  gains ~9 symbols. It only becomes interesting if the bottom band is ever
  re-folded — e.g. trading the 4 columns it frees for a shorter, wider `DISP`,
  which is the one route to a 7-row band and an 82×82 grid.
