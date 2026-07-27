"""sudoku-validity w2: the gadget's storage cell shrinks from 7 rows to 5, and the
output room is tucked with a 3-cell L pipe instead of a 2-cell straight one.

lanes11 is 30x30 (box 900).  Both dimensions bind, and both are driven by one
structure each:

  * HEIGHT 30 = dispatch 5 + gap 2 + band 8 + gap 2 + gadget 13, and the gadget's
    13 = 2 walls + fork-return + fork-row + STRIP3's SEVEN rows + timer 2.
  * WIDTH  30 = max(band 27, dispatch 5+23+2, gadget GW + 5).  The +5 is the O
    room hung east of the gadget on a straight 2-cell pipe: pipe 2 + room 3.

STRIP3 is 7 rows because it runs lanes11's INVERTED mask polarity (mask starts at
-1, a used bit is XOR-cleared).  That makes the update free -- on the valid path
`&` already leaves A = bit -- but it makes "this lane is not selected" (bit == 0)
indistinguishable from a collision, so it needs a SECOND branch on BP and a third
return lane.  Positive polarity (mask starts at 0, `|`-set) folds the unselected
case into the valid case for free, at the price of needing the bit twice; agg2's
TAIL already sends every mask twice (`-M1{ss0-M1{ss`), so the price is one op.

    3 cols x 5 rows, pipe column P, c0/c1/c2 = P-2/P-1/P:

        c0   c1   c2          cyclic ops:  r & X r | M
    y0:  >    >    v          entry: fork's south copy lands on (c0,y0)
    y1:       s    r          collision exit: X -> W -> ^ 0 s -> '>' rejoins
    y2:  M    0    &
    y3:  |    ^    X
    y4:  ^    r    <

  A = bit & mask is 0 when the bit is free OR the lane is unselected, and > 0
  exactly on a collision, so ONE `X` classifies the round.  `0 s` then reports and
  the man walks back onto (c1,y0)='>' -- a no-op for the ring man travelling east,
  a rejoin for the reporter travelling north -- so no `H` and no extra row.
  STRIP_DECIDE drops 7 -> 5 as a side effect.

  Both `r` cells are within 1 column of P and the ring is 3 wide, so the pipe
  pitch stays 3: strips tile the band with no gap, exactly as STRIP3 did.  The
  ring hangs WEST of its pipe rather than astride it, which costs nothing in
  binding and gives the gadget back its last interior column.

O TUCK: the source cell may turn at the very next cell, so
`[(GW,ty+1), (GW+1,ty+1), (GW+1,ty)]` is a legal 3-cell L that enters the output
room's BOTTOM wall.  The room then sits at columns GW..GW+2 instead of
GW+2..GW+4 -- width GW+3 instead of GW+5 -- inside the gadget's own rows.

2-ROW DISPATCH RING (--ring): see ring2() below.  Saves the fifth dispatch row.

MEASURED, and this is the point of the file: box 784 is a FLOOR for the whole
speculative-timer family, and it is set by the timer, not by the storage cell.

    build_w2.py --ring            ->  w2.man   29x27  box 841  2280t  1,917,760
                                       6/6 oracle, 377/377 gate

  * lap 48 is the measured cliff (377/377).  lap 46 fails 26 gate cases, all of
    them `col-*` lane-2; lap 44 fails 79; lap 42 fails 104.  Every failure is a
    duplicate delivered at ROUND 2 -- the lane-2 cases with the duplicate after a
    long valid prefix pass at lap 44.  It is a STARTUP transient: the band's men
    come from one `@` plus two forks walking east along the fork row, so the
    right-hand loop's man is born ~19 ticks after the left-hand one and is still
    one lap behind when round 2 arrives.  `grade_fast` 6/6 does not see any of
    this -- w2q42.man is 27x27 / 6-6 public and fails 104 gate cases.
  * the 2-row timer occupies lap/2 columns of the gadget, the output room needs
    3 more beside it, so WIDTH >= lap/2 + 5 = 29 at lap 48, 28 at lap 46.
  * folding the timer to 3 rows (a comb: 2W + 2d cells, d dips of 2 columns,
    so lap <= 3W-5) decouples width from lap and gives width 27 -- but it costs
    the row back, so height goes 27 -> 28 and the box is 784 either way.
  * HEIGHT floor is 27 = dispatch 4 + gap 2 + band 8 + gap 2 + gadget 11, and
    the gadget's 11 = 2 walls + fork-return + fork-row + strip 5 + timer 2.
  * WIDTH floor is 27 = MW = 2 + BW + 2*RW with BW=9, RW=8 forced by capacity.
  Beating 784 needs MW <= 26 AND a 10-row gadget AND lap <= 44, all at once.

The three parts here that ARE reusable and did not exist before:
  * the 5-row positive-polarity storage ring (STRIP3 was 7);
  * the 3-cell L output tuck (width GW+3 instead of GW+5);
  * ring2(), a 2-row dispatch ring one row shorter than serp(W,3).
"""

