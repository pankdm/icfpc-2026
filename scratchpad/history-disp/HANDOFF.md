# history-lesson: the 6400 attempt — full handoff

**State:** the new design is **working and oracle-verified end to end**, but as an
uncompacted artifact (393×83). The champion is untouched at **81×81 = 6561**.
The remaining work is entirely *compaction* — no unknowns of correctness left.

| file | what it is |
| --- | --- |
| `full_routeB.man` | **complete working program**, oracle 1/1, 291,027 ticks, 393×83 |
| `build_full_routeB.py` | builds it. `python3 build_full_routeB.py` (~35 s) |
| `rig.man` / `build_rig.py` | isolated dispatcher rig, oracle 612/612 — use this to iterate |
| `proto_routeB.py` | the register trace, checked against spec for every symbol 0..91 |
| `layout_routeB.py` | the compact floor plan attempt, with the conflict that stopped it |
| `../history-dict/*.py` | all the measurement scripts behind the numbers below |

Verify:

```bash
node tools/grade.js history-lesson scratchpad/history-disp/full_routeB.man
node sim/case.js scratchpad/history-disp/rig.man "$(cat scratchpad/history-disp/rig_case.json)"
python3 scratchpad/history-disp/proto_routeB.py
```

---

## 1. Why the champion cannot be improved by rearranging

Score is `max(w,h)²`. The feeder DP costs **exactly one row per column removed**
— measured content rows 65/64/63/62/61 at W = 79/80/81/82/83 — and the tail
below it is a constant 18 rows (2 feeder walls + 8 service band + 8 P1). So

```
height(W) = feeder(W) + 18        score = max(W, height(W))²

   W:       79     80     81     82     83
   height:  83     82    [81]    80     79
   score: 6889   6724   6561   6724   6889
```

The champion sits exactly on the diagonal where width equals height. With slope
−1 any width shift trades one dimension for the other 1:1 and `max` can only
stay or grow. **6561 is the floor of the layout.** Only the encoded size moves
the curve, at a fixed rate: ~150 feeder cells (~77 symbols) per row, two rows
per unit of box side.

### Dead ends, all measured

- **A pipe may not loop back into its own room** — load error, verbatim:
  *"pipe loops back to the room it started from"*. Kills merging DECODER into
  DISP. (`selfloop.man`)
- **Two rooms may not share a wall row.** A shared row silently fails to parse
  the upper room, so its `@` never spawns. `share4.man` (shared) crashes
  `no-pipe` with one runner; `share5.man` is the same layout unshared and
  passes. **A probe of two `@H` rooms "passes" either way and proves nothing** —
  always give the probe an expected output and check runner/pipe counts.
- **A one-content-row room cannot branch**: `X`, `d`, `a`, `x` all turn north or
  south, which is the wall. So no divmod loop fits in 3 rows and the
  UNPACK/DECODER stack cannot be 7.
- **The service band is 8 rows because UNPACK stacks over DECODER** (4+4), not
  because of DISP or YEAR — both are 7. Unstacking needs 11 columns the band
  does not have.
- **The feeder is at its packing floor**: 4900 occupied cells in a 5120-cell
  grid at W=80. The DP is exact for its model and already exploits chunks whose
  leading symbol is small (1.864 digits/symbol against the 1.964 bound).
- **The dictionary packer is at its floor.** Fixed shared profile is optimal;
  giving group B the feeder's variable-width bands is *worse* (a 2-row band
  amortises the 3-cell per-entry overhead over 2 entries, the current 4–7-row
  profile over 4–7); unifying groups A and B is never better. (`pack.py`)

---

## 2. The unlock: 25 symbol values are dead

`tokenize` maps a byte to symbol `b − 31`, and DISP reads `v <= 16` as a
dictionary reference. But only **66 of the 91 symbol values name a byte that
actually occurs**. The other 25 are dead, in ten contiguous runs:

```
(2) (4-7) (11-12) (16-17) (19-22) (29-31) (33) (58) (60-65) (82)
```

Today only the 9 inside `1..16` (`SMALL_FREE`) are recycled. Recycling more is
nearly free: **a promoted entry is already in the ring**, so its P1 cost is
unchanged — it just stops costing `ESC, position` (2 symbols) per reference and
costs 1.

### Route A (raise the threshold) — built, and it only TIES

Raising T to 30 makes every free symbol below 30 direct. Implemented and
measured; **every threshold lands on height 81, i.e. 6561 at width 80.**

The projection that said 6400 was wrong, and the reason matters: it assumed
group A could be packed width-sorted like group B. It cannot. DISP reaches ring
position `p` by rotating `p−1` times, so **position `v` *is* symbol `v`**, and
every position whose symbol spells a literal byte is **pinned**. Raising T adds
those pinned byte entries to group A where they interleave with the wide phrase
entries. Group A's 29 entries then need ~279 cells against 73/row = 4 rows, and
group B stays at 4 even after losing five entries (3 rows forces `nB=5` and
`sum(TB)+3nB` = 78 > 73).

