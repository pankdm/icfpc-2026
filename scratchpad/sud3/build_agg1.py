"""sudoku-validity agg1: PERIOD PROBE for the branch-free aggregator.

Geometry is deliberately NOT optimised here -- it reuses lanes11's dispatch and
addressing band verbatim so that the only thing the measurement reflects is the
cost of replacing the speculative timer with a real 6-lane collector.

  strip (2 cols x 5 rows, branch-free, no H/X/d):
      r  &  s        down the right column   (A = mask & acc  -> collision flag)
      r  |  M        up the left column      (acc |= mask)
  accumulator lives permanently in B and starts at 0, so no init tail.
  the mask therefore has to arrive TWICE, which is why TAIL sends `ss`.

  aggregator (own room, straight-line, fully unrolled):
      r M (r | M)x5  then  1 + M 1 /  s      -- 1/(1+OR) is 1 iff OR == 0
"""

import os, sys
sys.path.insert(0, "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg/tools")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from littleman import Program
import serp

DISPATCH9 = list("3MrS/S3MrS/SrM7-M9*S")
TAIL = list("-M1{ss1N~M1{ss")                 # each mask goes out TWICE
ROW9 = list("rM") + ["r"] * 4 + TAIL
COL9 = list("rrrM") + ["r"] * 2 + TAIL
BOX9 = list("rrM3*Mrr+Mr") + TAIL

AGG = list("rM") + list("r|M") * 5 + list("1+M1/s")


def avail_times(DW, DH, pipe_in=2):
    S = [i for i, c in enumerate(DISPATCH9) if c == "S"]
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


def pad(ops, W, H, avail, min_gap=3, max_pads=6):
    """Insert nops so the FOUR `s` cells (two lanes, each sent twice) land in a
    usable pattern: the two copies of one mask must share a column (they are the
    same pipe), and the two lanes must be >= min_gap apart."""
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


def nearest_map(us, ps):
    out = []
    for u in us:
        d = sorted((abs(u - p), p) for p in ps)
        if len(d) > 1 and d[0][0] == d[1][0]:
            return None
        out.append(d[0][1])
    return out


def solve_out(scols, lo, hi, min_col, min_gap=3):
    """six lane pipe columns.  scols is 12 long: for each of the three rooms,
    lane1 sent twice then lane2 sent twice.  Both copies of one mask must bind
    the SAME pipe (they are the same lane), and the six lanes must be a
    bijection onto the six pipes."""
    best = None

    def rec(chosen, start):
        nonlocal best
        if len(chosen) == 6:
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


def ring(p, L, y):
    """2-wide, 5-tall branch-free strip.  Incoming pipe binds column L."""
    R = L + 1
    p.put(L, y, ">"); p.put(R, y, "v")
    p.put(R, y + 1, "r"); p.put(R, y + 2, "&"); p.put(R, y + 3, "s")
    p.put(R, y + 4, "<"); p.put(L, y + 4, "^")
    p.put(L, y + 3, "r"); p.put(L, y + 2, "|"); p.put(L, y + 1, "M")


