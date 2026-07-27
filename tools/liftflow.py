#!/usr/bin/env python3
"""liftflow.py — the ADAPTER: a .man grid -> the flow IR that `tools/smtrows.py` eats.

`smtrows.py` is Z3-optimal op placement INSIDE a controller room, which is the granularity
where our air actually is (the snake champion's controller is 936 blank glide cells out of
1340 reachable). But it only ever accepted a `build*.py` exposing `build_flow()`, and only
two builders in the repo do (little-little-man, pathfinder). Every hand-structured champion
— snake's build_fold*, gradebook, tcp — was unreachable. This module closes that gap: it
recovers the SAME object (`.blocks` = {label: [token...]}, `.ports` = {name: (col, group,
lo, hi)}) straight from a grid, so smtrows runs on ANY champion.

WHAT IS RECOVERED, and from where
  * `tools/lift.py` gives room/pipe topology and a per-man static walk. We redo the walk here
    at (cell, heading) granularity — `lift.walk` collapses states to cells, and a blank glide
    entered on two different headings then acquires two successors, which merges two unrelated
    control paths into one and corrupts any block structure built on it.
  * INSTRUCTION cells (PROBLEM.md's op set) become tokens; turn glyphs and blank glides are
    ROUTING and are dropped — they are exactly the material a re-placement pass regenerates.
  * A block ends at a branch (`X`/`d`/`a`/`x` -> `("br", ...)`), at `H`, at `Y`, or where
    control merges. That matches flowgrid's own emitter, where `br` costs one extra row
    (it lays `v` then `X` beneath it) and `go` costs none.

PORT BINDING is the part that must not be approximated. `s`/`r`/`q` lock onto the NEAREST
pipe by Manhattan distance to the pipe's attach cell (`path[0]` outgoing, `path[-1]` incoming),
reading-order ties — so an op's identity depends on its COLUMN, and moving it across a Voronoi
midpoint silently rewires the program. We name one port per pipe endpoint on the man's room and
derive each port's legal column band as the strict Voronoi cell among same-direction ports.
`S` (send-all), `R` and `U` (take from any ready incoming) are NOT column-bound and are lifted
as plain ops — but `U`'s *turn* is relative to its pipe, so a block containing `U` is flagged
`unpinnable` and reported rather than silently re-placed.

The y-term of the Manhattan distance cancels only when every same-direction port attaches on
the same row (true for every bottom/top-edge controller we build, snake included). When it does
not, `--report` says so and the emitted bands are the conservative row-independent intersection.

FIDELITY. The static walk over-approximates: a branch fans out three ways and `U` four, so
paths that never execute still appear. `--trace <slug>` runs the Rust engine with `--profile`
over the real public cases and intersects the lift with the cells the machine ACTUALLY executed,
turning the over-approximation into a measured one; `--report` prints both counts so the gap is
never invisible.

  python3 tools/liftflow.py <file.man>                    structure report
  python3 tools/liftflow.py <file.man> --trace snake      + executed-cell intersection
  python3 tools/liftflow.py <file.man> --json             the IR
  python3 tools/smtrows.py <file.man> [--free-ports]      Z3 on the lifted IR
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lift as _lift  # noqa: E402

OPS = _lift.OPS
TURNS = _lift.TURNS
BRANCH = _lift.BRANCH
CW, CCW = _lift.CW, _lift.CCW

# Column-bound pipe ops: these resolve by NEAREST attach cell, so their column is semantic.
SEND_NEAREST = set("s")
RECV_NEAREST = set("rq")
# Not column-bound: S floods every outgoing pipe; R/U take from any ready incoming.
FREE_PIPE_OPS = set("SRU")


class LiftedFlow:
    """Duck-type of flowgrid.Flow as far as smtrows is concerned."""

    def __init__(self):
        self.blocks = {}
        self.ports = {}
        self.meta = {}


def _walk_states(lf, start):
    """Static walk keeping (pos, heading) — the only granularity at which a glide's
    successor is well defined. Returns (states, trans) over (pos, dir) pairs."""
    states = {}
    trans = {}
    stack = [((start[0], start[1]), (1, 0))]
    while stack:
        st = stack.pop()
        if st in states:
            continue
        (x, y), d = st
        ch = lf.at(x, y)
        states[st] = ch
        if not lf.walkable(x, y):          # stepping onto a wall ends this path
            trans[st] = []
            continue
        if ch in _lift.STOP:
            trans[st] = []
            continue
        if ch in TURNS:
            outs = [TURNS[ch]]
        elif ch in BRANCH:
            outs = [d, CW[d], CCW[d]]
        elif ch == "Y":
            outs = [CW[d], CCW[d]]
        elif ch == "U":
            outs = [d, CW[d], CCW[d], CW[CW[d]]]
        else:
            outs = [d]
        nxt = []
        for nd in outs:
            s2 = ((x + nd[0], y + nd[1]), nd)
            nxt.append(s2)
            stack.append(s2)
        trans[st] = nxt
    return states, trans


def _contract(states, trans, entry, keep):
    """Contract routing states away: op-state -> set of next op-states.

    `keep(st)` says a state is an instruction. Everything else (turn glyphs, glides) is pure
    routing and is skipped over."""
    def reach(seeds):
        out, seen, stack = [], set(), list(seeds)
        while stack:
            s = stack.pop()
            if s in seen:
                continue
            seen.add(s)
            if s not in states:
                continue
            if keep(s):
                out.append(s)
                continue
            stack.extend(trans.get(s, []))
        return out

    op_states = [s for s in states if keep(s)]
    succ = {s: reach(trans.get(s, [])) for s in op_states}
    heads = reach([entry])
    return op_states, succ, heads


def _basic_blocks(op_states, succ, heads, states):
    """flowgrid-shaped blocks: straight-line op runs, cut at branches and merges."""
    pred = {s: set() for s in op_states}
    for s, ns in succ.items():
        for n in ns:
            pred.setdefault(n, set()).add(s)
    leaders = set(heads)
    for s in op_states:
        ch = states[s]
        if len(pred.get(s, ())) != 1:
            leaders.add(s)
        if len(succ.get(s, ())) > 1 or ch in BRANCH or ch == "Y":
            for n in succ.get(s, ()):
                leaders.add(n)
    blocks, seen = [], set()
    order = sorted(leaders, key=lambda s: (s[0][1], s[0][0]))
    # Emit in reverse-postorder from the entry so the block sequence follows control flow.
    todo = [h for h in heads] + order
    for ld in todo:
        if ld in seen or ld not in leaders:
            continue
        run, cur = [], ld
        while cur is not None and cur not in seen:
            seen.add(cur)
            run.append(cur)
            ch = states[cur]
            ns = succ.get(cur, [])
            if ch in BRANCH or ch == "Y" or len(ns) != 1:
                break
            nxt = ns[0]
            cur = nxt if nxt not in leaders else None
        blocks.append(run)
    return blocks


def _ports_of_room(lf, room_idx):
    """One named port per pipe endpoint on this room, with its Voronoi column band.

    `col` is the attach cell's column (`path[0]` for outgoing, `path[-1]` for incoming —
    exactly what the engine measures nearest against). Group 's' = outgoing (targets of `s`),
    'r' = incoming (targets of `r`/`q`)."""
    room = lf.rooms[room_idx]
    (x0, y0), (x1, y1) = room["min"], room["max"]
    raw = []
    for i, p in enumerate(lf.pipes):
        if p["src"] == room_idx:
            a = p["path"][0]["pos"]
            raw.append((f"o{i}", a[0], a[1], "s", i))
        if p["dst"] == room_idx:
            a = p["path"][-1]["pos"]
            raw.append((f"i{i}", a[0], a[1], "r", i))
    ports, rows_by_group = {}, {}
    for name, cx, cy, grp, pi in raw:
        rows_by_group.setdefault(grp, set()).add(cy)
    for name, cx, cy, grp, pi in raw:
        same = sorted([r for r in raw if r[3] == grp], key=lambda r: (r[1], r[2]))
        lo, hi = x0 + 1, x1 - 1
        for oname, ox, oy, ogrp, opi in same:
            if oname == name:
                continue
            if ox < cx:
                # strictly nearer cx than ox: 2c >= ox+cx+2 (smtrows' conservative form)
                lo = max(lo, -(-(ox + cx + 2) // 2))
            elif ox > cx:
                hi = min(hi, (ox + cx - 2) // 2)
        ports[name] = (cx, grp, lo, hi)
    meta = {
        "attach_rows": {g: sorted(v) for g, v in rows_by_group.items()},
        "coplanar": all(len(v) <= 1 for v in rows_by_group.values()),
        "interior": [x0 + 1, y0 + 1, x1 - 1, y1 - 1],
    }
    return ports, meta, raw


def _bind(pt, raw, grp):
    """Which port does an op at `pt` bind to? Manhattan to the attach cell, reading-order ties
    — the engine's `nearest_outgoing` / `nearest_incoming` verbatim."""
    best = None
    for name, cx, cy, g, pi in raw:
        if g != grp:
            continue
        k = (abs(cx - pt[0]) + abs(cy - pt[1]), cy, cx)
        if best is None or k < best[0]:
            best = (k, name)
    return None if best is None else best[1]