Route A also overruns the ring — 43 entries + sentinel need 43 cells of pipe
against the strip's 37 — and combing more of the strip **split the return leg
into three pipes**, because *every pipe cell adjacent to a room wall reads as an
attachment* and the serpentine touched P1's top wall in three columns.

### Route B (recycle whole runs) — this is the one that works

Keep the threshold at 17 and ESC at 29; recycle `60-65` into ring positions
17–22. Group A keeps its 2 rows and its 7 byte entries, and the recycled
phrases land in group *B*, which absorbs them. Measured with the real packers
(`split2.py`, `runsB.py`):

| recycled | direct | symbols | feeder | grp A | grp B | height | box |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none (today) | 9 | 2042 | 64 | 2r | 4r | 82 | 6724 |
| **`60-65`** | **15** | **1951** | **61** | **2r** | **5r** | **80** | **6400** |
| `19-22`+`60-65` | 19 | 1926 | 60 | 2r | 4r | 78 | 6400 |

The single run is the one to build: it needs only **one** range test, so DISP
fits in 6 content rows and the service band stays 8.

---

## 3. How the dispatcher works

The blocker was that a two-sided range test needs two constants while `A` and
`B` are both live and `BP` is write-only. Three things solve it.

**Products, not comparisons.** `(59−v)(66−v) < 0` iff `60 ≤ v ≤ 65`. Both
factors derive from one accumulator. Each product's two zeros (`v = 59, 66`) are
*used byte symbols*, so `X`'s straight branch sends them to the literal-byte
path where they already belonged. Verified for all 91 symbols.

**The `-` at row 2 x9 is free work.** It is the classifier's `−17` descent cell
and cannot move — it must sit between the head's `X` and the 3-way `X` on the
same column. But the byte path also crosses it travelling east carrying `B = v`,
so loading 59 first makes that cell compute `59−v` at no cost.

**`BP` survives everything.** The head's `b` leaves `BP = v` and no `A`/`B`
arithmetic touches it.

The grid, 38×6 interior (`disp_rows()` in `build_rig.py`):

```
r0  v@<<s     <            <            <     corridor; s->YEAR at x4
r1  >`17`Mr bX^   >WM`16`-b  v                head, then BP = v-43 rebuild
r2   >`59`   -M7+*X>WM`90`-^            W     test, then v+31 rebuild
r3  vX~`92`M+X   v>^                    s     classifier, ESC test
r4  >rb          >           >> mdrMs>rX^     ESC lane (vertical r,b), ring top
r5                           ^sr<   ^s<       ring undersides
```

Ports (local, from the room's interior origin): stream in `(-2, 1)`, output out
`(4, -2)`, ring in `(39, 4)`, ring out `(39, 5)`. Every send and receive wins
its nearest-pipe contest by a wide margin at these positions — recheck if you
move them.

---

## 4. What is left

**Compact 38 interior columns down to ≤ 23**, then fold into `build_ring`. 23 is
the cap: the band spends 50 columns on the other rooms and gaps, leaving 30 for
DISP's room plus the ring strip, and the strip needs 5 columns to carry 38 cells.

`layout_routeB.py` records where the paper attempt stuck: test B's `X` branches
north/south into occupied cells, and the `v <= 16` descent has to cross the test
rows to reach the rotate entry. Note that attempt was for the *two*-run design;
the single-run design that now works is smaller and may well fit — it was never
retried on paper after the rig succeeded.

Compaction levers, cheapest first:
1. The rig is deliberately roomy — r2's byte tail and r1's BP rebuild both have
   slack, and the ring machinery can slide left.
2. Blank cells are direction-preserving, so one cell can serve two lanes
   crossing at right angles. The rig already does this at r3 x13–x15.
3. The ESC lane being vertical (`r` above `b`) is what freed the rows; keep it.

**Also required when folding in**, and easy to miss:
- The ring grows to 37 entries + sentinel, so the two legs must carry **37
  cells**; at W=80 they carry exactly 37. No slack — any reroute must preserve
  the length.
- `build_full_routeB.py` uses a naive one-row P1 preload precisely *because*
  that gives it full control of ring positions. `build_ring`'s P1 decides
  positions from a width-sorted grid, so folding in means making the 6 recycled
  phrases land in group B's first 6 walk positions.
- A pipe's source cell must step **away** from the wall it attaches to. A source
  that immediately runs parallel to the wall is silently not parsed as a pipe —
  this cost an hour; the symptom is a missing pipe and a `no-pipe` crash in the
  room at the far end.

## 5. Infrastructure already landed on main

In `build_ring.py`, all four builds byte-identical:
- `group_a_grid` / `pack_group_a` — group A generalised to R×n with a
  width-aware permutation of the free positions
- `THRESHOLD` and `group_b_rows` parameterised through the encoder
- `disp_compact_rows(threshold, esc)` — both alphabet literals are two digits,
  so the dispatcher does not change size when they change
- fix: sentinel relocation now picks a free cell whose column is wide enough
- fix: physical slot order derives from the last row's walk direction rather
  than assuming an even row count
