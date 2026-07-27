#!/usr/bin/env python3
"""sudoku-validity lanes9: re-encode the mask bit so the addressing rooms shrink,
then run them at H=5 instead of H=7.

Two measurements drove this, both taken on lanes8 (34x34, LAP 70, 3317t):

1. A serpentine's lap is  loop = (H-1)*W = capacity + 3H - 4.  Every extra PAIR
   of interior rows costs 6 ticks of lap for the same op count, and lap is
   exactly what the self-clocking timer has to cover.  lanes8's rooms were H=7.

2. The critical man is COL, not BOX as previously assumed: its lane-2 mask leaves
   at t=61 against box 55 and row 55, because COL stalls waiting for the third
   broadcast value.  That is why `lane2-col-dup@2` is the one case that gates the
   cliff (LAP 66 fails / 68 passes; 68 then fails for an unrelated structural bug
   in the excursion gadget, which is why lanes8 shipped at 70).

Dropping to H=5 costs ~2 columns per room, and rooms may NOT share walls -- the
loader rejects `+----+----+` outright ("pipe interrupted ... found '-'"), so each
room pays its own two walls plus a 1-column gap.  At lanes8's op counts that made
the band 37 wide, i.e. a worse box than lanes8.  The op counts had to come down.

RE-ENCODING.  The mask bit only has to be *some* injection (idx, v) -> bit; it
need not be 9*idx + v.  Using

    bit    = idx + 9*(v-1)          (idx in 0..8, v in 1..9  ->  bit in 0..80)
    shift1 = 54 - bit = 9*(7-v) - idx
    shift2 = ~shift1                (exactly one of the two is in 0..63)

moves the *9 scaling from the idx side to the v side -- and v is broadcast, so
DISPATCH does that multiply once for all three rooms instead of each room doing
it on its own index.  Each room's shift is then a single `-`:

    ROW  r M r r r r - M1{s 1N~M1{s        25 -> 18 ops
    COL  r r r M r r - M1{s 1N~M1{s        25 -> 18 ops
    BOX  r r M3*M r r +M r - M1{s 1N~M1{s  30 -> 23 ops
    DISP 3MrS /S 3MrS /S  r M7-M9* S       14 -> 20 ops

shift1 now spans -26..54, so lane1 never reaches bit 63 and no mask is ever
negative -- strictly safer than lanes8's encoding, which ran up to bit 62.

The cost is 6 extra serial dispatch ops before the last broadcast, which is why
the rooms all stall on w' and land within a tick of each other.  It buys the band
down to 33 columns and the frame to 33x32.
"""
import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
import serp

# ------------------------------------------------------------------ op streams
# bit = idx + 9*(v-1);  shift1 = 9*(7-v) - idx;  w' = 9*(7-v) is broadcast value 5
DISPATCH9 = list("3MrS/S3MrS/SrM7-M9*S")          # r, r/3, c, c/3, 9*(7-v)
TAIL = list("-M1{s1N~M1{s")                        # shift1 -> both lane masks
ROW9 = list("rM") + ["r"] * 4 + TAIL               # idx = value1 (r)
COL9 = list("rrrM") + ["r"] * 2 + TAIL             # idx = value3 (c)
BOX9 = list("rrM3*Mrr+Mr") + TAIL                  # idx = 3*(r/3) + c/3

STRIP3 = [" >v", " Mr", " ~b", "H &", "s^X", "^Xd", " ^<"]
STRIP_DECIDE = 7            # ticks from a strip's `r` to the `s` that emits 0


def strip3(p, x, y):
    for j, row in enumerate(STRIP3):
        for i, ch in enumerate(row):
            if ch != " ":
                p.put(x + i, y + j, ch)


# --------------------------------------------------------------------- timing
def avail_times(DW, DH, pipe_in=2):
    """Tick each broadcast value becomes readable in a room, relative to the
    first broadcast."""
    S = [i for i, c in enumerate(DISPATCH9) if c == "S"]
    return [serp.segment(DW, DH, S[0], i) + pipe_in for i in S]


def walk(ops, W, H, avail):
    """Return (send ticks, send columns, stalls) for one addressing room."""
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


