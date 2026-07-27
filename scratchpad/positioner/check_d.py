#!/usr/bin/env python3
"""Is the d-bottom positioner a bijection index -> column?

pos4.man uses `x` at every level, so both branches of every node deflect and the
leaves land on one column parity (spacing 2, width 2^(b+1)-1).  `d` turns CW iff
BP>0 and otherwise goes STRAIGHT, so one branch deflects and the other does not
-- the two leaves under a `d` node are ADJACENT.  Feed each index and report the
column the man halts on.

    python3 scratchpad/positioner/check_d.py [file.man] [n]
"""
import json
import subprocess
import sys

MAN = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/positioner/pos4_d.man"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 16


def halt_col(k):
    """Run with index k; return the column of the man's final cell."""
    r = subprocess.run(
        ["interp/target/release/lm", "--inspect=60", MAN, "--input=%d" % k],
        capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout.strip().split("\n")[-1])
    except Exception:
        return None, "parse"
    runners = d.get("runners") or []
    if not runners:
        return None, d.get("end", "no runners")
    # the surviving man's position
    p = runners[0].get("pos")
    return (p[0] if p else None), d.get("end", "")


def main():
    cols, ends = {}, {}
    for k in range(N):
        c, e = halt_col(k)
        cols[k] = c
        ends[k] = e
    distinct = len({c for c in cols.values() if c is not None})
    print("%s  n=%d" % (MAN, N))
    print("index -> column:")
    for k in range(N):
        print("  %2d -> %s   %s" % (k, cols[k], ends[k][:28]))
    print("\ndistinct columns: %d/%d" % (distinct, N))
    vals = [cols[k] for k in range(N) if cols[k] is not None]
    if vals:
        print("span %d..%d  width %d" % (min(vals), max(vals),
                                         max(vals) - min(vals) + 1))


main()
