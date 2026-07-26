#!/usr/bin/env python3
"""sched.py — INSTRUCTION SCHEDULING: slide blocking pipe ops later past work they don't need.

READ THIS BEFORE BELIEVING A SPEEDUP. A stalled man executes nothing, so you cannot hide a
stall behind later work — the naive "issue an independent op while we wait" does not exist on
this machine. The only reordering that can pay is the mirror image:

    r ; op1 ; op2      arrive T, wait d, resume T+d, finish op2 at T+d+2
    op1 ; op2 ; r      arrive T, do both, hit `r` at T+2, value is ready at T+d
                       ->  finish at max(T+d, T+2)      saves min(k, d) ticks for k ops moved

so a blocking `r`/`s` should be issued as LATE as possible, after every op that does not need
its result. That is the only move this tool makes: bubble each blocking op down its
straight-line run, past ops (and blank glides — a glide costs a tick too) that are dataflow-
independent of it.

AND THE CEILING IS LOW, which is the honest headline. The gain is bounded by min(k, d) on the
man that is bubbled, and only the CRITICAL man's ticks reach the score. On a champion whose
critical man barely stalls, there is nothing to win: measured stall share of the critical man
is 0.0% on matmul and gradebook, 11.5-11.9% on memory and plotter, 17.6% on sudoku-validity.
The eye-catching global stall figures (63%, 82%) are averages over idle SATELLITE men, and a
satellite that waits less still waits for the same producer. Worse, in steady state a man that
stalls is by definition not the bottleneck, so its schedule cannot set the period at all.
Expect this pass to find legal swaps and no score.

WHEN IS A SWAP LEGAL. Two cells p, q = p+d may trade places iff all of:
  * they are WELDED — every man executes p then q, with one heading, and q has no other
    predecessor and p no other successor. Otherwise some walk sees a different instruction.
  * neither is control (`> < ^ v V X d a x Y H U`), a backtick literal cell, `@`, `I` or `O`.
    Moving control moves the walk; moving a literal cell changes a constant.
  * they are INDEPENDENT on A / B / BP — no RAW, WAR or WAW. Independence is what makes the
    post-pair register state identical, so everything downstream is untouched.
  * they are not both pipe ops — pipe traffic order is observable.
  * a moved pipe op still picks the SAME pipe. `s`/`r`/`q` resolve to the nearest pipe by
    Manhattan distance from the INSTRUCTION CELL, with a reading-order tiebreak, so sliding
    one cell can silently retarget it in a multi-pipe room.

Everything is then grade-gated: a candidate survives only if it passes EVERY public case and
does not score worse. The input is never modified; output is <name>-sched.man.

  python3 tools/sched.py <slug> <file.man> --census   # dataflow + swap census, no grading
  python3 tools/sched.py <slug> <file.man>            # census, then grade every bubble
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import dce as DCE      # noqa: E402  (DeadSet: rooms/pipes/reachability/literal protection)
import lift as LIFT    # noqa: E402  (TURNS / BRANCH / STOP and the movement rules)
import polish as PO    # noqa: E402  (ok / key / fmt / footprint / atomic_write)

A, B, BP, P = "A", "B", "BP", "P"       # P = the pipe network (a shared, timed resource)

# reads, writes per instruction. `P` marks an observable interaction with the pipes.
RW: dict[str, tuple[frozenset, frozenset]] = {}
for _c in "0123456789":
    RW[_c] = (frozenset(), frozenset({A}))
for _c in " .":
    RW[_c] = (frozenset(), frozenset())
for _c in "+-*%&|~{}":
    RW[_c] = (frozenset({A, B}), frozenset({A}))
RW.update({
    "M": (frozenset({A}), frozenset({B})),
    "W": (frozenset({A, B}), frozenset({A, B})),
    "b": (frozenset({A}), frozenset({BP})),
    "m": (frozenset({BP}), frozenset({BP})),
    "]": (frozenset({BP}), frozenset({BP})),
    "q": (frozenset({P}), frozenset({BP})),
    "/": (frozenset({A, B}), frozenset({A, B})),
    "N": (frozenset({A}), frozenset({A})),
    "s": (frozenset({A, P}), frozenset({P})),
    "S": (frozenset({A, P}), frozenset({P})),
    "r": (frozenset({P}), frozenset({A, P})),
    "R": (frozenset({P}), frozenset({A, P})),
})
BLOCKING = set("sSrR")          # may park the man: these are what we want to issue late
PIPE_OPS = set("sSrRq")         # position-sensitive: nearest-pipe is resolved geometrically
MOVABLE = set(RW)               # anything with a known, position-independent effect


def load_rows(path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8").replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max((len(r) for r in rows), default=0)
    return [r.ljust(w) for r in rows]


def render(rows: list[str]) -> str:
    return "\n".join(r.rstrip() for r in rows).rstrip("\n") + "\n"


# ------------------------------------------------------------------ the analysis

class Sched:
    def __init__(self, rows: list[str]):
        self.rows = rows
        self.ds = DCE.DeadSet(rows)          # rooms, pipes, reachability, literal protection
        lf = self.ds.lift
        self.lf = lf
        self.rooms = self.ds.rooms
        self.pipes = self.ds.pipes

        # --- per-cell traversal state, unioned over every man.
        # walk() returns cells+edges but not headings, and a cell entered on two headings
        # continues differently, so the walk is re-run here recording (pos, heading).
        self.dirs: dict[tuple[int, int], set] = {}
        self.succ: dict[tuple, set] = {}
        self.pred: dict[tuple, set] = {}
        for st in lf.starts():
            self._walk(st)

    def _walk(self, start):
        seen, stack = set(), [((start[0], start[1]), (1, 0))]
        while stack:
            pos, d = stack.pop()
            if (pos, d) in seen:
                continue
            seen.add((pos, d))
            x, y = pos
            ch = self.lf.at(x, y)
            self.dirs.setdefault(pos, set()).add(d)
            if not self.lf.walkable(x, y) or ch in LIFT.STOP:
                continue
            if ch in LIFT.TURNS:
                outs = [LIFT.TURNS[ch]]
            elif ch in LIFT.BRANCH:
                outs = [d, LIFT.CW[d], LIFT.CCW[d]]
            else:
                outs = [d]
            for nd in outs:
                nxt = (x + nd[0], y + nd[1])
                self.succ.setdefault(pos, set()).add(nxt)
                self.pred.setdefault(nxt, set()).add(pos)
                stack.append((nxt, nd))

    def at(self, x, y) -> str:
        return self.lf.at(x, y)

    def room_of(self, x, y):
        for i, r in enumerate(self.rooms):
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    # ---- the legality predicate -------------------------------------------
    def welded(self, p, d) -> bool:
        """Does every walk that touches p run straight through p -> p+d, and reach p+d only
        that way? If not, some man sees the pair in another order or enters it in the middle,
        and swapping shows him a different instruction."""
        q = (p[0] + d[0], p[1] + d[1])
        if self.dirs.get(p) != {d} or self.dirs.get(q) != {d}:
            return False
        return self.succ.get(p) == {q} and self.pred.get(q) == {p}

    def movable(self, c) -> str | None:
        x, y = c
        ch = self.at(x, y)
        if ch not in MOVABLE:
            return f"'{ch}' is control/unknown"
        if not self.ds.in_room_interior(x, y):
            return "not in a room interior"
        if c in self.ds.protected:
            return "protected (literal / pipe / IO / display)"
        return None

    def nearest_pipe(self, cell, ch):
        """Which pipe `s`/`r`/`q` at this cell resolves to: min Manhattan distance to the
        segment attached to this room, ties by reading order."""
        room = self.room_of(*cell)
        if room is None:
            return None
        want_src = ch in "sS"
        best = None
        for i, pipe in enumerate(self.pipes):
            path = pipe["path"]
            if want_src and pipe.get("src") == room:
                seg = path[0]["pos"]
            elif not want_src and pipe.get("dst") == room:
                seg = path[-1]["pos"]
            else:
                continue
            k = (abs(seg[0] - cell[0]) + abs(seg[1] - cell[1]), seg[1], seg[0], i)
            if best is None or k < best[0]:
                best = (k, i)
        return None if best is None else best[1]

    @staticmethod
    def hazard(a: str, b: str) -> str | None:
        """May instruction `a`, executed before `b`, trade places with it?

        Purely on the characters: RAW / WAR / WAW over A, B, BP. Independence here is what
        makes the register state AFTER the pair identical either way, which is what lets
        everything downstream stay untouched."""
        if a in PIPE_OPS and b in PIPE_OPS:
            return "both touch the pipes (order is observable)"
        ra, wa = RW[a]
        rb, wb = RW[b]
        regs = {A, B, BP}
        if (rb & wa) & regs:
            return f"RAW on {sorted((rb & wa) & regs)}"
        if (ra & wb) & regs:
            return f"WAR on {sorted((ra & wb) & regs)}"
        if (wa & wb) & regs:
            return f"WAW on {sorted((wa & wb) & regs)}"
        return None

    def retargets(self, ch: str, frm, to) -> bool:
        """Would moving `ch` from cell `frm` to cell `to` change which pipe it uses?"""
        return ch in PIPE_OPS and self.nearest_pipe(frm, ch) != self.nearest_pipe(to, ch)

    def deps(self, ca, cb) -> str | None:
        a, b = self.at(*ca), self.at(*cb)
        why = self.hazard(a, b)
        if why:
            return why
        for ch, frm, to in ((a, ca, cb), (b, cb, ca)):
            if self.retargets(ch, frm, to):
                return f"'{ch}' would retarget to a different pipe"
        return None

    def swappable(self, p, d) -> str | None:
        q = (p[0] + d[0], p[1] + d[1])
        if not self.welded(p, d):
            return "not welded (branch/turn/join/two headings)"
        for c in (p, q):
            why = self.movable(c)
            if why:
                return why
        return self.deps(p, q)

    # ---- census ------------------------------------------------------------
    def pairs(self):
        """Every adjacent executed pair, with why it may or may not swap."""
        out = []
        for p, dirs in sorted(self.dirs.items()):
            for d in dirs:
                q = (p[0] + d[0], p[1] + d[1])
                if q not in self.dirs:
                    continue
                out.append((p, q, d, self.swappable(p, d)))
        return out

    def slide_step(self, op: str, src, cur, d) -> str | None:
        """May the op that started at `src` move one more cell, from `cur` to `cur+d`?

        The hazard is between the MOVING OP and the cell it is about to pass — not between
        the two cells as they sit in the grid. (Checking the cells is the tempting bug: an
        `r` that has already slid over three blanks would be compared blank-vs-`s` and waved
        through, when it is the `r` that is about to cross the `s`.)"""
        nxt = (cur[0] + d[0], cur[1] + d[1])
        if not self.welded(cur, d):
            return "not welded (branch/turn/join/two headings)"
        for c in (cur, nxt):
            why = self.movable(c)
            if why:
                return why
        ch = self.at(*nxt)
        why = self.hazard(op, ch)
        if why:
            return why
        if self.retargets(op, src, nxt):          # the moving op lands one cell further out
            return f"'{op}' would retarget to a different pipe"
        if self.retargets(ch, nxt, cur):          # everything it passes shifts back one
            return f"'{ch}' would retarget to a different pipe"
        return None

    def bubbles(self):
        """Per blocking op: how far it can slide later, and past what.

        Repeated adjacent swaps preserve the relative order of the ops passed, so the whole
        slide is legal exactly when every step is; the hazard is re-tested against the moving
        op each time, and the pipe-retarget test against the cell it would land on."""
        out = []
        for p, dirs in sorted(self.dirs.items()):
            if len(dirs) != 1:
                continue
            d = next(iter(dirs))
            op = self.at(*p)
            if op not in BLOCKING:
                continue
            passed, cur = [], p
            while True:
                why = self.slide_step(op, p, cur, d)
                if why:
                    break
                cur = (cur[0] + d[0], cur[1] + d[1])
                passed.append((cur, self.at(*cur)))
            out.append({"cell": p, "op": op, "dir": d,
                        "k": len(passed), "past": passed,
                        "blocked_by": self.slide_step(op, p, cur, d)})
        return out


def apply_bubble(rows, cell, d, k) -> list[str]:
    """Slide the op at `cell` k cells along d; everything it passes shifts back one."""
    grid = [list(r) for r in rows]
    x, y = cell
    op = grid[y][x]
    for i in range(k):
        cx, cy = x + d[0] * i, y + d[1] * i
        nx, ny = x + d[0] * (i + 1), y + d[1] * (i + 1)
        grid[cy][cx] = grid[ny][nx]
    grid[y + d[1] * k][x + d[0] * k] = op
    return ["".join(r) for r in grid]


# ------------------------------------------------------------------ grading

Grader = DCE.Grader          # same contract: one JSON line per candidate, cached, parallel
ok, key, fmt = PO.ok, PO.key, PO.fmt


# ------------------------------------------------------------------ main

def census(sc: Sched, verbose: bool):
    prs = sc.pairs()
    legal = [p for p in prs if p[3] is None]
    # A swap only helps if it issues a BLOCKING op later, so classify by that.
    productive = [p for p in legal if sc.at(*p[0]) in BLOCKING and sc.at(*p[1]) not in BLOCKING]
    reasons: dict[str, int] = {}
    for _p, _q, _d, why in prs:
        if why:
            reasons[why.split(" (")[0]] = reasons.get(why.split(" (")[0], 0) + 1
    bl = sc.bubbles()
    movers = [b for b in bl if b["k"] > 0]
    print(f"   adjacent executed pairs : {len(prs)}")
    print(f"   legally swappable       : {len(legal)}")
    print(f"   ... of which PRODUCTIVE : {len(productive)}   "
          f"(swap issues an r/s/S/R one cell later)")
    print(f"   blocking ops (s/S/r/R)  : {len(bl)};  slidable: {len(movers)};  "
          f"total slide {sum(b['k'] for b in movers)} cell(s)")
    for b in movers:
        past = " ".join(f"{c!r}" for _p, c in b["past"])
        print(f"      {b['op']} at ({b['cell'][0]},{b['cell'][1]}) can slide {b['k']} past [{past}]"
              f"  then blocked by: {b['blocked_by']}")
    if verbose:
        print("   why the rest cannot move:")
        for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"      {n:5d}  {r}")
    return bl, movers


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("file")
    ap.add_argument("--out", default=None, help="output path (default <name>-sched.man)")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--cases", default=None)
    ap.add_argument("--max-waves", type=int, default=6)
    ap.add_argument("--census", action="store_true", help="analysis only: no grading, no output")
    ap.add_argument("--allow-y", action="store_true",
                    help="run even though the program forks; the grade gate is then the only check")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    src = Path(args.file).resolve()
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else src.with_name(src.stem + "-sched.man")
    if out == src:
        print("refusing to overwrite the input file", file=sys.stderr)
        return 2

    rows = load_rows(src)
    t0 = time.time()
    if any("Y" in r for r in rows) and not args.allow_y:
        # The weld test is only sound if `dirs` holds EVERY heading a cell is executed on,
        # and the walk starts only at `@`. A forked man can execute a cell on a heading the
        # walk never saw, which turns "welded" from conservative into wrong.
        print("REFUSING — program contains `Y`: the walk starts only from `@`, so a fork's "
              "headings are missing and the weld test would be unsound. Pass --allow-y to "
              "override (the grade gate is then the only check).")
        return 1
    sc = Sched(rows)
    w0, h0, box0 = PO.footprint(rows)
    print(f"== sched {src.name}  [{args.slug}]   {w0}x{h0} box {box0}   "
          f"{len(sc.rooms)} rooms, {len(sc.pipes)} pipes, {len(sc.lf.starts())} men")
    _bl, movers = census(sc, args.verbose)

    if args.census:
        print(f"   --census: nothing graded, nothing written ({time.time() - t0:.1f}s)")
        return 0
    if not movers:
        print("   NO SLIDABLE BLOCKING OP — scheduling cannot change this program at all.")
        return 0

    with tempfile.TemporaryDirectory(prefix="sched-") as workdir:
        base_g = Grader(args.slug, None, args.cases, workdir)
        base = base_g.grade(render(rows))
        if not ok(base):
            print(f"BASELINE DOES NOT PASS: {json.dumps(base)[:300]}")
            return 1
        worst = max((r.get("settleTick") or 0) for r in base.get("results", [])) or 0
        cap = args.cap if args.cap is not None else max(1000, worst * 4)
        g = Grader(args.slug, cap or None, args.cases, workdir)
        g.cache[render(rows)] = base
        print(f"   baseline: {fmt(base)}  ({base['passed']}/{base['total']} public)")

        cur, best = rows, base
        for wave in range(args.max_waves):
            sc = Sched(cur)
            movers = [b for b in sc.bubbles() if b["k"] > 0]
            if not movers:
                break
            # every prefix of a slide is a distinct schedule, so try them all
            cands = []
            for b in movers:
                for k in range(1, b["k"] + 1):
                    cands.append((b, k, apply_bubble(cur, b["cell"], b["dir"], k)))
            texts = [render(c[2]) for c in cands]
            res = g.grade_many(texts, args.jobs)
            print(f"   wave {wave}: {len(cands)} schedule(s) graded")
            scored = [(key(r), i) for i, r in enumerate(res) if ok(r) and key(r) < key(best)]
            for (b, k, _c), r in zip(cands, res):
                tag = f"{b['op']}({b['cell'][0]},{b['cell'][1]})+{k}"
                print(f"      {tag}: {fmt(r) if ok(r) else (r.get('error') or 'fails cases')}")
            if not scored:
                print(f"   wave {wave}: no schedule beats the baseline")
                break
            scored.sort()
            b, k, cand = cands[scored[0][1]]
            best = res[scored[0][1]]
            cur = cand
            print(f"   + slide {b['op']} at {b['cell']} by {k}: {fmt(best)}")

        print()
        print("== report")
        print(f"   before: {fmt(base)}")
        print(f"   after : {fmt(best)}")
        print(f"   {g.calls} candidate gradings in {time.time() - t0:.1f}s")
        if key(best) >= key(base):
            print("   NO IMPROVEMENT — every legal reordering is score-neutral or worse.")
            print("   This is the expected outcome: the gain of issuing a blocking op k cells")
            print("   later is min(k, stall), and it only reaches the score through the")
            print("   CRITICAL man. Check `node sim/xray.js` — if the critical man's stall")
            print("   share is small, there is nothing here and the answer is elsewhere.")
            return 0
        PO.atomic_write(out, render(cur))
        print(f"   score {base['score']:,.0f} -> {best['score']:,.0f} "
              f"({100 * (1 - best['score'] / base['score']):.2f}% better)")
        print(f"   wrote {out}")
        print(f"   verify: node tools/grade.js {args.slug} {out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