def pad(ops, W, H, avail, min_gap=3, max_pads=6, min_col=0):
    """Insert nop pads so the two lane `s` cells land >= min_gap columns apart,
    minimising (final send tick, -leftmost lane column).

    Two independent insertion points are needed: a serpentine's rows alternate
    direction, so pads before the first `s` and pads between the two `s` cells
    move the exits in opposite directions, and only the pair can both space them
    and keep them off the room's west edge.  Pads that land inside the room's
    stall window are free, and the search finds those on its own.
    """
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
                if len(cols) != 2 or abs(cols[0] - cols[1]) < min_gap:
                    continue
                out.append((sends[-1], k1 + k2, cand, sends, cols, stalls))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def pipe_pair(u1, u2, lo, hi, min_col, min_gap=3):
    """Choose (p_lane1, p_lane2) on the room's bottom wall, columns lo..hi, so
    each lane `s` is STRICTLY nearest its own pipe.  All six outgoing pipe
    sources share a row, so the row term cancels and only |dx| decides; ties go
    by reading order, so strictness is required, not just <=.
    Prefers the pair with the smallest eastmost column, which keeps the gadget
    (width = last strip + 2) as narrow as possible; min_col is what keeps the
    leftmost strip clear of the gadget's init tail."""
    best = None
    for p1 in range(lo, hi + 1):
        for p2 in range(lo, hi + 1):
            if abs(p1 - p2) < min_gap or min(p1, p2) < min_col:
                continue
            if not (abs(u1 - p1) < abs(u1 - p2) and abs(u2 - p2) < abs(u2 - p1)):
                continue
            key = (max(p1, p2), abs(p1 - p2))
            if best is None or key < best[0]:
                best = (key, p1, p2)
    return None if best is None else (best[1], best[2])


