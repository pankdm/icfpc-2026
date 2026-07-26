#!/usr/bin/env python3
"""Lift gradebook room0's walk to basic blocks with 3-way branch terminators.

Node = (cell, heading). Payload ops annotated with pipe binding (in/out, pipe id).
Literal runs are captured as atomic tokens.
"""
import sys, os, json
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
import walkfold as wf

DIRN = {(1, 0): "E", (-1, 0): "W", (0, -1): "N", (0, 1): "S"}


def lift(path):
    rows = wf.load_rows(path)
    g = wf.Grid(rows)
    start = g.starts()[0]
    succ = g.walk(start)

    # pipe attachment sites for room0
    inc, out = [], []
    for pi, p in enumerate(g.pipes):
        pp = p.get("path") or []
        if not pp:
            continue
        if p.get("src") == 0:
            out.append((pi, tuple(pp[0]["pos"])))
        if p.get("dst") == 0:
            inc.append((pi, tuple(pp[-1]["pos"])))

    def near(cands, cell):
        return min(cands, key=lambda c: (abs(c[1][0] - cell[0]) + abs(c[1][1] - cell[1]),
                                         c[1][1], c[1][0]))[0]

    def band_of(cell, ch):
        if ch in "rq":
            return ("in", near(inc, cell))
        if ch == "s":
            return ("out", near(out, cell))
        return None

    st0 = ((start[0], start[1]), (1, 0))
    pred = {}
    for s, ns in succ.items():
        for n in ns:
            pred.setdefault(n, []).append(s)

    leaders = {st0}
    for s, ns in succ.items():
        if len(ns) > 1:
            leaders.update(ns)
    leaders.update(s for s in succ if len(pred.get(s, ())) != 1)

    segs = {}
    for L in leaders:
        if L not in succ:
            continue
        cur, cells = L, []
        while True:
            cells.append(cur)
            ns = succ.get(cur, [])
            if len(ns) != 1 or ns[0] in leaders:
                break
            cur = ns[0]
        segs[L] = (cells, succ.get(cells[-1], []))

    def payload(cells):
        """ops with bindings; literal runs atomic."""
        toks = []
        lit = None
        for (c, d) in cells:
            ch = g.at(*c)
            if not g.walkable(*c):
                continue
            if ch == "`":
                if lit is None:
                    lit = ""
                else:
                    toks.append(("lit", "`" + lit + "`", None, c))
                    lit = None
                continue
            if lit is not None:
                if ch.strip():
                    lit += ch
                continue
            if ch in wf.OPS:
                toks.append(("op", ch, band_of(c, ch), c))
        assert lit is None, f"unterminated literal in segment"
        return toks

    def resolve(state):
        """Follow op-less glide segments to the next real block / halt / wall."""
        seen = set()
        while True:
            if state in seen:
                return ("loop", None)
            seen.add(state)
            if state not in segs:
                # not a leader: shouldn't happen for branch successors
                return ("dead", state)
            cells, outs = segs[state]
            last_cell = cells[-1][0]
            ch = g.at(*last_cell)
            if payload(cells) or ch in wf.BRANCH:
                return ("block", state)
            if ch == "H":
                return ("halt", None)
            if not outs:
                # walked out of room / into wall
                return ("wall", last_cell)
            if len(outs) == 1:
                state = outs[0]
            else:
                return ("block", state)

    # BFS order from start, exploring only glide-resolved block states
    order, seen = [], set()
    stack = [st0]
    while stack:
        s = stack.pop(0)
        if s in seen or s not in segs:
            continue
        seen.add(s)
        order.append(s)
        cells, outs = segs[s]
        last = g.at(*cells[-1][0])
        if last in wf.BRANCH:
            d = cells[-1][1]
            legs = [("S", d), ("CW", wf.CW[d]), ("CCW", wf.CCW[d])]
            for name, nd in legs:
                nstate = ((cells[-1][0][0] + nd[0], cells[-1][0][1] + nd[1]), nd)
                k, t = resolve(nstate)
                if k == "block" and t not in seen:
                    stack.append(t)
        else:
            for o in outs:
                k, t = resolve(o)
                if k == "block" and t not in seen:
                    stack.append(t)

    ids = {s: i for i, s in enumerate(order)}
    blocks = []
    for s in order:
        cells, outs = segs[s]
        last_cell, last_d = cells[-1]
        last = g.at(*last_cell)
        toks = payload(cells)
        if last in wf.BRANCH:
            # the branch glyph is the final token; strip it from the op list
            assert toks and toks[-1][1] == last, (toks, last)
            toks = toks[:-1]
            legs = {}
            for name, nd in (("S", last_d), ("CW", wf.CW[last_d]),
                             ("CCW", wf.CCW[last_d])):
                nstate = ((last_cell[0] + nd[0], last_cell[1] + nd[1]), nd)
                k, t = resolve(nstate)
                legs[name] = (k, ids.get(t) if k == "block" else
                              (t if k == "wall" else None))
            term = ("branch", last, legs)
        elif last == "H" or not outs:
            term = ("halt",) if last == "H" else ("wall", last_cell)
        else:
            k, t = resolve(outs[0])
            if k == "block":
                term = ("goto", ids[t])
            elif k == "halt":
                term = ("halt",)
            else:
                term = ("wall", t)
        blocks.append({"id": ids[s], "at": (list(s[0]), DIRN[s[1]]),
                       "ops": [(t[1], t[2]) for t in toks],
                       "cells": [list(t[3]) for t in toks],
                       "term": term})
    return blocks


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "solutions/gradebook/gradebook-walkfold.man"
    blocks = lift(path)
    print(f"{len(blocks)} blocks")
    for b in blocks:
        opstr = " ".join(ch if bd is None else f"{ch}[{bd[0]}{bd[1]}]"
                         for ch, bd in b["ops"])
        print(f"B{b['id']:<3} @{tuple(b['at'][0])}{b['at'][1]}: {opstr}")
        print(f"      term {b['term']}")