import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
import serp

FORCE = bool(os.environ.get("W2_FORCE"))

# `%` and every arithmetic op except `/` LEAVE B UNCHANGED, so one `3 M` at the
# top can serve BOTH divisions if the first of them is a `%`.  Broadcasting r%3
# instead of r/3 therefore drops the second `3 M` -- 20 dispatch ops -> 18 -- and
# BOX rebuilds 3*(r/3) as r - r%3 in the same 11 ops it used before.
#   bcast: r, r%3, c, c/3, 9*(7-v)
# `%` and every arithmetic op except `/` leave B unchanged, so ONE `3 M` at the
# top serves both divisions provided the first of them is a `%`.  Broadcasting
# r%3 instead of r/3 drops the second `3 M`: 20 dispatch ops -> 18, and BOX
# rebuilds 3*(r/3) as r - r%3 in the same 11 ops.  bcast: r, r%3, c, c/3, 9*(7-v)
DISPATCH9 = list("3MrS%SrS/SrM7-M9*S")
TAIL = list("-M1{ss0-M1{ss")                       # each mask goes out TWICE
ROW9 = list("rM") + ["r"] * 4 + TAIL
COL9 = list("rrrM") + ["r"] * 2 + TAIL
BOX9 = list("rMrN+Mrr+Mr") + TAIL                  # idx = (r - r%3) + c/3

STRIP_ROWS = 5
STRIP_DECIDE = 5            # ticks from the strip's 1st `r` to the `s` that emits 0


def strip(p, P, y):
    """positive-polarity 3x5 branch ring; P is the pipe column (RIGHT edge).
    Hanging the ring west of its pipe instead of astride it costs nothing in
    binding -- the 2nd `r` is 1 column west, and 2 > 1 still beats the
    neighbouring pipe 3 away -- and saves the gadget its last interior
    column, which is what carries width from 28 down to 27."""
    c0, c1, c2 = P - 2, P - 1, P
    p.put(c0, y + 0, ">"); p.put(c1, y + 0, ">"); p.put(c2, y + 0, "v")
    p.put(c2, y + 1, "r")                       # 1st copy of the bit
    p.put(c2, y + 2, "&")                       # A = bit & mask
    p.put(c2, y + 3, "X")                       # >0 -> collision (turn west)
    p.put(c2, y + 4, "<")
    p.put(c1, y + 4, "r")                       # 2nd copy
    p.put(c0, y + 4, "^")
    p.put(c0, y + 3, "|")                       # A = bit | mask
    p.put(c0, y + 2, "M")                       # mask := A
    p.put(c1, y + 3, "^"); p.put(c1, y + 2, "0"); p.put(c1, y + 1, "s")


# ------------------------------------------------------- 2-row dispatch ring
# serp needs H odd, so the smallest dispatch room it can draw is 5 rows tall, and
# its interior row 0 carries nothing but `@` and `v`.  A plain 2-row ring with the
# `@` OFF the cycle costs 4 rows for the same 2W-5 op slots and a cycle 2 ticks
# SHORTER -- and, because the ops still sit on one straight row until it fills,
# the broadcast times are identical to serp's at the same capacity.
#
#     @ > o o o o v        interior (0,0)..(W-1,1); '@' is entered once and left
#       ^ o o o o <        the loop is (1..W-1, 0) then (W-1..1, 1), length 2(W-1)
#
# (1,0) MUST be the '>' that catches the northbound return: an op cell there would
# leave the man still heading north, into the top wall.  (0,1) is unused.
def ring2(W):
    g = {(0, 0): "@", (1, 0): ">", (W - 1, 0): "v", (W - 1, 1): "<", (1, 1): "^"}
    slots = [(x, 0) for x in range(2, W - 1)] + [(x, 1) for x in range(W - 2, 1, -1)]
    t = {}
    for x in range(1, W):
        t[(x, 0)] = x - 1
    for x in range(W - 1, 0, -1):
        t[(x, 1)] = 2 * W - 2 - x
    return slots, g, t