# --------------------------------------------------------------------- layout
def build(DW=13, DH=3, RW=8, BW=9, H=5, timer_left=1, timer_lap=46,
          gadget_pad=2, gap=0, DXfix=None):
    p = Program()

    # ---- addressing band: BOX | ROW | COL.  Rooms may not SHARE a wall (the
    # loader cannot parse `+----+----+`) but they may TOUCH, `+----++----+`,
    # which is verified and costs 2 columns less than lanes8's 1-column gaps.
    YA = 7
    # The gadget's init tail needs three clear columns left of the first strip
    # ('@' column, a down column, and the strip's own blank column 0), so the
    # leftmost lane exit must sit at x >= 5.  Offset the whole band to buy that
    # rather than widening it.
    #
    # bx0 -> pcol -> DW -> broadcast timing -> pad choice -> lane columns -> bx0
    # is circular, so settle it by iteration; it converges in two passes.
    # Strip columns are chosen independently of the `s` cells now, so the band no
    # longer has to be shoved east to clear the gadget's init tail: bx0 = 0.
    bx0 = 0
    rx0 = bx0 + BW + 2 + gap
    cx0 = rx0 + RW + 2 + gap
    pbox, prow, pcol = bx0 + BW, rx0 + RW // 2 + 1, cx0 + 1
    DX = pbox - 2 if DXfix is None else DXfix
    DW = max(DW, pcol - DX + 1)
    band_w = cx0 + RW + 2
    assert DX >= 5, ("no margin left of dispatch for INPUT", DX)
    assert DX < pbox and pcol < DX + DW + 1, ("dispatch misses a room",
                                              DX, DW, pbox, pcol)
    avail = avail_times(DW, DH)

    # `s` cells only need distinct columns now (min_gap=1); the >= 3 strip spacing
    # became a constraint on the pipes.  Walk each room's pad variants in
    # send-tick order and take the first that admits a legal pipe pair.
    ROOMS = (("box", BOX9, BW, bx0, 5), ("row", ROW9, RW, rx0, 1),
             ("col", COL9, RW, cx0, 1))
    chosen, lanepipe = {}, {}
    for name, ops9, W, x0, min_col in ROOMS:
        for send, npads, cand, sends, lcols, stalls in pad(ops9, W, H, avail, min_gap=1):
            u1, u2 = x0 + 1 + lcols[0], x0 + 1 + lcols[1]
            pr = pipe_pair(u1, u2, x0 + 1, x0 + W, min_col)
            if pr:
                chosen[name] = (cand, sends, lcols, stalls)
                lanepipe[name] = pr
                break
        assert name in chosen, ("no pipe pair for any pad variant", name)
    box_ops, box_send, box_col, box_stall = chosen["box"]
    row_ops, row_send, row_col, row_stall = chosen["row"]
    col_ops, col_send, col_col, col_stall = chosen["col"]

    p.room(bx0, YA, BW + 2, H + 2)
    p.room(rx0, YA, RW + 2, H + 2)
    p.room(cx0, YA, RW + 2, H + 2)
    bx = serp.place(p, bx0 + 1, YA + 1, BW, H, box_ops)
    rw = serp.place(p, rx0 + 1, YA + 1, RW, H, row_ops)
    cl = serp.place(p, cx0 + 1, YA + 1, RW, H, col_ops)

    p.room(DX, 0, DW + 2, DH + 2)
    serp.place(p, DX + 1, 1, DW, DH, DISPATCH9)
    p.input_room(DX - 5, 0)                  # right wall at DX-3, pipe clear of it
    p.pipe([(DX - 2, 1), (DX - 1, 1)])
    for px in (pbox, prow, pcol):
        p.pipe([(px, DH + 2), (px, YA - 1)])

    # ---- lane exits -> strips.  pad() only sees room-LOCAL columns, so the
    # absolute exits have to come back off the placed serpentines.
    srcy = YA + H + 2
    lane, scol = {}, {}
    for name, pos, ops2 in (("box", bx, box_ops), ("row", rw, row_ops),
                            ("col", cl, col_ops)):
        scol[name] = [pos[i][0] for i, c in enumerate(ops2) if c == "s"]
        lane[name] = list(lanepipe[name])
    cols = sorted(lane["box"] + lane["row"] + lane["col"])
    YG = srcy + 2

    # ---- gadget: return row, fork row, 7 strip rows, 2 timer rows -> 13 outer
    GW = cols[-1] + gadget_pad
    p.room(0, YG, GW, 13)
    R0, R1, R2 = YG + 1, YG + 2, YG + 3
    ix = cols[0] - 4
    assert ix >= 1, ("init tail falls out of the gadget", cols)
    p.put(ix, R0, "@"); p.put(ix + 1, R0, "v")
    for k, ch in enumerate("1NM>"):
        p.put(ix + 1, R1 + k, ch)
    p.put(ix + 2, R1 + 3, "^"); p.put(ix + 2, R1, ">")

    busy = {c for C in cols for c in (C - 2, C - 1, C, C + 1)}
    tfork = max(c for c in range(1, cols[-1] - 1) if c not in busy)
    for C in [c - 1 for c in cols[:-1]] + [tfork]:
        p.put(C, R1, "Y"); p.put(C, R0, ">")
        p.put(C + 1, R0, "v"); p.put(C + 1, R1, ">")
    p.put(cols[-1] - 1, R1, "v")             # survivor drops into the last strip
    for C in cols:
        strip3(p, C - 2, R2)
    for C in cols:
        p.pipe([(C, srcy), (C, YG - 1)])

    # ---- timer.  The two rows under the strips are completely free across the
    # gadget's whole interior, so the timer is a plain rectangle between columns
    # L and E and its lap is 2*(E-L+1) -- tunable in both directions over roughly
    # 10..2*(GW-2).  lanes8 instead had a fixed-length corridor plus an
    # "excursion" detour gadget to lengthen it, and that gadget is what breaks
    # at depth2=1 (LAP 68 fails every public case); nothing like it is needed.
    ty = R2 + 7
    L = timer_left
    E = L + timer_lap // 2 - 1
    assert 1 <= L and E <= GW - 2, ("timer loop leaves the gadget", L, E, GW)
    assert L + 3 < E, ("timer loop too short for its `1 s`", L, E)
    assert L <= tfork <= E, ("timer man lands outside its loop", tfork, L, E)
    p.put(L, ty, ">"); p.put(E, ty, "v")
    p.put(E, ty + 1, "<"); p.put(L, ty + 1, "^")
    p.put(L + 3, ty + 1, "1"); p.put(L + 2, ty + 1, "s")   # row ty+1 runs WEST
    p.put(tfork, ty, ">")                                  # entry joins the loop

    OX = min(18, GW - 4)
    p.pipe([(OX, YG + 13), (OX, YG + 14), (OX + 1, YG + 14)])
    p.output_room(OX + 2, YG + 13)

    decide = max(box_send[-1], row_send[-1], col_send[-1]) + 2 + STRIP_DECIDE
    maxloop = max(serp.loop_len(DW, DH), serp.loop_len(BW, H), serp.loop_len(RW, H))
    ck = dict(cols=cols, row=rw, col=cl, box=bx, tfork=tfork, band=band_w,
              lap=2 * (E - L + 1), pipes=(pbox, prow, pcol),
              ops=dict(row=row_ops, col=col_ops, box=box_ops), lane=lane,
              scol=scol,
              rooms=dict(box=(bx0, BW + 2), row=(rx0, RW + 2), col=(cx0, RW + 2)),
              dispatch=(DX, DW),
              send=dict(row=row_send, col=col_send, box=box_send),
              stall=dict(row=row_stall, col=col_stall, box=box_stall),
              avail=avail, decide=decide, maxloop=maxloop,
              floor=max(decide, maxloop))
    return p, ck


