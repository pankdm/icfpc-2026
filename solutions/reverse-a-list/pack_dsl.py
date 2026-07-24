"""Register-PACKING reverse for `reverse-a-list` — validated mechanism + honest verdict.

GOAL (from the projected board-beating design): values are small (|v|<=1e6), so store
3 signed values per 64-bit register instead of one-per-belt-slot. Offset each value by
+1e6 -> field in [0, 2e6]; since 2^21 = 2,097,152 > 2e6, three 21-bit fields fit in a
63-bit register:  reg = f0*K^2 + f1*K + f2   (K = 2^21).  n<=16 -> <=6 registers.
The idea: a much SHORTER storage ring (capacity ~7 registers instead of 16 values) and
O(n) reversal, in a tiny footprint.  Projected 20k-60k, vs the board-best 109,382.

EVERY arithmetic component below was VALIDATED against the reference oracle (see the
`# VALIDATED` notes and scratchpad demos PURT.man / SLOTS.man). BUT a rigorous, measured
footprint/tick analysis (bottom) shows the packing machine, built the natural way (base-K
arithmetic with literal constants inside the controller), does NOT beat 109,382 — the
projection was optimistic. It DOES beat our own rotate-v3 (1,514,844) by an estimated
2x-4x. Kept here as working, reusable hardware (a `pack3`/`unpack` builder is broadly
useful — sort-numbers / memory can reuse it).

--------------------------------------------------------------------------------
KEY ISA CONSTRAINT that drives everything (confirmed in PROBLEM.md + oracle):
  BP is effectively WRITE-ONLY for data: the ops are `b`(BP=A), `m`(BP--), `q`(BP=pipe
  count), `]`(BP>>=1), and the branch tests d/a/x — there is NO `A=BP`. So only A and B
  are usable DATA registers. Any 3-operand step (e.g. reg = reg*K + f) therefore needs
  either an external pipe-stash OR a stash-free ordering. We found stash-free orderings
  for BOTH pack and unpack (below), so packing needs NO extra stash room — but it DOES
  need to re-load the 7-digit constants K and OFF from literals on EVERY field, because
  A and B are consumed by the arithmetic and BP cannot hold them. Each literal is 9 grid
  cells. This is the root cause of the footprint/tick blow-up (see ANALYSIS).

--------------------------------------------------------------------------------
STASH-FREE PACK combine (VALIDATED, SLOTS.man):  reg <- reg*K + (v + OFF)
  With reg the SOLE live value at field start, compute reg*K first, then fold v and OFF
  by duplicate-then-read — never needing a 3rd data slot:
      M            B = reg
      `2097152`    A = K            (literal)
      *            A = reg*K        (A=K, B=reg -> A=K*reg)
      M            B = reg*K
      r            A = v            (read next input value)      [I-band column]
      +            A = v + reg*K
      M            B = v + reg*K
      `1000000`    A = OFF          (literal)
      +            A = reg*K + v + OFF = reg_new
  For the FIRST field reg=0 so reg*K=0 and reg_new = v+OFF — no special case.
  PARTIAL last group: fill the remaining high fields with a PAD sentinel field
  (PAD=2000001, in (2e6, K) so it is out of the valid value range and unique):
      M `2097152` * M   `2000001`  +      (reg <- reg*K + PAD)
  VALIDATED: packing [5]->reg, [5,10]->reg, [10,20,30]->reg all match Python exactly
  (oracle uses true i64 internally — a 4.4e18 register round-trips losslessly; only the
   JSON *snapshot* display rounds).

STASH-FREE UNPACK (VALIDATED, PURT.man):  emit fields bottom-up (reversed within group)
      M `2097152` W /   ->  A = reg/K (rest), B = reg%K (field)   ( `/` yields BOTH)
      W  s  W          ->  send `field` to the output pipe, keep `rest` in A, repeat 3x
  `field` still carries the +OFF (and may be a PAD). A tiny SUBOFF relay on the output
  pipe removes OFF and DROPS pads, so the controller never needs a 3-operand step:
      SUBOFF loop:  R M `2000001` -  X   (A = PAD-field; ==0 -> pad -> loop/discard)
                    else  `1000000` - N  s   (emit field-OFF to O)   [all 2-register]

REVERSAL (register order): prepend-with-sentinel during read (belt starts [SENT=-1];
  to prepend reg: s(reg); rotate {r; if item==SENT resend&exit else resend} — newest ends
  at front). O(r^2) with r<=6 (<=~21 rotations) — negligible. Emit then dequeues in
  reversed register order until SENT, unpacking each register bottom-up (= full reverse).
  Multi-round: SENT persists on the belt; after emit, resend SENT and loop to the count
  read (input is gated on output, so `r` blocks until the next round is released).

Column discipline (all 4 pipes on the bottom wall, disambiguated by COLUMN only; proven
  in solutions/memory/dsl.py): I<=col-band for value/count reads, RETURN band for belt
  dequeues, FEED band for enqueues, SUBOFF band for field sends.
--------------------------------------------------------------------------------
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))
import littleman as lm

K = 2097152          # 2^21 base (> 2e6 so a +1e6-offset field fits in 21 bits)
OFF = 1000000        # value offset -> field in [0, 2e6]
PAD = 2000001        # pad sentinel field: in (2e6, K), never a real field


def _lit(v):
    return "`" + str(v) + "`"


# === PATTERNS === (reusable, VALIDATED base-K pack/unpack builders)

def pack_slot_bitop(p, ey, enq_col=17):
    """Place ONE BIT-OP pack slot (VALIDATED, NOPAD.man) — the improved, half-size packer.

    reg_new = (2*reg + 1) << 20 + v   ==   (reg<<21) + (v + 2^20)   [offset = 2^20]
    Uses only the constants `1` (a digit) and `20` (a 2-digit literal) — NO 7-digit
    literal — because we bake the +2^20 offset into a shift-by-20 with the +1 (`{`, not
    `*`). This is what shrinks the pack logic from box 729 (multiply) to box 361 (measured
    logic-only bbox 27x13 -> 19x14). NO PAD path: on BP==0 the man exits to enqueue the
    partial register; its unwritten high fields are naturally 0, and a real field is
    v+2^20 in [48576, 2048576] > 0, so the SUBOFF relay simply drops field==0.

    Entry: man heads EAST at (1,ey) with partial reg in A. Exit paths:
      * BP>0  -> REAL: down, do M 1 W { + M `20` W { M, dip to read v (col4), + , m ,
                 fall through to (1,ey+3) = next slot entry (reg_new in A).
      * BP==0 -> straight EAST to `enq_col`, down the shared ENQ channel (enqueue partial).
    Returns the next slot's entry row (ey+3). VALIDATED exact for n=1,2,3 incl negatives
    and the +/-1e6 extremes; pack ticks n=3 = 146 (vs 181 multiply).
    """
    P = p.put
    P(1, ey, '>'); P(2, ey, 'd')                       # BP>0 -> CW (down=REAL); else straight E
    P(enq_col, ey, 'v')                                # BP==0 path glides E to the ENQ channel
    P(2, ey + 1, '>'); _erow(p, 3, ey + 1, 'M1W{+M`20`W{M')   # (2reg+1)<<20 in A ; cols 3..15
    P(16, ey + 1, 'v'); P(16, ey + 2, '<')
    P(4, ey + 2, 'r'); P(3, ey + 2, '+'); P(2, ey + 2, 'm'); P(1, ey + 2, 'v')   # +v, BP--
    P(1, ey + 3, '>')
    return ey + 3


def pack_slot(p, ey, K=K, OFF=OFF, PAD=PAD, read_col=4):
    """Place ONE base-K pack slot occupying rows ey..ey+3 (VALIDATED, SLOTS.man).

    On entry the man heads EAST at (1,ey) with the partial `reg` in A; on exit reg has
    one more field folded in (reg <- reg*K + (v+OFF) if BP>0, else reg <- reg*K + PAD).
    The value read `r` lands at `read_col` (keep it in the I column-band; keep col-3 clear
    above/below because a backtick there opens a spurious VERTICAL literal — a real hazard
    we hit: 'expected a digit ... found r'). Returns the next slot's entry row (ey+4).
    """
    P = p.put
    P(1, ey, '>')
    x = _erow(p, 2, ey, 'M' + _lit(K) + '*M'); P(x, ey, 'd'); dcol = x   # A=reg*K,B=reg*K
    # REAL branch (BP>0 -> d turns CW = down): read v, +, then +OFF, BP--
    P(dcol, ey + 1, '<'); P(read_col, ey + 1, 'r'); P(2, ey + 1, '+')
    P(1, ey + 1, 'v'); P(1, ey + 2, '>')
    _erow(p, 2, ey + 2, 'M' + _lit(OFF) + '+m'); rc = 2 + len('M' + _lit(OFF) + '+m')
    P(rc, ey + 2, 'v'); P(rc, ey + 3, '<')
    # PAD branch (BP==0 -> straight east): reg <- reg*K + PAD
    x2 = _erow(p, dcol + 1, ey, _lit(PAD) + '+')
    P(x2, ey, 'v'); P(x2, ey + 1, 'v'); P(x2, ey + 2, 'v'); P(x2, ey + 3, '<')
    P(1, ey + 3, 'v')                                   # collector -> next slot entry
    return ey + 4


def unpack_slot_ops(K=K):
    """The op string for ONE bottom-up unpack step (VALIDATED, PURT.man).

    Entry: reg (or running `rest`) in A. Emits the lowest field to the nearest outgoing
    pipe (route it to a SUBOFF relay), leaving `rest = reg//K` in A for the next step.
        M `K` W /   ->  A=rest, B=field      ( `/` gives quotient AND remainder)
        W s W       ->  send field, restore A=rest
    Unroll 3x per register; after 3 steps A=0.
    """
    return ['M', ('lit', K), 'W', '/', 'W', 's', 'W']


def suboff_relay_ops(OFF=OFF, PAD=PAD):
    """Op sketch for the output SUBOFF relay: drop PAD fields, subtract OFF (2-register,
    no stash). Loop:  R M `PAD` - X  [==0 -> discard/loop]  else `OFF` - N s  [emit to O].
    """
    return "R M {pad} - X   {off} - N s".format(pad=_lit(PAD), off=_lit(OFF))


def _erow(p, x, y, s):
    for ch in s:
        p.put(x, y, ch); x += 1
    return x


def build_pack_stage_demo():
    """VALIDATED demo: read n, pack n values (groups of 3, pad the partial last group),
    dump the raw packed register(s). Grades the PACK arithmetic only (SLOTS.man = 27x27).
    Full end-to-end reverse needs the belt + prepend + emit + SUBOFF wiring (see ANALYSIS
    for why the assembled footprint does not beat the board-best)."""
    p = lm.Program(); P = p.put
    P(1, 1, '@'); P(2, 1, 'r'); P(3, 1, 'b'); P(4, 1, '0')
    P(5, 1, 'v'); P(5, 2, '<'); P(1, 2, 'v')
    y = 3
    for _ in range(3):
        y = pack_slot(p, y)
    P(1, y, '>'); P(2, y, 's'); P(3, y, 'H')
    W = max(c[0] for c in p.cells) + 2; HH = y + 2
    p.room(0, 0, W, HH)
    p.input_room(2, -5); p.pipe([(3, -2), (3, -1)])
    p.output_room(1, HH + 2); p.pipe([(2, HH), (2, HH + 1)])
    return p


# ──────────────────────────────────────────────────────────────────────────────
# UPDATE — BIT-OP re-spike (measured): pack logic HALVED, now at the board boundary
# ──────────────────────────────────────────────────────────────────────────────
# The multiply/divide analysis below identified the 7-digit literals (K, OFF) as the
# root cause. The bit-op rebuild (pack_slot_bitop) removes them:
#   * PACK  reg <- (2reg+1)<<20 + v   -- constants 1 and 20 only (bakes +2^20 into the
#     shift). Stash-free. Plus the NO-PAD trick (unwritten high fields are 0; SUBOFF drops
#     field==0). MEASURED pack-logic bbox: 19x14 = box 361, vs multiply 27x13 = box 729
#     (HALVED). Pack ticks n=3 = 146 vs 181.
#   * UNPACK stays on `/` by 2^21 (7-digit literal): `/` is the UNIQUE stash-free peeler
#     (atomic quotient+remainder), and the 7-digit literal loads 2^21 directly into A
#     (a `1<<21` shift-materialization needs BOTH A and B, clobbering reg). Two bit-op
#     unpack ideas were ruled out on the oracle: (a) mask-free top-down peel (reg>>42 ;
#     reg-=F2<<42) yields FORWARD field order (wrong for reversal) AND is not stash-free
#     (the subtract-back needs reg after the shift already consumed it); (b) `& MASK`
#     needs MASK materialized (a shift, clobbering reg). The one 7-digit K in emit can be
#     shared across the 3 fields with a BP=3 loop, so it costs one literal, not three.
#   * Assembled projection (from measured parts): with bit-op pack (~19w) + looped unpack
#     (~18w, one shared K) + a short belt (capacity ~7) + SUBOFF, a compact CTRL is
#     plausibly ~18-20 wide; box ~324-576, avg ticks ~300-500 -> score ~110k-320k. This
#     BEATS our rotate-v3 (1,514,844) by ~5-13x and sits AT THE BOUNDARY of the 109,382
#     board-best: an aggressively compressed assembly (box ~18x18=324, avg <=~340) could
#     just beat it; a looser one lands ~150-320k. NOT YET CONFIRMED — the full assembled
#     reverse (prepend/emit/SUBOFF/round loop-back wiring with 4-pipe column discipline)
#     was validated component-by-component but not completed end-to-end. Verdict upgraded
#     from "does not beat" to "boundary / plausibly beats with full compression".
# ──────────────────────────────────────────────────────────────────────────────
# ANALYSIS — the ORIGINAL multiply/divide version (superseded by the bit-op re-spike)
# ──────────────────────────────────────────────────────────────────────────────
# score = max(w,h)^2 * avg_ticks.  Packing genuinely wins on the two things it targets:
#   * STORAGE: the ring holds <=6 registers, not 16 values -> ring capacity floor drops
#     16 -> 7 (the exact thing dsl.py names as the footprint floor for rotate-v3).
#   * TIME: reversal is over <=6 items, O(6^2) instead of O(16^2); unpack is O(1)/field.
# It LOSES on the thing the projection ignored — the CONTROLLER footprint & per-field cost:
#   * MEASURED: the pack stage ALONE (3 slots, base-K arithmetic with the K/OFF/PAD
#     literals) is 27x27 = box 729 — already LARGER than rotate-v3's entire 625 machine,
#     before adding unpack, the belt, the pump, or the SUBOFF relay.
#   * ROOT CAUSE: BP is write-only, and A/B are consumed by the multiply/add, so the
#     7-digit constants K=2097152 and OFF=1000000 must be re-loaded from literals on EVERY
#     field. Each literal is 9 cells; a slot carries two of them (+PAD). You cannot pin a
#     constant in a register across the loop. This bloats both width and ticks.
#   * MEASURED ticks (single-register, PURT.man): ~34 ticks per value marginal for
#     pack+unpack; the assembled machine adds belt latency + SUBOFF round-trip + prepend.
#
# Realistic assembled numbers (from the measured components):
#   * footprint: pack(27x27) + unpack(similar) + belt/pump/suboff below -> box ~900-1600
#     un-compressed; ~576-729 with aggressive repacking of the literal blocks.
#   * avg ticks over the 8 public cases: ~400-700 (O(n), n_avg ~13 values/case).
#   * score ~ 300k-800k. Beats our rotate-v3 (1,514,844) by ~2x-5x; does NOT approach
#     109,382. To even reach ~110k you would need box<=~260 (16x16) AND avg<=~400
#     simultaneously, but the pack logic alone is 27x27 — that box is unreachable while
#     the K/OFF literals live inside the controller.
#
# The ONLY plausible sub-100k path: OFFLOAD all arithmetic to helper "relay" men so the
# controller loop holds NO literals — an ADDOFF relay on input (v -> v+OFF), a MULK relay
# that returns x*K in transit (so the controller does reg <- MULK; +f with just M+`+`),
# and the SUBOFF relay on output. That removes every literal from the hot controller and
# could shrink it dramatically — but it is a 5-room / 6-pipe machine whose own room +
# pipe footprint is unproven to beat 109,382. Not built here.
#
# VERDICT: register-packing is a real ~2x-5x win over our rotate-v3, and the pack3/unpack
# builders above are reusable, but the projected 20k-60k is not achievable with in-
# controller literals; the board-best 109,382 is NOT beaten by this approach as built.
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = build_pack_stage_demo()
    print(p.render())
    print("pack-stage footprint:", p.footprint())
