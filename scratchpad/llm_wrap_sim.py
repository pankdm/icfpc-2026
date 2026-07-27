#!/usr/bin/env python3
"""How many ribbon wraps does the LLM token stream need if scalar state moves
from ONE indexed belt (2 columns, revisited 582x) to per-variable holders
(one read column + one write column each)?

Rows = blocks + 3*br + go + wraps  (calibrated: all-ops-deleted = 586 rows,
full build = 994 rows, i.e. 408 wraps today).
"""
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-man"))

import build_banked_dedup as dedup
import build_banked_boustro as bb
import llm_load_bound as bound


def build_streams():
    """Per block: list of port-ids ('any' ops dropped -- they cost columns, not
    wraps, and the current build has 278 columns of room)."""
    flow = bb.alias_empty_gotos(dedup.build_flow())
    loads, stores, touched = [], [], {}
    for label, toks in flow.blocks.items():
        bound.run_block(label, toks, loads, stores, touched)

    ev_by_block = defaultdict(list)
    for e in loads:
        ev_by_block[e["block"]].append((e["idx"], "load", e["addr"], e["kind"]))
    for s in stores:
        ev_by_block[s["block"]].append((s["idx"], "store", s["addr"], s["kind"]))

    streams = {}
    for label, toks in flow.blocks.items():
        seq = []
        evs = sorted(ev_by_block[label])
        handled = set()
        for idx, kind, addr, port in evs:
            if kind == "load":
                if port == "cr":
                    seq.append(("CELL_C", "CELL_R"))
                elif addr is None:
                    seq.append(("RAM_C", "RAM_R"))
                else:
                    seq.append((f"V{addr}_R",))
            else:
                if port == "cc":
                    seq.append(("CELL_C", "CELL_C"))
                elif addr is None:
                    seq.append(("RAM_C", "RAM_C"))
                else:
                    seq.append((f"V{addr}_W",))
        flat = [p for grp in seq for p in grp]
        # non-RAM ports keep their own columns
        extra = [t for t in toks if t in ("ri", "sd", "sa", "ss")]
        streams[label] = flat
        streams[label + "\0extra"] = extra
    return flow, streams


def simulate(order_index, streams, flow):
    """Boustrophedon wrap count: cursor sweeps E, wraps when the next required
    column is behind it, then sweeps W, and so on."""
    wraps = 0
    for label in flow.blocks:
        seq = streams[label]
        if not seq:
            continue
        x = -1
        d = 1
        for port in seq:
            c = order_index[port]
            if d == 1:
                if c <= x:
                    wraps += 1
                    d = -1
                    x = c
                else:
                    x = c
            else:
                if c >= x:
                    wraps += 1
                    d = 1
                    x = c
                else:
                    x = c
    return wraps


def main():
    flow, streams = build_streams()
    ports = sorted({p for label in flow.blocks for p in streams[label]})
    print("distinct holder columns needed:", len(ports))
    print(sorted(ports))
    freq = Counter(p for label in flow.blocks for p in streams[label])
    print("\nmost-visited columns:", freq.most_common(12))
    total_accesses = sum(freq.values())
    print("total port visits:", total_accesses)

    nbr = sum(1 for t in flow.blocks.values()
              if t and isinstance(t[-1], tuple) and t[-1][0] == "br")
    ngo = sum(1 for t in flow.blocks.values()
              if t and isinstance(t[-1], tuple) and t[-1][0] == "go")
    floor = len(flow.blocks) + 3 * nbr + ngo
    print("CFG floor rows:", floor)

    # ---- baseline: today's single belt (2 columns) --------------------------
    belt = {}
    for p in ports:
        if p.endswith("_W") or p.endswith("_C"):
            belt[p] = 0          # every write/command lands on the sc column
        else:
            belt[p] = 1          # every read lands on the rr column
    print("\nsingle-belt model wraps:", simulate(belt, streams, flow),
          "-> rows", floor + simulate(belt, streams, flow))

    # ---- per-variable holders: anneal the column order ---------------------
    best = None
    rng = random.Random(7)
    for restart in range(6):
        order = ports[:]
        rng.shuffle(order)
        idx = {p: i for i, p in enumerate(order)}
        cur = simulate(idx, streams, flow)
        T = 40.0
        for step in range(60000):
            T = 40.0 * (1 - step / 60000) + 0.5
            i, j = rng.randrange(len(order)), rng.randrange(len(order))
            if i == j:
                continue
            order[i], order[j] = order[j], order[i]
            idx = {p: k for k, p in enumerate(order)}
            new = simulate(idx, streams, flow)
            if new <= cur or rng.random() < pow(2.718, -(new - cur) / T):
                cur = new
            else:
                order[i], order[j] = order[j], order[i]
        idx = {p: k for k, p in enumerate(order)}
        val = simulate(idx, streams, flow)
        if best is None or val < best[0]:
            best = (val, order[:])
        print("  restart %d: wraps %d" % (restart, val))

    wraps, order = best
    rows = floor + wraps
    print("\nBEST holder-column wraps: %d  ->  rows %d" % (wraps, rows))
    print("order:", order)
    # width estimate: one column per port + chrome
    width = len(ports) * 2 + 40
    print("rough width if every holder gets 2 columns:", width)
    print("box if square-ish: max(%d,%d)^2 = %d" % (width, rows, max(width, rows) ** 2))
    for t in (205213603601,):
        print("ticks needed for %d: %d (speedup vs 10,958,374: %.2fx)"
              % (t, t // max(width, rows) ** 2,
                 10958374 / (t / max(width, rows) ** 2)))


if __name__ == "__main__":
    main()