def ring2_place(p, x0, y0, W, ops):
    slots, g, _ = ring2(W)
    assert len(ops) <= len(slots), (len(ops), len(slots))
    for (dx, dy), ch in g.items():
        p.put(x0 + dx, y0 + dy, ch)
    for i, (dx, dy) in enumerate(slots):
        p.put(x0 + dx, y0 + dy, ops[i] if i < len(ops) else " ")


# --------------------------------------------------------------------- timing
def avail_times(DW, DH, pipe_in=2, ring=False):
    S = [i for i, c in enumerate(DISPATCH9) if c == "S"]
    if ring:
        slots, _, t = ring2(DW)
        return [t[slots[i]] - t[slots[S[0]]] + pipe_in for i in S]
    return [serp.segment(DW, DH, S[0], i) + pipe_in for i in S]


def walk(ops, W, H, avail):
    t, k, stalls, sends, cols = 0, 0, [], [], []
    slots = serp.serp(W, H)[0]
    for i, c in enumerate(ops):
        if i:
            t += serp.segment(W, H, i - 1, i)
        if c == "r":
            stalls.append(max(0, avail[k] - t)); t = max(t, avail[k]); k += 1
        elif c == "s":
            sends.append(t); cols.append(slots[i][0])
    return sends, cols, stalls


def pad(ops, W, H, avail, max_pads=6):
    first_s = ops.index("s")
    cap = serp.capacity(W, H)
    out = []
    for k1 in range(max_pads + 1):
        for k2 in range(max_pads + 1 - k1):
            if len(ops) + k1 + k2 > cap:
                continue
            for p1 in range(first_s + 1):
                cand = (ops[:p1] + [" "] * k1 + ops[p1:first_s]
                        + [" "] * k2 + ops[first_s:])
                sends, cols, stalls = walk(cand, W, H, avail)
                if len(cols) != 4:
                    continue
                out.append((sends[-1], k1 + k2, cand, sends, cols, stalls))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


# ------------------------------------------------------------------- binding
def nearest_map(us, ps):
    out = []
    for u in us:
        d = sorted((abs(u - p), p) for p in ps)
        if len(d) > 1 and d[0][0] == d[1][0]:
            return None
        out.append(d[0][1])
    return out


def solve_out(scols, lo, hi, min_col, min_gap=3, min_last=0):
    best = None

    def rec(chosen, start):
        nonlocal best
        if len(chosen) == 6:
            if chosen[-1] < min_last:
                return
            m = nearest_map(scols, chosen)
            if (m and all(m[i] == m[i + 1] for i in range(0, 12, 2))
                    and len(set(m)) == 6):
                if best is None or chosen[-1] < best[0][-1]:
                    best = (list(chosen), m)
            return
        need = (6 - len(chosen) - 1) * min_gap
        for c in range(start, hi - need + 1):
            if best is not None and c > best[0][-1]:
                break
            rec(chosen + [c], c + min_gap)

    rec([], max(lo, min_col))
    return best


def solve_in(rcols, lo, hi, min_col, min_gap=2):
    names = list(rcols)
    flat = [(n, u) for n in names for u in sorted(rcols[n])]
    best = None
    for a in range(max(lo, min_col), hi + 1):
        for b in range(a + min_gap, hi + 1):
            for c in range(b + min_gap, hi + 1):
                ps = [a, b, c]
                m = nearest_map([u for _, u in flat], ps)
                if not m:
                    continue
                want = dict(zip(names, ps))
                if all(m[i] == want[flat[i][0]] for i in range(len(flat))):
                    if best is None or (c - a) < (best[2] - best[0]):
                        best = ps
    return best


