#!/usr/bin/env python3
"""Derive a legal satellite floor DETERMINISTICALLY from a port map.

The random band walks kept failing on reordered port maps because a legal floor
is not a random point: the six shallow request/reply runs form a strict
ordering.  A run at band row b is crossed by any pipe that descends past b in a
column the run spans, so

    b(X) > b(Y)   whenever Y's riser column lies strictly inside X's span

and a pipe that descends all the way to a room (ri, sp, qs, sa, sd, ss) may not
be spanned at all.  Topologically sorting that DAG assigns the rows; ctop then
sits one row below the deepest band.

  cd s4 && python3 scratchpad/pf_floor.py '{"ri":10,...}' [out.json]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, HERE)

import stateflow  # noqa: E402


def derive(c):
    scratch_off = c["sp"] - 3
    scalar_off = c["sc"] - 3
    cell_off = c["cc"] + 17
    display_off = c["sa"] - 8
    queue_off = c["qs"] - 2
    queue_tail = queue_off - 5
    # sd enters the display's WEST wall, so its own column has to be west of
    # the display room: the run at display_y+8 is level with the display's
    # rows and would otherwise be drawn straight through it.
    if c["sd"] >= display_off:
        raise ValueError(f"sd@{c['sd']} is not west of the display@{display_off}")
    sd_via = c["sd"]

    # riser column -> (name); risers turn at their own band row
    riser = {"sc": c["sc"], "rr": scalar_off + 7, "cc": c["cc"],
             "cr": cell_off + 7, "rp": scratch_off + 4, "qr": queue_tail}
    span = {
        "sc": (c["sc"], scalar_off + 3),
        "rr": (scalar_off + 7, c["rr"]),
        "cc": (c["cc"], cell_off - 20 + 3),
        "cr": (cell_off + 7, c["cr"]),
        "rp": (scratch_off + 4, c["rp"]),
        "qr": (queue_tail, c["qr"]),
    }
    span = {k: (min(a, b), max(a, b)) for k, (a, b) in span.items()}
    # the second riser of each run (the port column itself) is equally opaque
    port_col = {"sc": c["sc"], "rr": c["rr"], "cc": c["cc"], "cr": c["cr"],
                "rp": c["rp"], "qr": c["qr"]}

    # A command port's pipe descends in ONE unbroken vertical from the wall to
    # its component (the horizontal leg is zero-length once the component is
    # pinned), so sc/cc/sp/sa/qs are opaque at every band row -- not just at
    # their own.  Missing that is what put rp's return run straight through the
    # scalar command column on the first free-order build.
    deep = {"ri": c["ri"], "sp": c["sp"], "qs": c["qs"], "sa": c["sa"],
            "sd": c["sd"], "ss": c["ss"], "sd_via": sd_via,
            "sc": c["sc"], "cc": c["cc"]}
    names = list(span)
    for x in names:
        lo, hi = span[x]
        for d, col in deep.items():
            if lo < col < hi:
                raise ValueError(f"{x} run {lo}..{hi} crosses deep pipe {d}@{col}")

    edges = {x: set() for x in names}   # edges[x] = {y : b(y) < b(x)}
    for x in names:
        lo, hi = span[x]
        for y in names:
            if y == x:
                continue
            if lo < riser[y] < hi or lo < port_col[y] < hi:
                edges[x].add(y)
    order, seen, temp = [], set(), set()

    def visit(n):
        if n in seen:
            return
        if n in temp:
            raise ValueError(f"cyclic band ordering at {n}")
        temp.add(n)
        for m in edges[n]:
            visit(m)
        temp.discard(n)
        seen.add(n)
        order.append(n)

    for n in names:
        visit(n)
    band = {n: i for i, n in enumerate(order)}
    ctop = len(order) + 1
    floor = {
        "scratch_off": scratch_off, "scalar_off": scalar_off,
        "cell_off": cell_off, "display_off": display_off,
        "queue_off": queue_off, "queue_tail": queue_tail, "sd_via": sd_via,
        "ctop": ctop,
        "sc_band": band["sc"], "rr_band": band["rr"], "cc_band": band["cc"],
        "cr_band": band["cr"], "sp_band": 0, "rp_band": band["rp"],
        "qr_band": band["qr"],
        # rooms hang below every band row
        "ri_row": ctop + 1, "scratch_row": ctop + 1, "queue_row": ctop + 1,
        "display_row": 37, "sd_band": 3, "sa_band": -8, "ss_band": 19,
        "queue_left": queue_off + 7, "queue_right_off": queue_off + 9,
        "queue_rows": 1,
    }
    return floor


if __name__ == "__main__":
    ports = {n: stateflow.DEFAULT_PORTS[n][0] for n in stateflow.DEFAULT_PORTS}
    ports.update(json.loads(sys.argv[1]))
    floor = derive(ports)
    blob = {"ports": ports, "floor": floor}
    print(json.dumps(blob))
    if len(sys.argv) > 2:
        json.dump(blob, open(sys.argv[2], "w"), indent=1)