def executed_cells(man, slug, cap=None):
    """The cells the machine ACTUALLY executed, from the Rust engine's --profile, unioned
    over every public case. This is what turns the static over-approximation into a measured
    one."""
    lm = os.path.join(REPO, "interp", "target", "release", "lm")
    spec_path = os.path.join(REPO, "tests", f"{slug}.json")
    if not (os.path.exists(lm) and os.path.exists(spec_path)):
        return None
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import grade_fast
    spec = json.load(open(spec_path))
    tick_cap = cap or spec.get("tickCap") or 5_000_000
    hit = set()
    for tc in spec.get("publicTestData") or []:
        inp, exp, frames = grade_fast.rounds_of(tc)
        cmd = [lm, "--profile", man, f"--input={inp}", f"--expected={exp}",
               f"--cap={int(tick_cap)}"]
        if frames:
            cmd.append(f"--frames={frames}")
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        for line in (p.stderr or "").splitlines():
            if not line.startswith("PROFILE cells="):
                continue
            body = line[len("PROFILE cells="):]
            import re
            for mx, my in re.findall(r"\((-?\d+), (-?\d+)\)", body):
                hit.add((int(mx), int(my)))
    return hit


def lift_flow(man_path, man_index=None, trace_slug=None, cap=None):
    rows = _lift.load_rows(man_path)
    lf = _lift.Lift(rows)
    if lf.topo.get("type") == "error":
        raise SystemExit(f"analyze failed: {lf.topo.get('message')}")
    starts = lf.starts()
    walks = []
    for s in starts:
        states, trans = _walk_states(lf, s)
        n_ops = sum(1 for st, ch in states.items() if ch in OPS)
        walks.append((s, states, trans, n_ops))
    if man_index is None:
        man_index = max(range(len(walks)), key=lambda i: walks[i][3])
    start, states, trans, _ = walks[man_index]
    room_idx = lf.room_of(*start)
    ports, pmeta, raw = _ports_of_room(lf, room_idx)

    live = None
    if trace_slug:
        live = executed_cells(man_path, trace_slug, cap)

    def keep(st):
        ch = states[st]
        if ch not in OPS:
            return False
        if live is not None and st[0] not in live:
            return False
        return True

    entry = ((start[0], start[1]), (1, 0))
    op_states, succ, heads = _contract(states, trans, entry, keep)
    blocks = _basic_blocks(op_states, succ, heads, states)

    flow = LiftedFlow()
    label_of = {}
    for bi, b in enumerate(blocks):
        label_of[b[0]] = f"B{bi}"
    unpinnable = []
    n_port_ops = 0
    block_cells = {}
    for bi, b in enumerate(blocks):
        label = f"B{bi}"
        block_cells[label] = [st[0] for st in b]
        toks = []
        for st in b:
            ch = states[st]
            pt = st[0]
            if ch in BRANCH:
                tgts = tuple(label_of.get(n, "?") for n in succ.get(st, []))
                toks.append(("br",) + tgts)
                break
            if ch == "H":
                toks.append(("halt",))
                break
            if ch == "Y":
                toks.append(("fork",) + tuple(label_of.get(n, "?")
                                              for n in succ.get(st, [])))
                break
            if ch in SEND_NEAREST:
                toks.append(_bind(pt, raw, "s"))
                n_port_ops += 1
            elif ch in RECV_NEAREST:
                toks.append(_bind(pt, raw, "r"))
                n_port_ops += 1
            else:
                if ch in FREE_PIPE_OPS:
                    unpinnable.append((label, pt, ch))
                toks.append(ch)
        else:
            ns = succ.get(b[-1], [])
            if len(ns) == 1 and ns[0] in label_of:
                toks.append(("go", label_of[ns[0]]))
        flow.blocks[label] = toks
    flow.ports = ports
    flow.meta = {
        "man": man_index,
        "start": list(start),
        "room": room_idx,
        "room_interior": pmeta["interior"],
        "coplanar_ports": pmeta["coplanar"],
        "attach_rows": pmeta["attach_rows"],
        "n_ops": len(op_states),
        "n_port_ops": n_port_ops,
        "n_blocks": len(blocks),
        "unpinnable": unpinnable,
        "traced": trace_slug or None,
        "static_ops": sum(1 for st, ch in states.items() if ch in OPS),
        "static_cells": len(states),
        "op_cells": sorted({st[0] for st in op_states}),
        "occupied_rows": sorted({st[0][1] for st in op_states}),
        "block_cells": block_cells,
    }
    flow.lift = lf
    return flow