# --------------------------------------------------------------------- layout
def build(DW=20, DH=3, RW=8, BW=9, H=5, timer_left=1, timer_lap=48, DXfix=5,
          ring=False, KEEP=12, order="brc", MINCOL=4):
    p = Program()
    DROWS = 4 if ring else DH + 2          # dispatch room height
    YA = DROWS + 2
    MW = 2 + BW + RW + RW
    NAME = {"b": "box", "r": "row", "c": "col"}
    seq = [NAME[ch] for ch in order]
    wd = {"box": BW, "row": RW, "col": RW}
    ox, _x = {}, 1
    for n in seq:
        ox[n] = _x; _x += wd[n]
    OPS = {"box": BOX9, "row": ROW9, "col": COL9}
    DX = DXfix
    avail = avail_times(DW, DH, ring=ring)
    L = timer_left
    E = L + timer_lap // 2 - 1

    cands = {}
    for n in OPS:
        seen, keep = set(), []
        for send, npads, cand, sends, lcols, stalls in pad(OPS[n], wd[n], H, avail):
            key = tuple(lcols)
            if key in seen:
                continue
            seen.add(key)
            keep.append((send, cand, sends, lcols, stalls))
        cands[n] = keep[:KEEP]
        assert keep, ("no pad variant for", n)

    best = None
    for cb in cands["box"]:
        for cr in cands["row"]:
            for cc in cands["col"]:
                pick = {"box": cb, "row": cr, "col": cc}
                scols, rcols = [], {}
                ok = True
                for n in ("box", "row", "col"):
                    slots = serp.serp(wd[n], H)[0]
                    ops2 = pick[n][1]
                    if len(ops2) > len(slots):
                        ok = False
                        break
                    scols += [ox[n] + slots[i][0]
                              for i, ch in enumerate(ops2) if ch == "s"]
                    rcols[n] = {ox[n] + slots[i][0]
                                for i, ch in enumerate(ops2) if ch == "r"}
                if not ok:
                    continue
                # leftmost strip needs cols 1..3 free for '@', the timer fork and
                # its return `>`, so the first pipe column is at least 5.
                so = solve_out(scols, 1, MW - 2, MINCOL, min_gap=3, min_last=E)   # GW = cols[-1]+2, timer needs E <= GW-2
                if not so:
                    continue
                cols = sorted(so[0])
                si = solve_in(rcols, 1, MW - 2, DX + 1)
                if not si:
                    continue
                if not (DX < min(si) and max(si) < DX + DW + 1):
                    continue
                width = max(MW, DX + DW + 2, cols[-1] + 5)
                # the strip decides off the FIRST copy of the last mask, which is
                # sends[-2]; sends[-1] is the duplicate the `|` update consumes.
                decide = max(pick[n][2][-2] for n in pick) + 2 + STRIP_DECIDE
                key = (width, decide)
                if best is None or key < best[0]:
                    best = (key, pick, scols, cols, so[1], si)
    assert best, "no geometry satisfies both bindings"
    _, pick, scols, cols, lanepipe, inpipe = best

    # ---- addressing band (unchanged from lanes11 apart from the longer TAIL)
    p.room(0, YA, MW, H + 3)
    pos, before = {}, dict(p.cells)
    for n in ("box", "row", "col"):
        pos[n] = serp.place(p, ox[n], YA + 2, wd[n], H, pick[n][1])
    for (x, y), ch in p.cells.items():
        if (x, y) in before and before[(x, y)] != ch and before[(x, y)] != " ":
            raise AssertionError(("loops collided at", x, y))

    order = list(seq)
    R0, R1 = YA + 1, YA + 2
    for n in order:
        p.put(ox[n], R1, " ")
    p.put(ox[order[0]], R1, "@")
    for n in order[:-1]:
        c = ox[n] + 1
        p.put(c, R1, "Y"); p.put(c, R0, ">")
        p.put(c + 1, R0, "v"); p.put(c + 1, R1, ">")
    p.put(ox[order[-1]] + 1, R1, "v")

    # ---- dispatch + input
    p.room(DX, 0, DW + 2, DROWS)
    if ring:
        ring2_place(p, DX + 1, 1, DW, DISPATCH9)
    else:
        serp.place(p, DX + 1, 1, DW, DH, DISPATCH9)
    assert DX >= 5, ("no margin left of dispatch for INPUT", DX)
    p.input_room(DX - 5, 0)
    p.pipe([(DX - 2, 1), (DX - 1, 1)])
    inmap = dict(zip(("box", "row", "col"), inpipe))
    for px in inpipe:
        p.pipe([(px, DROWS), (px, YA - 1)])

    # ---- gadget: fork-return, fork row, 5 strip rows, 2 timer rows
    srcy = YA + H + 3
    YG = srcy + 2
    GW = cols[-1] + 2
    GH = 4 + STRIP_ROWS + 2
    p.room(0, YG, GW, GH)
    G0, G1, G2 = YG + 1, YG + 2, YG + 3
    ty = G2 + STRIP_ROWS
    assert ty + 1 == YG + GH - 2, (ty, YG, GH)

    # the timer man descends a column that no strip occupies; that column also
    # carries his Y in the fork row, so it must keep the fork chain >= 2 apart.
    busy = {c for C in cols for c in (C - 2, C - 1, C)}
    sforks = [C - 2 for C in cols]
    tcand = [t for t in range(2, cols[-1])
             if t not in busy and t >= L and t <= E
             and all(abs(t - f) >= 2 for f in sforks)]
    assert tcand, ("no free column for the timer descent", cols)
    tfork = tcand[0]
    p.put(1, G1, "@")
    for c in sorted([tfork] + sforks[:-1]):
        p.put(c, G1, "Y"); p.put(c, G0, ">")
        p.put(c + 1, G0, "v"); p.put(c + 1, G1, ">")
    p.put(sforks[-1], G1, "v")
    forks = sorted([tfork] + sforks)
    assert all(b - a >= 2 for a, b in zip(forks, forks[1:])), forks
    assert forks[0] >= 2, ("no room for the gadget '@' west of the first fork", forks)

    for C in cols:
        strip(p, C, G2)
    for C in cols:
        p.pipe([(C, srcy), (C, YG - 1)])

    # ---- speculative timer, same rectangle loop lanes11 uses
    assert 1 <= L and E <= GW - 2, ("timer loop leaves the gadget", L, E, GW)
    assert L + 3 < E and L <= tfork <= E, ("timer geometry", L, E, tfork)
    p.put(L, ty, ">"); p.put(E, ty, "v")
    p.put(E, ty + 1, "<"); p.put(L, ty + 1, "^")
    p.put(L + 3, ty + 1, "1"); p.put(L + 2, ty + 1, "s")
    p.put(tfork, ty, ">")

    # ---- O tucked beside the gadget on a 3-cell L into its BOTTOM wall
    p.pipe([(GW, ty + 1), (GW + 1, ty + 1), (GW + 1, ty)])
    p.output_room(GW, ty - 3)

    decide = max(pick[n][2][-2] for n in pick) + 2 + STRIP_DECIDE
    ck = dict(cols=cols, pos=pos, ops={n: pick[n][1] for n in pick},
              send={n: pick[n][2] for n in pick}, scols=scols,
              lane=dict(zip(scols, lanepipe)), inpipe=inmap, ox=ox, wd=wd, H=H,
              lap=2 * (E - L + 1), decide=decide, MW=MW, GW=GW, tfork=tfork,
              maxloop=max([2 * DW - 2 if ring else serp.loop_len(DW, DH)]
                          + [serp.loop_len(wd[n], H) for n in wd]))
    return p, ck


