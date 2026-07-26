#!/usr/bin/env python3
"""smtplace.py — exact SMT floorplanner for .man programs (Z3 proposes, place.py verifies).

place.py's annealer samples floorplans; this tool ASKS Z3 for the minimal-envelope one.
The division of labour is strict:

  Z3 side (this file)    : rigid room rectangles (dims fixed, positions free), pairwise
                           non-overlap with corridor clearance, per-pipe reachability
                           (a route can only be >= |dx|+|dy|-1 cells, and pipe length is
                           latency AND capacity so it must stay >= the original), envelope
                           objective  minimize max(W,H), tie-break minimize total forced
                           pipe-length increase.  All LIA — no routing, no semantics.
  place.py side          : everything that is actually load-bearing.  plan.build() routes
                           every pipe (respecting --pipe-len min), re-checks the four
                           correctness cliffs (nearest-pipe binding under both endpoint
                           readings, R/U reading-order permutation, length floor, wall
                           adjacency), verify_topology() re-parses with the oracle, and
                           the Rust engine grades the result.  smtplace NEVER renders a
                           grid place.py did not bless.

CEGAR: a Z3 model that place.py rejects (unroutable pipe / changed resolution / oracle
parse drift) becomes a no-good cube on the block positions (radius 1), plus a growing
separation floor between the offending pipe's two rooms, and Z3 re-solves.  A verified
improvement tightens the envelope bound and the loop continues until UNSAT / timeout /
iteration cap.  UNSAT under the final bound is a (model-relative) optimality certificate:
no placement with that clearance and pipe-stretch budget fits a smaller box.

Groups (--group "1,2,9"): blocks locked to their ORIGINAL relative offsets and moved as
one rigid cluster.  Pipes internal to a group keep their exact original route (translated
verbatim), so a FIFO belt whose pipe lengths are storage is untouchable by construction.

  python3 tools/smtplace.py <slug> <file.man> [--gap 2] [--pipe-len min] [--extra 8]
        [--group "i,j,k" ...] [--iters 20] [--timeout 60] [--out X.man] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import z3  # noqa: E402

import lift as LIFT  # noqa: E402
import place as PLACE  # noqa: E402


# ── robust analyze ────────────────────────────────────────────────────────────
# lift.analyze pipes the oracle's JSON through console.log and then process.exit(0),
# which truncates unflushed stdout on large grids (pathfinder's 381x496 dies there).
# Same call, but the JSON goes through a file.  Patching the lift module patches
# place.py too (same module object).

_orig_analyze = LIFT.analyze


def _analyze_file(rows):
    script = (
        "const fs=require('fs');"
        "const {boot}=require(process.argv[1]+'/sim/harness.js');"
        "(async()=>{const w=await boot();"
        "const rows=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
        "fs.writeFileSync(process.argv[3],String(w.analyze(rows)));process.exit(0)})()"
        ".catch(e=>{fs.writeFileSync(process.argv[3],"
        "JSON.stringify({type:'error',message:String(e)}));process.exit(1)})"
    )
    fd, tmp = tempfile.mkstemp(suffix=".rows.json")
    fd2, out = tempfile.mkstemp(suffix=".topo.json")
    os.close(fd2)
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(rows, fh)
        subprocess.run(["node", "-e", script, str(REPO), tmp, out],
                       capture_output=True, text=True, cwd=REPO, timeout=300)
        with open(out, encoding="utf-8") as fh:
            data = fh.read().strip()
        if not data:
            return {"type": "error", "message": "analyze produced no output"}
        return json.loads(data)
    except Exception as exc:  # noqa: BLE001
        return {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
    finally:
        for f in (tmp, out):
            try:
                os.unlink(f)
            except OSError:
                pass


LIFT.analyze = _analyze_file


class GroupPlan(PLACE.Plan):
    """Plan whose route reuse also accepts a uniformly TRANSLATED original route.

    When both endpoints of a pipe moved by the same delta (a rigid group move), the
    original route translated by that delta has identical length, shape and relative
    geometry — reusing it keeps every FIFO/latency property bit-exact instead of hoping
    the router rediscovers an equivalent serpentine.  The resolution and topology gates
    still run on the result, so this is an optimisation, not a bypass."""

    def route_all(self, layout, pipe_len="free", margin=8, order=None, retries=3,
                  tighten=False):
        """Route reusable pipes FIRST so they claim their own original cells.

        place.py's longest-first order lets a re-routed 300-cell serpentine steal cells
        from a pipe that did not move at all; when that pipe's turn comes its original
        route is blocked and the router fails in a maze of its neighbours' combs.  A
        pipe whose two endpoints moved by one common delta will simply reclaim its own
        (translated) route, so those go first, then the truly-moved ones longest-first."""
        if order is not None:
            return super().route_all(layout, pipe_len=pipe_len, margin=margin,
                                     order=order, retries=retries, tighten=tighten)
        base = self.base_layout()
        reusable, rest = [], []
        slack = {}
        for p in self.pipes:
            s, d = self.ends(layout, p)
            s0, d0 = self.ends(base, p)
            ds = (s[0] - s0[0], s[1] - s0[1])
            dd = (d[0] - d0[0], d[1] - d0[1])
            if ds == dd:
                reusable.append(p.idx)
            else:
                rest.append(p.idx)
                md = abs(s[0] - d[0]) + abs(s[1] - d[1])
                slack[p.idx] = p.length - (md - 1)
        # tightest-first: a net with no winding slack has exactly one corridor that
        # works, while a big-deficit serpentine can comb into whatever is left.
        rest.sort(key=lambda i: (slack[i], -self.pipes[i].length))
        # retry policy: the loser goes to the front of REST only — never above the
        # reusable pipes, whose reserved original cells are the one stable thing here
        # (place.py's own retry promotes the loser above them, evicting their routes
        # and turning one failure into a different failure every pass).
        last = None
        for _ in range(max(retries, 4)):
            paths, bad = self._route_pass(layout, pipe_len, margin,
                                          reusable + rest, tighten)
            if paths is not None:
                return paths, None
            last = bad
            if bad in reusable:
                reusable.remove(bad)     # cannot actually reuse -> it is a mover
            elif bad in rest:
                rest.remove(bad)
            rest.insert(0, bad)
        return self._shuffle_route(layout, pipe_len, margin, reusable + rest,
                                   tighten, last, fixed=reusable)

    def _reuse(self, p, src, dst, occ, taken, core=None):
        keep = super()._reuse(p, src, dst, occ, taken, core)
        if keep is not None:
            return keep
        osrc = (p.cells[0][0] - p.dirs[0][0], p.cells[0][1] - p.dirs[0][1])
        odst = (p.cells[-1][0] + p.dirs[-1][0], p.cells[-1][1] + p.dirs[-1][1])
        d = (src[0] - osrc[0], src[1] - osrc[1])
        if (dst[0] - odst[0], dst[1] - odst[1]) != d:
            return None
        cells = [(x + d[0], y + d[1]) for x, y in p.cells]
        for c in cells:
            if c in occ or c in taken:
                return None
            if core and not (core[0] <= c[0] <= core[2] and core[1] <= c[1] <= core[3]):
                return None
        return cells, list(p.dirs)


# ── the SMT model ─────────────────────────────────────────────────────────────


def zabs(e):
    return z3.If(e >= 0, e, -e)


class Model:
    def __init__(self, plan, groups, gap, extra_cap, base_maxdim, verbose=False,
                 deficit=24, parity=False, fan_order="wall", move_cap=0,
                 objectives="m", max_m=0, free_len=False):
        self.plan = plan
        self.gap = gap
        self.verbose = verbose
        n = len(plan.blocks)
        self.X = [z3.Int(f"x{i}") for i in range(n)]
        self.Y = [z3.Int(f"y{i}") for i in range(n)]
        self.opt = z3.Optimize()
        o = self.opt

        # group membership: gid[i] == leader index (or i itself when free)
        self.gid = list(range(n))
        for g in groups:
            lead = g[0]
            for i in g:
                self.gid[i] = lead

        # anchor = largest block, pinned at its original offset (kills translation
        # symmetry; also keeps any orphan cells, which never move, consistent).
        areas = [b.w * b.h for b in plan.blocks]
        self.anchor = max(range(n), key=lambda i: areas[i])
        ax, ay = plan.blocks[self.anchor].ox0, plan.blocks[self.anchor].oy0
        o.add(self.X[self.anchor] == ax, self.Y[self.anchor] == ay)

        # domain: nothing ever needs to sit further than one baseline box away
        dom = base_maxdim + 4
        for i in range(n):
            o.add(self.X[i] >= ax - dom, self.X[i] <= ax + dom)
            o.add(self.Y[i] >= ay - dom, self.Y[i] <= ay + dom)

        # move cap: a hard leash on how far a block may travel from where it is.
        # Optimize() over 22 blocks in a +-216 domain does not converge (measured:
        # `unknown` after 120s on snake, so not one candidate was ever produced), and
        # the moves that actually shrink a generated floorplan are SMALL -- snake's
        # 212 -> ~200 needs the RAM hub up 12 rows and its satellites up 4.  A leash
        # both shrinks the domain by an order of magnitude and keeps every block near
        # enough that place.py's route reuse still fires.
        if move_cap:
            for i in range(n):
                if i == self.anchor:
                    continue
                b = plan.blocks[i]
                o.add(self.X[i] >= b.ox0 - move_cap, self.X[i] <= b.ox0 + move_cap)
                o.add(self.Y[i] >= b.oy0 - move_cap, self.Y[i] <= b.oy0 + move_cap)

        # rigid groups: original relative offsets
        for i in range(n):
            j = self.gid[i]
            if j != i:
                o.add(self.X[i] - self.X[j] ==
                      plan.blocks[i].ox0 - plan.blocks[j].ox0)
                o.add(self.Y[i] - self.Y[j] ==
                      plan.blocks[i].oy0 - plan.blocks[j].oy0)

        # pairwise non-overlap with clearance.  Required separation is the corridor
        # gap, but never MORE than the champion's own original separation: if two
        # rooms already sit 0 apart legally, holding them to 2 would be UNSAT-by-fiat.
        self.sep_extra = {}
        for i in range(n):
            for j in range(i + 1, n):
                if self.gid[i] == self.gid[j]:
                    continue  # rigid relative geometry, legal by construction
                s = min(gap, self._orig_sep(i, j))
                self._add_sep(i, j, s)

        self.fan_pairs = self._add_fan_order(fan_order)

        # fixed obstacles: orphan cells (place.py never moves them)
        if plan.orphans:
            oxs = [x for x, _ in plan.orphans]
            oys = [y for _, y in plan.orphans]
            self.orphan_rect = (min(oxs), min(oys), max(oxs), max(oys))
        else:
            self.orphan_rect = None

        # pipes: a route between wall cells (x1,y1)-(x2,y2) has >= |dx|+|dy|-1 cells,
        # can always be padded LONGER (space permitting) but never shorter.  Length is
        # capacity, so md-1 <= L + extra with extra >= 0 capped and minimised.
        self.extras = []
        for p in plan.pipes:
            if self.gid[p.src_b] == self.gid[p.dst_b]:
                continue  # internal to a group: exact original route reused
            e1x = self.X[p.src_b] + p.src_off[0]
            e1y = self.Y[p.src_b] + p.src_off[1]
            e2x = self.X[p.dst_b] + p.dst_off[0]
            e2y = self.Y[p.dst_b] + p.dst_off[1]
            md = zabs(e1x - e2x) + zabs(e1y - e2y)
            o.add(md >= 2)
            ex = z3.Int(f"ext{p.idx}")
            o.add(ex >= 0, ex >= md - 1 - p.length)
            if extra_cap is not None:
                o.add(md - 1 <= p.length + extra_cap)
            # the router pads a route up to the pipe's length with sideways bulges, and
            # measured on this repo's champions that fails once the deficit is large in
            # a tight corridor.  Cap how much winding a placement may DEMAND: no more
            # than the original layout demanded (that much provably routed — the
            # champion is the proof), plus a little slack.
            s1, d1 = plan.ends(plan.base_layout(), p)
            orig_deficit = p.length - (abs(s1[0] - d1[0]) + abs(s1[1] - d1[1]) - 1)
            if free_len:
                # --pipe-len free: the router takes the SHORTEST route, so nothing has
                # to be wound and a pipe may come out shorter than the champion's.  That
                # is a real risk (a pipe's length is also its FIFO capacity) but it is
                # the constraint that pins snake's satellite band 40 rows below its hub:
                # pipe 21 must stay >= 101 cells, so its two ends may not approach closer
                # than md=60, and M=200 is UNSAT purely because of that.  Shorter pipes
                # also cost FEWER ticks, so when the grade still passes this is a win on
                # both terms of the score.
                pass
            else:
                o.add(md - 1 >= p.length - max(deficit, orig_deficit))
            if parity:
                # any route between these endpoints has length ≡ md-1 (mod 2), so an
                # EXACT-length route exists only when md keeps the original parity —
                # needed when even a +1 padding overshoot changes a q-depth count.
                omd = abs(s1[0] - d1[0]) + abs(s1[1] - d1[1])
                o.add((e1x - e2x + e1y - e2y) % 2 == omd % 2)
            self.extras.append(ex)

        # envelope
        self.X0, self.X1 = z3.Int("X0"), z3.Int("X1")
        self.Y0, self.Y1 = z3.Int("Y0"), z3.Int("Y1")
        self.M = z3.Int("M")
        for i in range(n):
            b = plan.blocks[i]
            o.add(self.X0 <= self.X[i], self.X[i] + b.w <= self.X1)
            o.add(self.Y0 <= self.Y[i], self.Y[i] + b.h <= self.Y1)
        if self.orphan_rect:
            x0, y0, x1, y1 = self.orphan_rect
            o.add(self.X0 <= x0, x1 + 1 <= self.X1)
            o.add(self.Y0 <= y0, y1 + 1 <= self.Y1)
        o.add(self.M >= self.X1 - self.X0, self.M >= self.Y1 - self.Y0)

        # a pipe attaching to a display (or any block) side that faces the envelope
        # edge needs room to come AROUND: the route approaches a bottom attachment from
        # below, so the envelope must extend a few rows past it, or the router starves.
        for p in plan.pipes:
            for bi, off in ((p.src_b, p.src_off), (p.dst_b, p.dst_off)):
                b = plan.blocks[bi]
                if b.kind != "display":
                    continue
                if off[1] == b.h - 1:                       # bottom wall attachment
                    o.add(self.Y1 >= self.Y[bi] + b.h + 3)
                if off[1] == 0:                             # top wall attachment
                    o.add(self.Y[bi] - self.Y0 >= 3)
                if off[0] == 0:                             # left wall attachment
                    o.add(self.X[bi] - self.X0 >= 3)

        # area certificate: every block cell and every pipe cell must fit in the box,
        # so M^2 >= total cells — a constant lower bound, and the honest floor of what
        # any floorplanner could ever reach.
        total = sum(areas) + sum(p.length for p in plan.pipes) + len(plan.orphans)
        self.area_lb = int(total ** 0.5) + (0 if int(total ** 0.5) ** 2 >= total else 1)
        o.add(self.M >= self.area_lb)

        o.add(self.M <= base_maxdim - 1)     # only strict improvements are interesting
        if max_m:
            # ask for a TARGET envelope instead of the optimum.  Proving optimality is
            # what makes Optimize() diverge here; a target turns the whole thing into a
            # satisfiability question, and the CEGAR loop still tightens on every win.
            o.add(self.M <= max_m)
        # move as little as possible.  Endpoints that keep their EXACT original position
        # keep their original route verbatim (place.py's reuse), which routes a heavily
        # padded champion pipe with certainty where the padder may fail.
        move = []
        for i in range(n):
            if self.gid[i] != i or i == self.anchor:
                continue
            move.append(zabs(self.X[i] - plan.blocks[i].ox0))
            move.append(zabs(self.Y[i] - plan.blocks[i].oy0))
        # objective policy.  `minimize(M)` has to PROVE that no smaller envelope exists,
        # and on a generated 22-block floorplan that does not terminate (measured: Optimize
        # returns `unknown` after 180s on snake without ever emitting a candidate, so the
        # CEGAR loop never starts).  `--max-m T --objective move` turns the same question
        # into "the least-disturbed layout that fits in T", which is both a satisfiability
        # query and exactly the bias place.py's route reuse wants.
        if objectives == "m":
            self.h_M = o.minimize(self.M)
            if self.extras:
                o.minimize(z3.Sum(self.extras))
            if move:
                o.minimize(z3.Sum(move))
        elif objectives == "move":
            if move:
                o.minimize(z3.Sum(move))
        # "none": pure satisfiability

    # ── fan ordering: the constraint that makes a proposal ROUTABLE ───────────
    @staticmethod
    def _walls(b, off):
        w = set()
        if off[1] == 0:
            w.add("T")
        if off[1] == b.h - 1:
            w.add("B")
        if off[0] == 0:
            w.add("L")
        if off[0] == b.w - 1:
            w.add("R")
        return w

    def _add_fan_order(self, mode):
        """Keep every port fan NESTED: pipes leaving one wall of one block must reach
        their far ends in the same relative order as the ports they hang off.

        This is the constraint whose absence produced `pipe N unroutable` on every
        snake/pathfinder proposal.  Neither program's room graph forces a crossing —
        both are near-trees (snake: 22 rooms, 23 simple edges, 2 independent cycles;
        three hubs, no hub-hub edge) — so an unroutable Z3 model is never a topology
        failure, it is an ORDER failure: the hub's ports are at a fixed pitch along one
        wall and the satellites they serve are interchangeable as far as the model can
        see, so Z3 permutes them and turns a properly nested fan into an interleaved one
        that no planar routing exists for.  Pipe k of snake's hub #20 joins the k-th
        port column to the k-th satellite; swap any two satellites and those two pipes
        must cross.

        The encoding is deliberately the cheapest thing that expresses it: for every
        pair of pipes touching one wall of one block, the far endpoints keep the SIGN of
        their original coordinate difference, on both axes.  Strict orders only — a tie
        (all sixteen satellites share a row) constrains nothing, so a fan may still be
        re-shaped, just not re-ordered.  Every constraint is a strict linear inequality
        over two position variables, i.e. purely conjunctive: it PRUNES the search
        instead of adding disjunctions, and the original layout satisfies all of them by
        construction, so the model can never be made UNSAT by this alone.

        mode: "off" (skip), "wall" (pairs sharing a wall of the shared block — the
        default), "all" (every pair touching the shared block).
        """
        if mode == "off":
            return 0
        plan = self.plan
        touch = {}
        for p in plan.pipes:
            touch.setdefault(p.src_b, []).append((p.idx, p.src_off, p.dst_b, p.dst_off))
            touch.setdefault(p.dst_b, []).append((p.idx, p.dst_off, p.src_b, p.src_off))
        added = 0
        for bi, lst in sorted(touch.items()):
            b = plan.blocks[bi]
            for ia in range(len(lst)):
                for ib in range(ia + 1, len(lst)):
                    _, oa, fa, ofa = lst[ia]
                    _, ob, fb, ofb = lst[ib]
                    if mode == "wall" and not (self._walls(b, oa) & self._walls(b, ob)):
                        continue
                    # two far ends inside one rigid group (or the same block) are at a
                    # constant offset from each other: the relation already holds.
                    if self.gid[fa] == self.gid[fb]:
                        continue
                    for axis in (0, 1):
                        V = self.X if axis == 0 else self.Y
                        ba = plan.blocks[fa]
                        bb = plan.blocks[fb]
                        pa = (ba.ox0 if axis == 0 else ba.oy0) + ofa[axis]
                        pb = (bb.ox0 if axis == 0 else bb.oy0) + ofb[axis]
                        if pa == pb:
                            continue
                        ea = V[fa] + ofa[axis]
                        eb = V[fb] + ofb[axis]
                        self.opt.add(ea < eb if pa < pb else ea > eb)
                        added += 1
        return added

    def _orig_sep(self, i, j):
        a, b = self.plan.blocks[i], self.plan.blocks[j]
        ax0, ay0, ax1, ay1 = a.rect(a.ox0, a.oy0)
        bx0, by0, bx1, by1 = b.rect(b.ox0, b.oy0)
        dx = max(bx0 - ax1 - 1, ax0 - bx1 - 1)
        dy = max(by0 - ay1 - 1, ay0 - by1 - 1)
        return max(dx, dy, 0)

    def _add_sep(self, i, j, s):
        a, b = self.plan.blocks[i], self.plan.blocks[j]
        self.sep_extra[(i, j)] = s
        self.opt.add(z3.Or(
            self.X[i] + a.w + s <= self.X[j],
            self.X[j] + b.w + s <= self.X[i],
            self.Y[i] + a.h + s <= self.Y[j],
            self.Y[j] + b.h + s <= self.Y[i]))

    def bump_sep(self, i, j):
        """A pipe between i and j keeps failing to route: demand more corridor."""
        key = (min(i, j), max(i, j))
        s = self.sep_extra.get(key, 0) + 1
        if s > self.gap + 6:
            return False
        self._add_sep(key[0], key[1], s)
        return True

    def no_good(self, offsets, radius=1):
        """Exclude a cube around a rejected placement (free blocks only)."""
        lits = []
        for i, (vx, vy) in enumerate(offsets):
            if i == self.anchor or self.gid[i] != i:
                continue
            lits.append(z3.Or(self.X[i] <= vx - radius - 1,
                              self.X[i] >= vx + radius + 1,
                              self.Y[i] <= vy - radius - 1,
                              self.Y[i] >= vy + radius + 1))
        if lits:
            self.opt.add(z3.Or(lits))

    def solve(self, timeout_s):
        self.opt.set("timeout", int(timeout_s * 1000))
        t0 = time.time()
        res = self.opt.check()
        dt = time.time() - t0
        if res == z3.sat:
            m = self.opt.model()
            offsets = tuple((m[self.X[i]].as_long(), m[self.Y[i]].as_long())
                            for i in range(len(self.plan.blocks)))
            return "sat", offsets, m[self.M].as_long(), dt
        return ("unsat" if res == z3.unsat else "unknown"), None, None, dt


# ── grading ───────────────────────────────────────────────────────────────────


def grade_fast(slug, text, jobs=4, cap=None):
    fd, tmp = tempfile.mkstemp(suffix=".man", dir=str(REPO / "solutions"))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        cmd = [sys.executable, str(REPO / "tools" / "grade_fast.py"), slug, tmp,
               "--jobs", str(jobs)]
        if cap:
            cmd += ["--cap", str(cap)]
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=3600)
        for ln in reversed(p.stdout.splitlines()):
            ln = ln.strip()
            if ln.startswith("{"):
                return json.loads(ln)
        return {"error": (p.stderr or p.stdout or "no output").strip()[:300]}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def ok(res):
    return (isinstance(res, dict) and "error" not in res
            and res.get("total") and res.get("passed") == res.get("total"))


# ── the loop ──────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--gap", type=int, default=2)
    ap.add_argument("--extra", type=int, default=8,
                    help="hard cap on forced length increase per pipe (latency budget)")
    ap.add_argument("--pipe-len", choices=("free", "min", "exact"), default="min",
                    help="'free' lets a pipe come out SHORTER than the original — fewer "
                         "ticks and far more placement freedom, but a pipe used as a FIFO "
                         "store loses capacity, so the grade is the only gate")
    ap.add_argument("--margin", type=int, default=8)
    ap.add_argument("--group", action="append", default=[],
                    help="comma-separated block indices moved as one rigid cluster")
    ap.add_argument("--deficit", type=int, default=24,
                    help="max extra winding (length minus straight distance) a placement "
                         "may demand of a pipe beyond what the original layout demanded")
    ap.add_argument("--min-m", type=int, default=0,
                    help="start the envelope no tighter than this (routing headroom); "
                         "wins still tighten the bound from there")
    ap.add_argument("--route-tries", type=int, default=0,
                    help="extra random net orders per proposal before calling a "
                         "floorplan unroutable (place.Plan._shuffle_route)")
    ap.add_argument("--no-route-guard", action="store_true",
                    help="allow a new route to run alongside a room wall, as the "
                         "original program's own routes already do (required for a "
                         "tight --gap; the grade is then the only gate)")
    ap.add_argument("--max-m", type=int, default=0,
                    help="ask for max(W,H) <= N (satisfiability) instead of the optimum")
    ap.add_argument("--objective", choices=("m", "move", "none"), default="m",
                    help="'m' minimises the envelope (proves optimality — does not "
                         "converge past ~20 blocks); 'move' minimises total block "
                         "displacement subject to --max-m; 'none' pure satisfiability")
    ap.add_argument("--move-cap", type=int, default=0,
                    help="max cells a block may move from its original offset "
                         "(0 = unlimited; a leash makes Optimize() converge)")
    ap.add_argument("--fan-order", choices=("off", "wall", "all"), default="wall",
                    help="keep port fans nested (see Model._add_fan_order): 'wall' "
                         "constrains pipe pairs sharing a wall, 'all' every pair "
                         "sharing a block, 'off' reproduces the old unordered model")
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--timeout", type=float, default=60.0, help="per-solve seconds")
    ap.add_argument("--time-limit", type=float, default=1800.0, help="whole-run seconds")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--cap", type=int)
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true",
                    help="stop after the first verified floorplan; do not grade")
    ap.add_argument("--no-grade", action="store_true")
    ap.add_argument("--no-tighten", action="store_true",
                    help="keep out-of-envelope original routes instead of re-deriving "
                         "them (a reused route outside the block box pins the old box)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    plan = GroupPlan(args.man)
    # New routes must not graze ANY wall (see place.py) — except that a program whose
    # OWN routes graze walls cannot be re-routed under that rule at all once the
    # floorplan is tight: with --gap 1 every corridor is one cell wide, so any pipe in
    # it touches both walls and the guard rejects it.  Measured on snake at M=204: every
    # Z3 model died with "pipe N unroutable" until the guard came off.  The grade is then
    # the gate, exactly as it is for the champion this program already is.
    plan.route_guard = not args.no_route_guard
    plan.route_shuffles = args.route_tries
    n = len(plan.blocks)
    print(f"{Path(args.man).name}: {n} blocks, {len(plan.pipes)} pipes, "
          f"{len(plan.orphans)} orphans, adjacency guard "
          f"{'on' if plan.adjacency_ok_base else 'OFF'}")

    # round-trip gate (same as place.py: refuse to touch what we cannot reproduce)
    want = "\n".join(r.rstrip() for r in plan.rows).rstrip("\n") + "\n"
    got = PLACE.render(plan.draw(plan.base_offsets, plan.pipe_paths_original()))
    if got != want:
        raise SystemExit("round-trip mismatch — refusing to place")
    print("  round-trip OK")

    base_cells = plan.draw(plan.base_offsets, plan.pipe_paths_original())
    bw, bh, bbox = PLACE.box_of(base_cells)
    base_maxdim = max(bw, bh)
    print(f"  baseline {bw}x{bh} box {bbox}")

    groups = []
    for spec in args.group:
        g = sorted(int(t) for t in spec.replace(";", ",").split(",") if t.strip())
        if len(g) > 1:
            groups.append(g)

    model = Model(plan, groups, args.gap, args.extra, base_maxdim, args.verbose,
                  deficit=args.deficit, parity=args.pipe_len == "exact",
                  fan_order=args.fan_order, move_cap=args.move_cap,
                  objectives=args.objective, max_m=args.max_m,
                  free_len=args.pipe_len == "free")
    if args.min_m:
        model.opt.add(model.M >= args.min_m)
    print(f"  SMT: anchor block {model.anchor}, groups {groups or 'none'}, "
          f"area lower bound M >= {model.area_lb} "
          f"(baseline M = {base_maxdim}), fan-order {args.fan_order} "
          f"({model.fan_pairs} constraints), move-cap "
          f"{args.move_cap or 'none'}, objective {args.objective}"
          f"{' <= ' + str(args.max_m) if args.max_m else ''}")

    base_res = None
    if not args.no_grade:
        base_res = grade_fast(args.slug, want, args.jobs, args.cap)
        if not ok(base_res):
            raise SystemExit(f"baseline fails locally: {base_res}")
        print(f"  baseline grade: {base_res['passed']}/{base_res['total']} "
              f"score {base_res['score']:,.0f}")

    t_start = time.time()
    best = None            # (score, text, res, w, h)
    pair_fail = {}
    m_fail = [None, 0]     # routing failures at the same proposed M: after a few, the
    stats = {"sat": 0, "unsat": 0, "unknown": 0, "routing_fail": 0,
             "resolution_fail": 0, "topo_fail": 0, "grade_fail": 0}

    for it in range(1, args.iters + 1):
        if time.time() - t_start > args.time_limit:
            print(f"  [{it}] overall time limit reached")
            break
        status, offsets, mval, dt = model.solve(args.timeout)
        stats[status] += 1
        if status == "unsat":
            print(f"  [{it}] UNSAT in {dt:.1f}s — no smaller floorplan exists under "
                  f"(gap<={args.gap}, extra<={args.extra}, current bound); "
                  f"model-relative optimality certificate")
            break
        if status == "unknown":
            print(f"  [{it}] solver timeout ({dt:.1f}s) — stopping")
            break
        lay = (offsets, plan.base_layout()[1])
        print(f"  [{it}] Z3 proposes block-envelope M={mval} ({dt:.1f}s) — verifying")

        cells, err, paths = plan.build(lay, pipe_len=args.pipe_len, margin=args.margin,
                                       tighten=not args.no_tighten)
        if cells is None:
            print(f"      place.py rejects: {err}")
            model.no_good(offsets)
            if err and err.startswith("pipe") and "unroutable" in err:
                stats["routing_fail"] += 1
                pi = int(err.split()[1])
                p = plan.pipes[pi]
                key = (min(p.src_b, p.dst_b), max(p.src_b, p.dst_b))
                pair_fail[key] = pair_fail.get(key, 0) + 1
                if pair_fail[key] >= 2:
                    model.bump_sep(*key)
                    pair_fail[key] = 0
                # a long pipe that cannot wind is an AREA problem, not a pair problem:
                # after repeated failures at the same envelope, demand a roomier one.
                if m_fail[0] == mval:
                    m_fail[1] += 1
                    if m_fail[1] >= 4:
                        print(f"      4 routing failures at M={mval} — relaxing to "
                              f"M >= {mval + 1}")
                        model.opt.add(model.M >= mval + 1)
                        m_fail = [None, 0]
                else:
                    m_fail = [mval, 1]
            elif err == "nearest-pipe resolution changed":
                stats["resolution_fail"] += 1
            continue
        bad = PLACE.verify_topology(plan, cells, lay)
        if bad:
            print(f"      oracle rejects: {bad}")
            stats["topo_fail"] += 1
            model.no_good(offsets)
            continue
        w, h, box = PLACE.box_of(cells)
        text = PLACE.render(PLACE.trimmed(cells))
        real_m = max(w, h)
        print(f"      routed+verified: {w}x{h} box {box}")
        if box >= (best[3] if best else bbox):
            model.no_good(offsets)
            model.opt.add(model.M <= real_m - 1)
            continue
        if args.no_grade or args.dry_run:
            out = Path(args.out or str(Path(args.man).with_suffix("")) + "-smt.man")
            out.write_text(text, encoding="utf-8")
            print(f"      wrote {out} (ungraded)")
            if args.dry_run:
                return 0
            best = (None, text, None, box, w, h)
            model.opt.add(model.M <= real_m - 1)
            continue
        res = grade_fast(args.slug, text, args.jobs, args.cap)
        if not ok(res) or res["score"] >= base_res["score"]:
            print(f"      grade rejects: "
                  f"{res.get('error') or ('%s/%s score %s' % (res.get('passed'), res.get('total'), res.get('score')))}")
            stats["grade_fail"] += 1
            model.no_good(offsets)
            continue
        print(f"      ACCEPTED {w}x{h} box {box} score {res['score']:,.0f} "
              f"(baseline {base_res['score']:,.0f})")
        if best is None or res["score"] < best[0]:
            best = (res["score"], text, res, box, w, h)
            out = Path(args.out or str(Path(args.man).with_suffix("")) + "-smt.man")
            out.write_text(text, encoding="utf-8")
            print(f"      wrote {out}")
        model.opt.add(model.M <= real_m - 1)

    print(f"  stats: {stats}, elapsed {time.time()-t_start:.0f}s")
    if best and best[0] is not None:
        print(f"  BEST: {best[4]}x{best[5]} box {best[3]} score {best[0]:,.0f} "
              f"vs baseline {base_res['score']:,.0f} "
              f"({100*(1-best[0]/base_res['score']):.1f}% lower)")
    elif best:
        print(f"  BEST (ungraded): {best[4]}x{best[5]} box {best[3]}")
    else:
        print("  no verified improvement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