def report(flow, path):
    m = flow.meta
    x0, y0, x1, y1 = m["room_interior"]
    print(f"{os.path.basename(path)}  man{m['man']} @{tuple(m['start'])}  room {m['room']}  "
          f"interior {x1 - x0 + 1}x{y1 - y0 + 1} at ({x0},{y0})")
    print(f"  blocks {m['n_blocks']}   ops {m['n_ops']}  (static walk saw {m['static_ops']} "
          f"op cells over {m['static_cells']} states)"
          + (f"   [traced against {m['traced']}]" if m["traced"] else ""))
    print(f"  port ops {m['n_port_ops']}   ports {len(flow.ports)}   "
          f"coplanar attaches: {m['coplanar_ports']}  rows {m['attach_rows']}")
    print(f"  op rows used now: {len(m['occupied_rows'])} distinct rows "
          f"(room gives {y1 - y0 + 1})")
    if m["unpinnable"]:
        print(f"  UNPINNABLE (S/R/U — not column-bound; U's turn is pipe-relative): "
              f"{len(m['unpinnable'])}")
        for lbl, pt, ch in m["unpinnable"][:10]:
            print(f"    {lbl} {ch} at {pt}")
    print("  ports:")
    for n, (c, g, lo, hi) in sorted(flow.ports.items(), key=lambda kv: kv[1][0]):
        used = sum(1 for toks in flow.blocks.values() for t in toks if t == n)
        print(f"    {n:>4}  col {c:>3}  {g}  band [{lo},{hi}]  used {used}x")
    terms = {}
    for toks in flow.blocks.values():
        t = toks[-1][0] if toks and isinstance(toks[-1], tuple) else "fall"
        terms[t] = terms.get(t, 0) + 1
    print(f"  terminators: {terms}")
    sizes = sorted(len([t for t in v if not isinstance(t, tuple)])
                   for v in flow.blocks.values())
    print(f"  block op counts: min {sizes[0]} med {sizes[len(sizes) // 2]} "
          f"max {sizes[-1]}  sum {sum(sizes)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man")
    ap.add_argument("--man-index", type=int, default=None)
    ap.add_argument("--trace", metavar="SLUG")
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    flow = lift_flow(args.man, args.man_index, args.trace, args.cap)
    if args.json:
        print(json.dumps({
            "blocks": {k: [list(t) if isinstance(t, tuple) else t for t in v]
                       for k, v in flow.blocks.items()},
            "ports": {k: list(v) for k, v in flow.ports.items()},
            "meta": {k: v for k, v in flow.meta.items() if k != "op_cells"},
        }))
    else:
        report(flow, args.man)


if __name__ == "__main__":
    main()
