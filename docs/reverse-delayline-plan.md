# Reverse-a-list: delay-line board-beat — implementation plan

Target: beat the reverse board-best **109,382**. Our current submission is ring-v2
(956,100 local / 1,536,640 server). The delay-line is the only design that can beat the
board because it is **O(n) ticks, not O(n²)** — so it is footprint-bound, and footprint
we can fold.

## Validated core (already measured on the oracle — do not re-derive)

**Reverse-collector:** two men + n length-2 "lane" pipes.
- **READER** (top room, walks EAST): reads the count, discards it; then for each value does
  `r, s` — `s` sends v_i into lane i's mouth (the lane pipe whose source cell sits directly
  under the reader's s-cell; lanes on even columns, the one directly below wins the
  nearest-outgoing tie).
- **COLLECTOR** (bottom room, walks WEST): at each lane column, a **blocking** `r` (nearest
  incoming = the lane directly above) then `s` to the single O pipe. Sweeping **right→left**
  reads lane n−1 (last written) first → **output reversed**. Blocking `r` means **no
  length-staggering / timing tricks** — the pipe holds the value until the sweep arrives.
- Lanes are the minimum 2-cell pipes; values pass through raw (21-bit values fit any pipe
  cell — no bias/pack needed).

**Measured:** correct reversal for n=3,7,16; **tick(n)=4n+3** (n=16→67, n=7→31, n=1→7);
flat footprint (2n+6)×18. Prototype: `scratchpad/dl/buildRC.py`, `rc.man`, `run.js`.

The tick side is done. **~85 avg ticks over the case set.** At flat box 1444 that's ~123k
(marginally above board); the board-beat is entirely in the fold.

---

## Phase 1 — Generalized flat version (SAFE FLOOR, submit)

Goal: a fully-correct, multi-round, all-n reverse at ~**123k** — already a ~7–12× win over
our 956k/1.5M, and near the board. Submit it as the floor before risking the fold.

**1a. n<16 generality (the collector-homing problem).** A fixed 16-lane structure deadlocks
for n<16: the collector starts at empty lane 15 and its blocking `r` never returns. Fix:
- READER sends **n** to the collector on a dedicated **count-pipe** (before/after writing lanes).
- COLLECTOR receives n, computes its start column `col = base + 2·(n−1)`, walks there, then
  sweeps west doing `r,s` per lane, counting **n** emits (backpack countdown) so it stops at
  lane 0 and doesn't read past into stale/empty lanes.
- Cost: ~2(16−n) extra walk ticks for small n — negligible.

**1b. Multi-round reset.** After emitting, both men loop back to start for the next round
(round input is withheld until this round's output lands, so the ring/lanes are empty).
Reader loops to the count-read; collector loops to home. Measured ~15 ticks/round reset —
keep the loop-backs short (adjacent turn cells).

**1c. Layout hygiene.** Side-mount I and O rooms (left/right) so height stays ~12–14; the box
is width-dominated so this doesn't change it but keeps the fold clean. Value pass-through is
raw (no bias). Verify 8/8 public + n=1, n=16, negatives ±1e6, palindromes, 1–3 rounds.

**Submit Phase 1** (score ~123k is > board, so it's a safe bank of a big improvement).

---

## Phase 2 — The width-fold (BOARD-BEAT, hold if it lands)

The box is `width² = (2n+6)²` because 16 lanes spread horizontally. Height is only ~14.
Folding the 2n-wide walks into a 2-row boustrophedon takes width from ~38 to ~22 →
**box 484 → ~41k (beats board 2.6×)**. Even a lazy fold to width 30 → box 900 → ~76k wins.

**The crux = lane planarity (pipes cannot cross).** Proposed approach — **identical fold +
vertical lanes:**
- Fold the READER into 2 rows: lanes 0–7 on row A (east walk), lanes 8–15 on row B (west walk),
  sharing columns 4,6,…,18.
- Fold the COLLECTOR the same way directly below, so **lane i's reader-cell and collector-cell
  share a column → the lane is a short vertical pipe, no horizontal crossing.**
- The collector sweeps in reverse across the folded rows: read lane 15 (row B, col 18) → … →
  lane 8 (row B, col 4) → lane 7 (row A, col 18) → … → lane 0 (row A, col 4).
- **Open risk:** the pipes for the "far" reader row must reach the matching collector row
  without passing through the near row's structures. Prototype and MEASURE planarity on the
  oracle; if the straight 2-band stack crosses, try: (i) interleave reader/collector rows so
  each lane is a 2-cell vertical pipe between vertically-adjacent cells; (ii) a serpentine
  where reader and collector share the fold; (iii) start with a **conservative fold to width
  30** (box 900 → ~76k, still beats board) which needs less aggressive routing.

**Staged fold:** width 38→30 (box 900, ~76k) first — lower routing risk, already board-beating
— then push 30→22 (box 484, ~41k) if the tighter routing lands.

**Submit policy:** any Phase-2 result **beats the board → HOLD, commit + report the exact
score** for review (we conceal board-leaders until the endgame freeze). Phase 1 (~123k, above
board) submits normally.

---

## Risks & mitigations (all flagged by the brainstorm's adversarial vet)
1. **Fold planarity** (the make-or-break): mitigated by identical-fold vertical lanes + the
   staged width-30-first fallback (still wins at ~76k).
2. **n<16 deadlock:** solved by the count-pipe homing (1a).
3. **Multi-round reset cost:** real but ~15/round; keep loop-backs tight.
4. **Server penalty:** the brainstorm's ~85-tick estimate is local; apply the measured ~1.6×
   public→private/server factor → server ~135 ticks. Re-check: box 484 × 135 ≈ 65k (still
   beats 109k); box 900 × 135 ≈ 121k (marginal — so the tight fold matters for the server).
   **Measure the real multi-round avgTicks, don't trust the flat 4n+3.**

## Build order
1. Start from `scratchpad/dl/buildRC.py` (validated core).
2. Phase 1a→1b→1c, grade 8/8 + generality, **submit ~123k**.
3. Phase 2 conservative fold (width 30), measure server-realistic avgTicks, **hold if <109k**.
4. Phase 2 tight fold (width 22) toward ~41–65k, **hold**.
Test every stage on the oracle; the core tick law and reversal are already proven, so failures
will be in homing / reset / fold-routing — all localizable with the per-tick tracer.