def build(DW=23, DH=3, RW=8, BW=9, H=5, DXfix=5, AW=9, AH=5):
    p = Program()
    YA = 7
    MW = 2 + BW + RW + RW
    ox = {"box": 1, "row": 1 + BW, "col": 1 + BW + RW}
    wd = {"box": BW, "row": RW, "col": RW}
    OPS = {"box": BOX9, "row": ROW9, "col": COL9}
    DX = DXfix
    avail = avail_times(DW, DH)

    cands = {}
    for n in OPS:
        seen, keep = set(), []
        for send, npads, cand, sends, lcols, stalls in pad(OPS[n], wd[n], H, avail,
                                                           min_gap=3):
            key = tuple(lcols)
            if key in seen:
                continue
            seen.add(key)
            keep.append((send, cand, sends, lcols, stalls))
        cands[n] = keep[:12]
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
                so = solve_out(scols, 1, MW - 3, 2)
                if not so:
                    continue
                cols = sorted(so[0])
                si = solve_in(rcols, 1, MW - 2, DX + 1)
                if not si:
                    continue
                if not (DX < min(si) and max(si) < DX + DW + 1):
                    continue
                width = max(MW, DX + DW + 2, cols[-1] + 3)
                decide = max(pick[n][2][-1] for n in pick)
                key = (width, decide)
                if best is None or key < best[0]:
                    best = (key, pick, scols, cols, so[1], si)
    assert best, "no geometry satisfies both bindings"
    _, pick, scols, cols, lanepipe, inpipe = best

    p.room(0, YA, MW, H + 3)
    pos, before = {}, dict(p.cells)
    for n in ("box", "row", "col"):
        pos[n] = serp.place(p, ox[n], YA + 2, wd[n], H, pick[n][1])
    for (x, y), ch in p.cells.items():
        if (x, y) in before and before[(x, y)] != ch and before[(x, y)] != " ":
            raise AssertionError(("loops collided at", x, y))

    order = ["box", "row", "col"]
    R0, R1 = YA + 1, YA + 2
    for n in order:
        p.put(ox[n], R1, " ")
    p.put(ox[order[0]], R1, "@")
    for n in order[:-1]:
        c = ox[n] + 1
        p.put(c, R1, "Y"); p.put(c, R0, ">")
        p.put(c + 1, R0, "v"); p.put(c + 1, R1, ">")
    p.put(ox[order[-1]] + 1, R1, "v")

    p.room(DX, 0, DW + 2, DH + 2)
    serp.place(p, DX + 1, 1, DW, DH, DISPATCH9)
    p.input_room(DX - 5, 0)
    p.pipe([(DX - 2, 1), (DX - 1, 1)])
    inmap = dict(zip(("box", "row", "col"), inpipe))
    for px in inpipe:
        p.pipe([(px, DH + 2), (px, YA - 1)])

    srcy = YA + H + 3
    YG = srcy + 2
    GW = cols[-1] + 3
    p.room(0, YG, GW, 9)
    G0, G1, G2 = YG + 1, YG + 2, YG + 3        # return row, fork row, ring top
    for C in cols[:-1]:
        p.put(C, G1, "Y"); p.put(C, G0, ">")
        p.put(C + 1, G0, "v"); p.put(C + 1, G1, ">")
    p.put(cols[-1], G1, "v")
    ix = cols[0] - 1
    assert ix >= 1, ("no room for the gadget '@'", cols)
    p.put(ix, G1, "@")
    for C in cols:
        ring(p, C, G2)
        p.pipe([(C, srcy), (C, YG - 1)])

    # ---- aggregator, below the gadget (probe layout: box is not the point)
    YO = YG + 9 + 2
    p.room(0, YO, AW + 2, AH + 2)
    aslots = serp.place(p, 1, YO + 1, AW, AH, AGG)
    gout = cols[0] + 1                          # the six `s` cells all bind it
    p.pipe([(gout, YG + 9), (gout, YO - 1)])
    asend = [c for c, ch in zip(aslots, AGG) if ch == "s"][0]
    p.pipe([(AW + 2, asend[1]), (AW + 3, asend[1])])
    p.output_room(AW + 4, asend[1] - 1)

    ck = dict(cols=cols, ops={n: pick[n][1] for n in pick},
              send={n: pick[n][2] for n in pick}, scols=scols,
              lane=dict(zip(scols, lanepipe)), inpipe=inmap, ox=ox, wd=wd, H=H,
              MW=MW, GW=GW,
              maxloop=max([serp.loop_len(DW, DH), serp.loop_len(AW, AH)]
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


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dw", type=int, default=23)
    ap.add_argument("--dx", type=int, default=5)
    ap.add_argument("--rw", type=int, default=8)
    ap.add_argument("--bw", type=int, default=9)
    ap.add_argument("--rh", type=int, default=5)
    ap.add_argument("-o", "--out", default="agg1.man")
    a = ap.parse_args()
    p, ck = build(DW=a.dw, DXfix=a.dx, RW=a.rw, BW=a.bw, H=a.rh)
    check(ck)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), a.out)
    p.save(out)
    print(out, "footprint", p.footprint(), "cols", ck["cols"])
    print("   room %dw gadget %dw maxloop=%d" % (ck["MW"], ck["GW"], ck["maxloop"]))
