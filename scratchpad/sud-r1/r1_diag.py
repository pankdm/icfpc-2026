#!/usr/bin/env python3
"""Enumerate the pick combinations r1_build.build() considers and report why the
low-`decide` ones are or are not feasible.  Writes r1_diag.txt, prints a summary."""
import os, sys, collections
ROOT = "/Users/visenbaev/icfpc26/.claude/worktrees/sud-agg"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, ROOT + "/solutions/sudoku-validity")
sys.path.insert(0, ROOT + "/tools")
import r1_build as B, serp

DW, DH, RW, BW, H, DX = 21, 3, 8, 9, 5, 5
MW = 2 + BW + RW + RW
ox = {"box": 1, "row": 1 + BW, "col": 1 + BW + RW}
wd = {"box": BW, "row": RW, "col": RW}
OPS = {"box": B.BOX9, "row": B.ROW9, "col": B.COL9}
avail = B.avail_times(DW, DH)

cands = {}
for n in OPS:
    seen, keep = set(), []
    for send, npads, cand, sends, lcols, stalls in B.pad(OPS[n], wd[n], H, avail, min_gap=1):
        key = tuple(lcols)
        if key in seen:
            continue
        seen.add(key)
        keep.append((send, cand, sends, lcols, stalls))
    cands[n] = keep[:30]
print({n: len(cands[n]) for n in cands})

rows = []
for cb in cands["box"]:
    for cr in cands["row"]:
        for cc in cands["col"]:
            pick = {"box": cb, "row": cr, "col": cc}
            scols, rcols, ok = [], {}, True
            for n in ("box", "row", "col"):
                slots = serp.serp(wd[n], H)[0]
                ops2 = pick[n][1]
                if len(ops2) > len(slots):
                    ok = False
                    break
                scols += [ox[n] + slots[i][0] for i, ch in enumerate(ops2) if ch == "s"]
                rcols[n] = {ox[n] + slots[i][0] for i, ch in enumerate(ops2) if ch == "r"}
            if not ok:
                continue
            decide = max(pick[n][2][-1] for n in pick) + 2 + B.STRIP_DECIDE
            lap = decide + 2 if (decide + 2) % 2 == 0 else decide + 1
            lap = decide + 1 + 1
            if lap % 2:
                lap += 1
            so = B.solve_out(scols, 1, MW - 2, 6, min_last=lap // 2 - 1)
            si = B.solve_in(rcols, 1, MW - 2, DX + 1)
            fail = None
            if not so:
                fail = "out"
            elif not si:
                fail = "in"
            elif not (DX < min(si) and max(si) < DX + DW + 1):
                fail = "span"
            rows.append((decide, lap, fail, so and sorted(so[0])[-1]))

with open(os.path.join(HERE, "r1_diag.txt"), "w") as f:
    for r in sorted(rows, key=repr):
        f.write(repr(r) + "\n")
c = collections.Counter((r[0], r[2]) for r in rows)
for k in sorted(c, key=repr):
    print(k, c[k])
