"""sudoku-validity lanes11: ONE addressing room holding three men, and the output
room tucked beside the gadget instead of under it.

lanes10 kept BOX/ROW/COL as three touching rooms.  They are pure compute and hold
no state, so they can share a single room: three disjoint serpentine loops, three
`@` cells, three incoming pipes (dispatch already `S`-broadcasts, so no extra
sends) and six outgoing.  That reclaims the four interior wall columns.

The reclaimed columns are worth nothing by themselves -- lanes10 was 31 wide x 32
tall, so the box was already 32^2 with a spare column.  What makes the merge pay
is second-order: with ONE room, the six lane pipes all leave ONE bottom wall that
spans the whole band, so their columns are free instead of being confined to a
single room's span.  Pulling them west shrinks the gadget (width = last strip + 2)
until the OUTPUT room fits beside it, in the gadget's own rows, rather than in
three extra rows underneath.  Height 32 -> 29, and 29 is then the box driver.

    dispatch 5 + pipe 2 + band 7 + pipe 2 + gadget 13 + O 3  = 32   (lanes10)
    dispatch 5 + pipe 2 + band 8 + pipe 2 + gadget 13        = 30   (lanes11)

A room may hold at most ONE `@` ("room has multiple '@'s" is a load error), so the
three men come from one `@` plus two `Y` forks.  That distribution is free of
extra geometry because a serpentine's own row 0 is almost empty -- serp writes
only (0,0)='@' and (1,0)='v' there -- so row 0 doubles as the fork row and only a
single return row has to be added above it:

    YA+1   > v         > v            <- fork return row (new)
    YA+2   @ Y . . . . . Y . . . . v  <- serp row 0 of all three loops
    YA+3.. the three loop bodies

A fork's south copy lands on the loop's own entry `>` travelling south, exactly as
the gadget's strip forks do; its north copy lands on the return row's `>`.  The
last loop needs no fork, just the `v` serp already puts there.  Net cost: 1 row
against 4 columns reclaimed.

BINDING is the whole risk, and it got harder, not easier: every `r` now competes
with all three incoming pipes and every `s` with all six outgoing ones.  All
pipes of a direction share a row, so the row term cancels and only |dx| decides,
with ties going to the leftmost by reading order.  The three loops occupy
disjoint column ranges, so the incoming pipes just need their Voronoi boundaries
to fall in the gaps between those ranges; the outgoing six need each `s` strictly
inside its own pipe's cell.  solve_out()/solve_in() search for that and check()
re-verifies it cell by cell against the placed grid.

Band height stays 7: H=3 would cut two rows but needs capacity (H-1)*W - 3H + 4
= 2W-5 per loop, i.e. interiors 12+12+14 = 38 against the 22-25 that H=5 needs,
so the merged room would be 40 wide and the box would go the wrong way.
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



# ------------------------------------------------------------------- binding
def nearest_map(us, ps):
    """Map each column in `us` to its strictly-nearest column in `ps`.
    All pipes of one direction share a row, so the row term cancels and only
    |dx| decides; a tie would silently go to the leftmost pipe by reading order,
    so a tie is treated as failure.  Returns None unless the map is a bijection."""
    out = []
    for u in us:
        d = sorted((abs(u - p), p) for p in ps)
        if len(d) > 1 and d[0][0] == d[1][0]:
            return None                        # tie -> reading order, not ours
        out.append(d[0][1])
    return out


def solve_out(scols, lo, hi, min_col, min_gap=3, min_last=0):
    """Pick six outgoing pipe columns so the six lane `s` cells map onto them
    bijectively and strictly.  Prefers the smallest eastmost column, because the
    gadget is `last strip + 2` wide and the output room now sits beside it."""
    best = None

    def rec(chosen, start):
        nonlocal best
        if len(chosen) == 6:
            if chosen[-1] < min_last:
                return
            m = nearest_map(scols, chosen)
            if m and len(set(m)) == 6:
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
    """Pick one incoming pipe column per loop so every `r` cell of that loop is
    strictly nearest its own.  The three loops hold disjoint column ranges, so
    this is just asking the Voronoi boundaries to land in the gaps between them."""
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
def build(DW=23, DH=3, RW=8, BW=9, H=5, timer_left=1, timer_lap=46, DXfix=5):
    p = Program()
    YA = 7
    MW = 2 + BW + RW + RW                      # ONE room, three disjoint loops
    ox = {"box": 1, "row": 1 + BW, "col": 1 + BW + RW}
    wd = {"box": BW, "row": RW, "col": RW}
    OPS = {"box": BOX9, "row": ROW9, "col": COL9}

    DX = DXfix
    avail = avail_times(DW, DH)

    # one pad variant per distinct pair of `s` columns, cheapest send first
    cands = {}
    for n in OPS:
        seen, keep = set(), []
        for send, npads, cand, sends, lcols, stalls in pad(OPS[n], wd[n], H, avail,
                                                           min_gap=1):
            key = tuple(lcols)
            if key in seen:
                continue
            seen.add(key)
            keep.append((send, cand, sends, lcols, stalls))
        cands[n] = keep[:10]

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
                    scols += [ox[n] + slots[i][0] for i, ch in enumerate(ops2) if ch == "s"]
                    rcols[n] = {ox[n] + slots[i][0]
                                for i, ch in enumerate(ops2) if ch == "r"}
                if not ok:
                    continue
                # the init tail needs three columns west of the first strip
                so = solve_out(scols, 1, MW - 2, 5,
                               min_last=timer_left + timer_lap // 2 - 1)
                if not so:
                    continue
                cols = sorted(so[0])
                si = solve_in(rcols, 1, MW - 2, DX + 1)
                if not si:
                    continue
                if not (DX < min(si) and max(si) < DX + DW + 1):
                    continue
                width = max(MW, DX + DW + 2, cols[-1] + 7)
                decide = max(pick[n][2][-1] for n in pick) + 2 + STRIP_DECIDE
                key = (width, decide)
                if best is None or key < best[0]:
                    best = (key, pick, scols, cols, so[1], si)
    assert best, "no merged geometry satisfies both bindings"
    _, pick, scols, cols, lanepipe, inpipe = best

    # ---- draw
    p.room(0, YA, MW, H + 3)          # +1 interior row for the fork return lane
    pos, before = {}, dict(p.cells)
    for n in ("box", "row", "col"):
        pos[n] = serp.place(p, ox[n], YA + 2, wd[n], H, pick[n][1])
    for (x, y), ch in p.cells.items():
        if (x, y) in before and before[(x, y)] != ch and before[(x, y)] != " ":
            raise AssertionError(("loops collided at", x, y))

    # ---- one `@`, two `Y` forks: three men into three loops.
    order = ["box", "row", "col"]
    R0, R1 = YA + 1, YA + 2           # fork return row, serp row 0
    for n in order:
        p.put(ox[n], R1, " ")         # drop each loop's own '@'
    p.put(ox[order[0]], R1, "@")      # exactly one man in the room
    for n in order[:-1]:              # fork: south copy -> this loop, north -> on
        c = ox[n] + 1
        p.put(c, R1, "Y"); p.put(c, R0, ">")
        p.put(c + 1, R0, "v"); p.put(c + 1, R1, ">")
    p.put(ox[order[-1]] + 1, R1, "v")  # survivor drops into the last loop

    p.room(DX, 0, DW + 2, DH + 2)
    serp.place(p, DX + 1, 1, DW, DH, DISPATCH9)
    assert DX >= 5, ("no margin left of dispatch for INPUT", DX)
    p.input_room(DX - 5, 0)
    p.pipe([(DX - 2, 1), (DX - 1, 1)])
    inmap = dict(zip(("box", "row", "col"), inpipe))
    for px in inpipe:
        p.pipe([(px, DH + 2), (px, YA - 1)])

    srcy = YA + H + 3
    YG = srcy + 2
    GW = cols[-1] + 2
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
    p.put(cols[-1] - 1, R1, "v")
    for C in cols:
        strip3(p, C - 2, R2)
    for C in cols:
        p.pipe([(C, srcy), (C, YG - 1)])

    ty = R2 + 7
    L = timer_left
    E = L + timer_lap // 2 - 1
    assert 1 <= L and E <= GW - 2, ("timer loop leaves the gadget", L, E, GW)
    assert L + 3 < E and L <= tfork <= E, ("timer geometry", L, E, tfork)
    p.put(L, ty, ">"); p.put(E, ty, "v")
    p.put(E, ty + 1, "<"); p.put(L, ty + 1, "^")
    p.put(L + 3, ty + 1, "1"); p.put(L + 2, ty + 1, "s")
    p.put(tfork, ty, ">")

    # ---- O BESIDE the gadget, in the gadget's own rows: saves the three rows
    # lanes10 spent underneath it, which is what the merge is really buying.
    p.pipe([(GW, ty + 1), (GW + 1, ty + 1)])
    p.output_room(GW + 2, ty)

    decide = max(pick[n][2][-1] for n in pick) + 2 + STRIP_DECIDE
    ck = dict(cols=cols, pos=pos, ops={n: pick[n][1] for n in pick},
              send={n: pick[n][2] for n in pick}, scols=scols,
              lane=dict(zip(scols, lanepipe)), inpipe=inmap, ox=ox, wd=wd, H=H,
              lap=2 * (E - L + 1), decide=decide, MW=MW, GW=GW, tfork=tfork,
              maxloop=max([serp.loop_len(DW, DH)]
                          + [serp.loop_len(wd[n], H) for n in wd]))
    return p, ck


def check(ck):
    cols = ck["cols"]
    assert len(set(cols)) == 6 and all(b - a >= 3 for a, b in zip(cols, cols[1:])), cols
    # outgoing: every lane `s` strictly nearest its own pipe, among ALL six
    for n in ("box", "row", "col"):
        slots = serp.serp(ck["wd"][n], ck["H"])[0]
        xs = [ck["ox"][n] + slots[i][0]
              for i, c in enumerate(ck["ops"][n]) if c == "s"]
        assert len(set(xs)) == 2, (n, "both lanes send from one column", xs)
        for u in xs:
            own = ck["lane"][u]
            d = sorted((abs(u - q), q) for q in cols)
            assert d[0][1] == own and d[0][0] < d[1][0], (n, "s", u, "binds", d[:2])
    # incoming: every `r` strictly nearest its own room's pipe, among ALL three
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
    forks = sorted([c - 1 for c in cols[:-1]] + [ck["tfork"]])
    assert len(set(forks)) == len(forks)
    for a, b in zip(forks, forks[1:]):
        assert b - a >= 2, ("adjacent forks: Y eats the return >", forks)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dw", type=int, default=23)
    ap.add_argument("--dx", type=int, default=5)
    ap.add_argument("--rw", type=int, default=8)
    ap.add_argument("--bw", type=int, default=9)
    ap.add_argument("--rh", type=int, default=5)
    ap.add_argument("--timer-left", type=int, default=1)
    ap.add_argument("--lap", type=int, default=46)
    ap.add_argument("-o", "--out", default="lanes11.man")
    a = ap.parse_args()
    p, ck = build(DW=a.dw, DXfix=a.dx, RW=a.rw, BW=a.bw, H=a.rh,
                  timer_left=a.timer_left, timer_lap=a.lap)
    check(ck)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), a.out)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"], "LAP", ck["lap"])
    print("   room %dw  gadget %dw  in-pipes %s  decide=%d maxloop=%d" % (
        ck["MW"], ck["GW"], ck["inpipe"], ck["decide"], ck["maxloop"]))
    for n in ("row", "col", "box"):
        print("   %-3s %2d ops sends=%s" % (n, len(ck["ops"][n]), ck["send"][n]))
