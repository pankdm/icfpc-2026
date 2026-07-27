#!/usr/bin/env python3
"""Which port moves actually buy the 246 -> 191 row cut?

Takes the free-order optimum and reverts one port at a time to its baseline
column, reporting the rows lost.  A move whose reversion costs nothing is one we
do not have to make -- and every move we skip is a floorplan we do not have to
re-route.

    cd s4 && python3 scratchpad/pf_ablate.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pf_bandsearch as m  # noqa: E402

OPT = {"ri": 44, "rr": 46, "sc": 87, "rp": 97, "cc": 103, "sp": 112,
       "ss": 158, "qr": 165, "sa": 171, "qs": 187, "cr": 228, "sd": 242}


def rows(cols):
    try:
        r, w = m.geometry(cols, 0, m.FORBID)
    except Exception:
        return None, None
    return r, w


def main():
    r0, w0 = rows(OPT)
    rb, wb = rows(m.BASE)
    print(f"optimum rows {r0} width {w0};  baseline rows {rb} width {wb}")
    print("\nrevert ONE port to baseline:")
    out = []
    for n in OPT:
        c = dict(OPT)
        c[n] = m.BASE[n]
        if len(set(c.values())) != len(c):
            c[n] = m.BASE[n] + 1
        out.append((rows(c)[0], n, m.BASE[n], OPT[n]))
    for r, n, b, o in sorted(out, key=lambda t: -(t[0] or 0)):
        print(f"  {n:3s} {o:3d} -> {b:3d}: rows {r}  (+{(r or 0) - r0})")
    print("\napply ONE port move to the baseline:")
    out = []
    for n in OPT:
        c = dict(m.BASE)
        c[n] = OPT[n]
        if len(set(c.values())) != len(c):
            c[n] = OPT[n] + 1
        out.append((rows(c)[0], n, m.BASE[n], OPT[n]))
    for r, n, b, o in sorted(out, key=lambda t: (t[0] or 9999)):
        print(f"  {n:3s} {b:3d} -> {o:3d}: rows {r}  ({(r or 0) - rb:+d})")


if __name__ == "__main__":
    main()