def check(ck):
    cols = ck["cols"]
    assert len(set(cols)) == 6, ("lane exits collided", cols)
    assert all(b - a >= 3 for a, b in zip(cols, cols[1:])), ("3-wide strips", cols)
    # each lane `s` sits exactly above its own pipe; all six pipe sources share a
    # row, so |dx| decides and 0 beats every other pipe.  Distinct columns is
    # therefore the whole requirement.
    # Every lane `s` must be STRICTLY nearest its own pipe.  All six outgoing pipe
    # sources share a row, so the row term cancels and only |dx| matters; a tie
    # would silently go to the leftmost pipe by reading order.
    for name in ("row", "col", "box"):
        u = ck["scol"][name]
        p = ck["lane"][name]
        assert len(set(u)) == 2, (name, "both lanes send from one column", u)
        for i in (0, 1):
            own, other = abs(u[i] - p[i]), abs(u[i] - p[1 - i])
            assert own < other, (name, "lane", i, "binds the wrong pipe", u, p)
            for q in cols:                      # and no third pipe is nearer
                if q not in p:
                    assert own < abs(u[i] - q), (name, "lane", i, "steals", q)
    for name, px in zip(("box", "row", "col"), ck["pipes"]):
        x0, w = ck["rooms"][name]
        assert x0 < px < x0 + w - 1, ("incoming pipe misses its room", name, px, x0, w)
    DX, DW = ck["dispatch"]
    for px in ck["pipes"]:                     # and every drop leaves dispatch's
        assert DX < px < DX + DW + 1, ("pipe not under dispatch", px, DX, DW)
    forks = sorted([c - 1 for c in cols[:-1]] + [ck["tfork"]])
    assert len(set(forks)) == len(forks), ("duplicate fork column", forks)
    for a, b in zip(forks, forks[1:]):
        assert b - a >= 2, ("adjacent forks: Y eats the return >", forks)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dw", type=int, default=13)
    ap.add_argument("--rw", type=int, default=8)
    ap.add_argument("--bw", type=int, default=9)
    ap.add_argument("--rh", type=int, default=5)
    ap.add_argument("--timer-left", type=int, default=1)
    ap.add_argument("--lap", type=int, default=46)
    ap.add_argument("--dx", type=int, default=None)
    ap.add_argument("--gadget-pad", type=int, default=2)
    ap.add_argument("-o", "--out", default="lanes9.man")
    a = ap.parse_args()
    p, ck = build(DW=a.dw, RW=a.rw, BW=a.bw, H=a.rh, timer_lap=a.lap,
                  timer_left=a.timer_left, gadget_pad=a.gadget_pad, DXfix=a.dx)
    check(ck)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), a.out)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"], "LAP", ck["lap"])
    print("   avail=%s  decide=%d  maxloop=%d  LAP floor ~%d" % (
        ck["avail"], ck["decide"], ck["maxloop"], ck["floor"]))
    for n in ("row", "col", "box"):
        print("   %-3s %2d ops sends=%s stalls=%s" % (
            n, len(ck["ops"][n]), ck["send"][n], ck["stall"][n]))