def check(ck):
    cols = ck["cols"]
    assert len(set(cols)) == 6 and all(b - a >= 3 for a, b in zip(cols, cols[1:])), cols
    for n in ("box", "row", "col"):
        slots = serp.serp(ck["wd"][n], ck["H"])[0]
        xs = [ck["ox"][n] + slots[i][0]
              for i, c in enumerate(ck["ops"][n]) if c == "s"]
        assert len(xs) == 4, (n, xs)
        for u in xs:
            own = ck["lane"][u]
            d = sorted((abs(u - q), q) for q in cols)
            assert d[0][1] == own and d[0][0] < d[1][0], (n, "s", u, "binds", d[:2])
    ps = list(ck["inpipe"].values())
    for n in ("box", "row", "col"):
        slots = serp.serp(ck["wd"][n], ck["H"])[0]
        for i, c in enumerate(ck["ops"][n]):
            if c != "r":
                continue
            u = ck["ox"][n] + slots[i][0]
            d = sorted((abs(u - q), q) for q in ps)
            assert d[0][1] == ck["inpipe"][n] and d[0][0] < d[1][0], \
                (n, "r", u, "binds", d[:2])
    if not FORCE:
        assert ck["decide"] < ck["lap"], ("timer cliff", ck["decide"], ck["lap"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dw", type=int, default=20)
    ap.add_argument("--dh", type=int, default=3)
    ap.add_argument("--dx", type=int, default=5)
    ap.add_argument("--rw", type=int, default=8)
    ap.add_argument("--bw", type=int, default=9)
    ap.add_argument("--rh", type=int, default=5)
    ap.add_argument("--timer-left", type=int, default=1)
    ap.add_argument("--lap", type=int, default=48)
    ap.add_argument("--ring", action="store_true")
    ap.add_argument("--keep", type=int, default=12)
    ap.add_argument("--order", default="brc")
    ap.add_argument("-o", "--out", default="w2.man")
    a = ap.parse_args()
    p, ck = build(DW=a.dw, DH=a.dh, DXfix=a.dx, RW=a.rw, BW=a.bw, H=a.rh,
                  timer_left=a.timer_left, timer_lap=a.lap, ring=a.ring, KEEP=a.keep, order=a.order)
    check(ck)
    out = a.out if os.path.isabs(a.out) else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), a.out)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"], "LAP", ck["lap"])
    print("   room %dw gadget %dw in-pipes %s decide=%d maxloop=%d" % (
        ck["MW"], ck["GW"], ck["inpipe"], ck["decide"], ck["maxloop"]))
