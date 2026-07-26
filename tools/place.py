#!/usr/bin/env python3
"""place.py — the optimizing compiler's PLACER.

`tools/lift.py` says what a program IS, `tools/emit.py` turns an IR back into a grid.
This is the pass in between that MOVES code: it re-places whole rooms (with their men
and all their instruction cells carried rigidly along) and re-routes every pipe between
them, searching for a floorplan with a smaller `max(width,height)`.

WHY RIGID ROOMS. Score = max(w,h)^2 * avgTicks. Every champion in this repo is 51-89%
blank, but most of that blankness is *between* rooms, not inside them: tcp stacks a
22x20 room on top of a 17x11 room that share no columns, and pays 41 rows for 31 rows of
content. A rigid room move is the one placement move that CANNOT change a man's walk —
every cell he touches moves with him — so the only things that can break are the pipes,
and those are exactly what this pass re-routes and re-checks.

THE FOUR CORRECTNESS CLIFFS (each silent — no error, just a wrong answer):
  1. `r`/`s`/`q` bind to the NEAREST pipe by Manhattan distance with reading-order ties.
     Every pipe op in every room is re-resolved after placement and the candidate is
     rejected unless every single one still binds to the SAME pipe. Because the oracle's
     definition of "the pipe segment attached to the room" is not pinned down by the
     prose, resolution is computed under BOTH readings (endpoint cell only, and the whole
     straight run leading into the room) and both must agree with the original.
  2. `R`/`U` pick among ready incoming pipes in READING ORDER, not by distance, so the
     reading-order permutation of each room's incoming pipes is preserved too.
  3. Pipe length is BOTH latency and capacity (some designs use a pipe as a FIFO store),
     so `--pipe-len min` refuses any route shorter than the original and `exact` refuses
     any length change at all.
  4. A pipe that merely runs ALONGSIDE a room's wall can read as an extra attachment
     (fatal for an I/O room, which is allowed exactly one). The adjacency guard forbids a
     pipe cell from touching a room border anywhere but at its own two endpoints — and is
     auto-disabled when the ORIGINAL program already violates it, so this pass never
     holds a candidate to a standard the champion does not meet.

Everything else is a hard gate: the plan must round-trip (re-render the original layout
byte-for-byte before any move is allowed), and a candidate is accepted only when the real
oracle says it passes EVERY public case and scores strictly lower. Output goes to a NEW
file; the input is never modified.

  python3 tools/place.py <slug> <file.man> --dry-run          # plan + round-trip gate
  python3 tools/place.py <slug> <file.man> --budget 4000      # search + grade
  python3 tools/place.py <slug> <file.man> --plan moves.json  # replay a hand-written plan
"""
from __future__ import annotations

import argparse
import concurrent.futures
import heapq
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
GRADER = REPO / "tools" / "grade_json.js"

import lift as LIFT  # noqa: E402  (repo tool, path set above)

PIPE_OPS = set("sSrRqU")
OUT_OPS = set("sS")
IN_OPS = set("rRqU")
DIRS4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
ARROW = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}
BEND_COST = 2.0
GROW_COST = 30.0


# ═══════════════════════════════════════════════════════════════════ the plan


class Block:
    """A rigid rectangle of glyphs: a room (with its man and all his code) or a display.

    Nothing inside is ever rewritten, which is what makes the move safe."""

    __slots__ = ("kind", "idx", "w", "h", "glyphs", "ox", "oy", "ox0", "oy0")

    def __init__(self, kind, idx, x0, y0, x1, y1, rows):
        self.kind, self.idx = kind, idx
        self.w, self.h = x1 - x0 + 1, y1 - y0 + 1
        self.glyphs = {}
        for y in range(y0, y1 + 1):
            row = rows[y] if y < len(rows) else ""
            for x in range(x0, x1 + 1):
                ch = row[x] if x < len(row) else " "
                if ch != " ":
                    self.glyphs[(x - x0, y - y0)] = ch
        self.ox0, self.oy0 = x0, y0
        self.ox, self.oy = x0, y0

    def cells(self, ox, oy):
        return {(ox + dx, oy + dy) for dx, dy in self.glyphs}

    def rect(self, ox, oy):
        return (ox, oy, ox + self.w - 1, oy + self.h - 1)

    def border(self, ox, oy):
        out = set()
        x1, y1 = ox + self.w - 1, oy + self.h - 1
        for x in range(ox, x1 + 1):
            out.add((x, oy))
            out.add((x, y1))
        for y in range(oy, y1 + 1):
            out.add((ox, y))
            out.add((x1, y))
        return out

    def interior(self, ox, oy):
        return [(x, y)
                for y in range(oy + 1, oy + self.h - 1)
                for x in range(ox + 1, ox + self.w - 1)]


class Pipe:
    __slots__ = ("idx", "src_b", "src_off", "dst_b", "dst_off", "cells", "dirs", "length")

    def __init__(self, idx, cells, dirs):
        self.idx = idx
        self.cells, self.dirs = cells, dirs
        self.length = len(cells)


def load_rows(path):
    text = Path(path).read_text(encoding="utf-8").replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max((len(r) for r in rows), default=0)
    return [r.ljust(w) for r in rows]


def render(cells):
    if not cells:
        return ""
    w = max(x for x, _ in cells) + 1
    h = max(y for _, y in cells) + 1
    grid = [[" "] * w for _ in range(h)]
    for (x, y), ch in cells.items():
        grid[y][x] = ch
    return "\n".join("".join(r).rstrip() for r in grid).rstrip("\n") + "\n"


def trimmed(cells):
    """Shift a cell map so its bounding box starts at (0,0) — margins are free.

    This is not cosmetic: a routed pipe may bulge to a negative coordinate, and `render`
    indexes a plain list, so an untrimmed negative cell wraps to the far edge of the grid
    and silently deletes a room."""
    if not cells:
        return cells
    mx = min(x for x, _ in cells)
    my = min(y for _, y in cells)
    return {(x - mx, y - my): ch for (x, y), ch in cells.items()}


class Plan:
    def __init__(self, path):
        self.path = Path(path)
        self.rows = load_rows(path)
        self.topo = LIFT.analyze(self.rows)
        if self.topo.get("type") == "error":
            raise SystemExit(f"analyze failed: {self.topo.get('message')}")
        self.blocks = []
        for i, r in enumerate(self.topo.get("rooms") or []):
            (x0, y0), (x1, y1) = r["min"], r["max"]
            self.blocks.append(Block("room", i, x0, y0, x1, y1, self.rows))
        for i, d in enumerate(self.topo.get("displays") or []):
            (x0, y0), (x1, y1) = d["min"], d["max"]
            self.blocks.append(Block("display", i, x0, y0, x1, y1, self.rows))

        self.pipes = []
        for i, p in enumerate(self.topo.get("pipes") or []):
            cells = [tuple(s["pos"]) for s in p["path"]]
            dirs = [tuple(s["dir"]) for s in p["path"]]
            self.pipes.append(Pipe(i, cells, dirs))

        # attach every pipe endpoint to the block whose BORDER it points at
        for p in self.pipes:
            sb = self._block_at((p.cells[0][0] - p.dirs[0][0], p.cells[0][1] - p.dirs[0][1]))
            db = self._block_at((p.cells[-1][0] + p.dirs[-1][0], p.cells[-1][1] + p.dirs[-1][1]))
            if sb is None or db is None:
                raise SystemExit(f"pipe {p.idx}: endpoint not on a room border "
                                 f"(src {p.cells[0]} dst {p.cells[-1]}) — cannot plan")
            p.src_b, p.src_off = sb
            p.dst_b, p.dst_off = db

        covered = set()
        for b in self.blocks:
            covered |= b.cells(b.ox0, b.oy0)
        for p in self.pipes:
            covered |= set(p.cells)
        self.orphans = {(x, y): ch
                        for y, row in enumerate(self.rows)
                        for x, ch in enumerate(row)
                        if ch != " " and (x, y) not in covered}

        self.base_offsets = tuple((b.ox0, b.oy0) for b in self.blocks)
        self.border_offs = [sorted({(x - b.ox0, y - b.oy0)
                                    for (x, y) in b.border(b.ox0, b.oy0)})
                            for b in self.blocks]
        self.rooms_with_ru = {bi for bi, b in enumerate(self.blocks)
                              if b.kind == "room" and
                              any(ch in "RU" and 0 < dx < b.w - 1 and 0 < dy < b.h - 1
                                  for (dx, dy), ch in b.glyphs.items())}
        base = self.base_layout()
        self.base_resolution = self.resolution(base, self.pipe_paths_original())
        self.adjacency_ok_base = self._adjacency_clean(base, self.pipe_paths_original())

    # ---- helpers -------------------------------------------------------------
    def base_layout(self):
        return (self.base_offsets,
                tuple((p.src_off, p.dst_off) for p in self.pipes))

    def _block_at(self, pt):
        for bi, b in enumerate(self.blocks):
            x0, y0, x1, y1 = b.rect(b.ox0, b.oy0)
            if x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1:
                return bi, (pt[0] - x0, pt[1] - y0)
        return None

    def pipe_paths_original(self):
        return [(list(p.cells), list(p.dirs)) for p in self.pipes]

    def endpoint(self, offsets, bi, off):
        ox, oy = offsets[bi]
        return (ox + off[0], oy + off[1])

    def ends(self, layout, p):
        offsets, attach = layout
        so, do = attach[p.idx]
        return (self.endpoint(offsets, p.src_b, so),
                self.endpoint(offsets, p.dst_b, do))

    # ---- rendering -----------------------------------------------------------
    def draw(self, offsets, paths):
        cells = dict(self.orphans)
        for b, (ox, oy) in zip(self.blocks, offsets):
            for (dx, dy), ch in b.glyphs.items():
                cells[(ox + dx, oy + dy)] = ch
        for pi, (pcells, pdirs) in enumerate(paths):
            orig = self.pipes[pi] if pi < len(self.pipes) else None
            if orig is not None and list(pcells) == list(orig.cells):
                # an untouched pipe keeps its own glyphs: a champion may spell a straight
                # run as arrowheads rather than body, which is legal and which our
                # canonical renderer would silently rewrite (breaking the round-trip gate)
                for (cx, cy) in pcells:
                    cells[(cx, cy)] = self.rows[cy][cx]
                continue
            n = len(pcells)
            for i, (cx, cy) in enumerate(pcells):
                d = pdirs[i]
                bend = i == 0 or i == n - 1 or pdirs[i - 1] != d
                cells[(cx, cy)] = ARROW[d] if bend else ("-" if d[0] else "|")
        return cells

    # ---- occupancy -----------------------------------------------------------
    def occupancy(self, offsets):
        occ = set(self.orphans)
        for b, (ox, oy) in zip(self.blocks, offsets):
            x0, y0, x1, y1 = b.rect(ox, oy)
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    occ.add((x, y))
        return occ

    def blocks_disjoint(self, offsets):
        rects = [b.rect(ox, oy) for b, (ox, oy) in zip(self.blocks, offsets)]
        for i in range(len(rects)):
            ax0, ay0, ax1, ay1 = rects[i]
            for j in range(i + 1, len(rects)):
                bx0, by0, bx1, by1 = rects[j]
                if ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1:
                    return False
        return True

    # ---- routing -------------------------------------------------------------
    def route_all(self, layout, pipe_len="free", margin=8, order=None, retries=3,
                  tighten=False):
        """Route every net; on failure, RE-ORDER and try again (negotiated congestion,
        lite). One greedy order is not enough: plotter's 116-cell delay line takes the
        shortest lane and walls off the 60-cell one, and only pulling the loser to the
        front of the queue fixes it."""
        last = None
        for k in range(retries):
            paths, bad = self._route_pass(layout, pipe_len, margin, order, tighten)
            if paths is not None:
                return paths, None
            last = bad
            if order is None:
                order = self._default_order(layout, pipe_len)
            order = [bad] + [i for i in order if i != bad]   # loser routes first next time
        return None, last

    def _default_order(self, layout, pipe_len):
        return sorted(range(len(self.pipes)),
                      key=lambda i: (-(self.pipes[i].length if pipe_len != "free" else 0),
                                     -sum(abs(a - b) for a, b in
                                          zip(*self.ends(layout, self.pipes[i])))))

    def _route_pass(self, layout, pipe_len="free", margin=8, order=None, tighten=False):
        """Route every pipe over the free cells left by the placed blocks.

        Nets are routed longest-first (the classic ordering heuristic: a long net has the
        fewest alternatives, so it should claim its lane before the short ones fill it),
        and a failed net is retried once after the others have committed."""
        offsets = layout[0]
        occ = self.occupancy(offsets)
        bound = self.bound(offsets, margin)
        core = self.bound(offsets, 0)
        # bake the adjacency guard into routing: a cell that touches a room border is
        # only usable by the pipe that attaches THERE, so the router never has to be told
        # afterwards that a legal-looking route grazes a wall it must not.
        graze = {}
        for bi, (b, o) in enumerate(zip(self.blocks, offsets)):
            # room borders are only protected when the original program itself respects
            # the adjacency rule — but a DISPLAY border is protected unconditionally: a
            # re-routed pipe running alongside a display reads as attached to it and the
            # display STEALS the pipe's endpoint (seen on pathfinder — verify_topology
            # catches it after the fact, but the router must not keep proposing it).
            # route_guard (opt-in, e.g. smtplace): protect ALL borders for NEW routes
            # even when the original program grazes walls — the original's grazes ride
            # along inside REUSED routes (which skip this check), while a fresh route
            # grazing a different room would silently steal its r/s/q bindings, which
            # no model-level gate can see (resolution only knows endpoint attachments).
            if not (self.adjacency_ok_base or getattr(self, "route_guard", False)) \
                    and b.kind != "display":
                continue
            for c in b.border(*o):
                for d in DIRS4:
                    graze.setdefault((c[0] + d[0], c[1] + d[1]), set()).add(c)
        taken = set()
        paths = [None] * len(self.pipes)
        if order is None:
            # hardest-first: under a length floor the ORIGINAL length is what makes a net
            # hard (it has to claim room to bulge into), not how far apart its ends are.
            order = self._default_order(layout, pipe_len)
        deferred = []
        for pi in order:
            p = self.pipes[pi]
            src, dst = self.ends(layout, p)
            keep = self._reuse(p, src, dst, occ, taken, core if tighten else None)
            if keep is not None:      # nothing moved -> keep the champion's own route
                paths[pi] = keep
                taken |= set(keep[0])
                continue
            r = self._route_len(src, dst, occ, taken, p, pipe_len, bound, core,
                                graze, src, dst)
            if r is None:
                deferred.append(pi)
                continue
            paths[pi] = r
            taken |= set(r[0])
        for pi in deferred:
            p = self.pipes[pi]
            src, dst = self.ends(layout, p)
            r = self._route_len(src, dst, occ, taken, p, pipe_len, bound, core,
                                graze, src, dst)
            if r is None:
                return None, pi
            paths[pi] = r
            taken |= set(r[0])
        return paths, None

    def _reuse(self, p, src, dst, occ, taken, core=None):
        """A pipe whose two endpoints did not move keeps its ORIGINAL route.

        Re-deriving a route that already exists is pure downside: the router will happily
        find a different path of the same length whose glyphs the oracle then parses as a
        different number of pipes. Only nets that actually moved get re-routed."""
        osrc = (p.cells[0][0] - p.dirs[0][0], p.cells[0][1] - p.dirs[0][1])
        odst = (p.cells[-1][0] + p.dirs[-1][0], p.cells[-1][1] + p.dirs[-1][1])
        if tuple(src) != osrc or tuple(dst) != odst:
            return None
        for c in p.cells:
            if c in occ or c in taken:
                return None
            if core and not (core[0] <= c[0] <= core[2] and core[1] <= c[1] <= core[3]):
                return None      # this route is what pushes the box out — re-derive it
        return list(p.cells), list(p.dirs)

    def bound(self, offsets, margin):
        xs0 = min(o[0] for o in offsets) - margin
        ys0 = min(o[1] for o in offsets) - margin
        xs1 = max(o[0] + b.w - 1 for b, o in zip(self.blocks, offsets)) + margin
        ys1 = max(o[1] + b.h - 1 for b, o in zip(self.blocks, offsets)) + margin
        return (xs0, ys0, xs1, ys1)

    def _route_len(self, src, dst, occ, taken, p, pipe_len, bound, core, graze=None,
                   gsrc=None, gdst=None):
        """Route one pipe, then PAD it up to the length its capacity/latency needs.

        Pipe length is both latency and capacity, and tcp's `q` reads a pipe's depth, so
        `--pipe-len min|exact` must be able to hit a target length. A length-in-the-state
        A* can hit it but happily walks over its own cells (the state has no visited set),
        which the oracle rejects; padding a shortest, self-avoiding route with 2-cell jogs
        cannot self-intersect, and grid parity guarantees the deficit is always even."""
        ok_graze = (lambda c: (not graze or not (graze.get(c, set()) - {gsrc, gdst})))
        r = self._route_one(src, dst, occ, taken, 2, None, bound, core, ok_graze)
        if r is None or pipe_len == "free":
            return r
        cells, dirs = r
        if len(cells) == p.length or (pipe_len == "min" and len(cells) > p.length):
            return r
        if len(cells) > p.length:
            return None                      # cannot make a route shorter than shortest
        # bulge inside the blocks' own bounding box if at all possible: padding that
        # escapes the box costs max(w,h), which is squared in the score.
        for pad_box in (core, bound):
            r2 = self._pad(cells, dst, p.length, occ, taken, src, pad_box, ok_graze,
                           pipe_len)
            if r2 is not None:
                return r2
        return None

    def _pad(self, cells, dst, target, occ, taken, src, bound, ok_graze, pipe_len):
        cells = list(cells)
        need = target - len(cells)
        if need % 2:
            # every route between one attachment pair has a fixed length PARITY, so an odd
            # deficit is unreachable; `min` may overshoot by one, `exact` simply cannot.
            if pipe_len != "min":
                return None
            need += 1
        if need <= 0:
            return (cells, self._dirs(cells, dst)) if need == 0 or pipe_len == "min" else None
        blocked = occ | taken | set(cells) | {src, dst}
        lo_x, lo_y, hi_x, hi_y = bound
        while need > 0:
            grew = False
            # never bulge the first or last two edges: those cells ARE the straight run
            # the oracle measures `nearest pipe` against, and bending them silently
            # retargets every r/s/q in the room.
            for i in range(2, max(2, len(cells) - 3)):
                a, b = cells[i], cells[i + 1]
                d = (b[0] - a[0], b[1] - a[1])
                for perp in ((d[1], d[0]), (-d[1], -d[0])):
                    # how deep can this edge bulge sideways?  a t-deep bulge adds 2t
                    # cells, so one wide-open corridor can absorb a whole deficit that
                    # a fixed 1-deep jog would have to find dozens of separate slots for
                    t = 0
                    while t < need // 2:
                        pa = (a[0] + perp[0] * (t + 1), a[1] + perp[1] * (t + 1))
                        pb = (b[0] + perp[0] * (t + 1), b[1] + perp[1] * (t + 1))
                        if pa in blocked or pb in blocked:
                            break
                        if not ok_graze(pa) or not ok_graze(pb):
                            break
                        if not (lo_x <= pa[0] <= hi_x and lo_y <= pa[1] <= hi_y):
                            break
                        if not (lo_x <= pb[0] <= hi_x and lo_y <= pb[1] <= hi_y):
                            break
                        t += 1
                    if t == 0:
                        continue
                    out = [(a[0] + perp[0] * k, a[1] + perp[1] * k) for k in range(1, t + 1)]
                    back = [(b[0] + perp[0] * k, b[1] + perp[1] * k) for k in range(t, 0, -1)]
                    cells = cells[:i + 1] + out + back + cells[i + 1:]
                    blocked |= set(out) | set(back)
                    need -= 2 * t
                    grew = True
                    break
                if grew or need <= 0:
                    break
            if not grew:
                return None
        for i in range(len(cells) - 1):
            if abs(cells[i + 1][0] - cells[i][0]) + abs(cells[i + 1][1] - cells[i][1]) != 1:
                return None
        if len(set(cells)) != len(cells):
            return None
        return cells, self._dirs(cells, dst)

    @staticmethod
    def _dirs(cells, dst):
        dirs = []
        for i in range(len(cells)):
            if i < len(cells) - 1:
                dirs.append((cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1]))
            else:
                dirs.append((dst[0] - cells[i][0], dst[1] - cells[i][1]))
        return dirs

    def _route_one(self, src, dst, occ, taken, minlen, maxlen, bound, core=None,
                   ok_graze=None):
        blocked = occ | taken
        lo_x, lo_y, hi_x, hi_y = bound
        cx0, cy0, cx1, cy1 = core if core else bound
        exact = maxlen is not None
        # a length-bounded route needs the length in the A* state; a free route only has
        # to clear the >=2-cell minimum, so the counter saturates and the state space
        # stays 4x the box instead of 4x box x length.
        lcap = maxlen if maxlen is not None else minlen

        def free(c):
            return c not in blocked and c != src and c != dst and \
                lo_x <= c[0] <= hi_x and lo_y <= c[1] <= hi_y and \
                (ok_graze is None or ok_graze(c))

        def hcost(c):
            return abs(c[0] - dst[0]) + abs(c[1] - dst[1])

        # forced straight stub out of the source so cells[0]'s backward neighbour == src
        starts = []
        for d in DIRS4:
            c0 = (src[0] + d[0], src[1] + d[1])
            if free(c0):
                starts.append((c0, d))
        if not starts:
            return None
        pq = []
        best = {}
        parent = {}
        for c, d in starts:
            st = (c, d, 1)
            best[st] = 0.0
            parent[st] = None
            heapq.heappush(pq, (hcost(c), 0.0, c[0], c[1], d, 1))
        goal = None
        pops = 0
        while pq:
            pops += 1
            if pops > 300000:
                return None
            _, g, cx, cy, d, ln = heapq.heappop(pq)
            st = ((cx, cy), d, ln)
            if best.get(st, 1e18) < g - 1e-9:
                continue
            # the oracle accepts a BENT end (the arrowhead just has to point at the
            # destination border), so any cell orthogonally adjacent to dst is a goal —
            # except one we entered moving away from it, which would double the pipe back.
            if abs(cx - dst[0]) + abs(cy - dst[1]) == 1 and (cx - d[0], cy - d[1]) != dst \
                    and ln >= minlen and (not exact or ln == maxlen):
                goal = st
                break
            if maxlen is not None and ln >= maxlen:
                continue
            for nd in DIRS4:
                if nd[0] == -d[0] and nd[1] == -d[1]:
                    continue
                # the SOURCE needs a two-cell straight stub: the loader derives the
                # attachment from cells[0]'s move-direction (cells[0] - dirs[0] must be
                # the source wall), so a route that turns on its very first cell parses
                # as src-less — the pipe silently detaches (dashboard `src: -1`).
                if ln == 1 and nd != d:
                    continue
                nc = (cx + nd[0], cy + nd[1])
                if not free(nc):
                    continue
                ng = g + 1.0 + (0.0 if nd == d else BEND_COST)
                if not (cx0 <= nc[0] <= cx1 and cy0 <= nc[1] <= cy1):
                    ng += GROW_COST      # a detour outside the block box grows the score
                ns = (nc, nd, min(ln + 1, lcap))
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    parent[ns] = st
                    heapq.heappush(pq, (ng + hcost(nc), ng, nc[0], nc[1], nd, ns[2]))
        if goal is None:
            return None
        chain = []
        st = goal
        while st is not None:
            chain.append(st)
            st = parent[st]
        chain.reverse()
        cells = [c for c, _, _ in chain]
        dirs = []
        for i in range(len(cells)):
            if i < len(cells) - 1:
                dirs.append((cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1]))
            else:
                dirs.append((dst[0] - cells[i][0], dst[1] - cells[i][1]))
        if len(cells) < 2 or len(set(cells)) != len(cells):
            return None
        return cells, dirs

    # ---- the correctness cliffs ---------------------------------------------
    @staticmethod
    def _attach(cells, dirs, at_dst, whole_run):
        """The pipe cells that count as 'attached' to the room at this endpoint."""
        if at_dst:
            if not whole_run:
                return [cells[-1]]
            run = [cells[-1]]
            d = dirs[-1]
            i = len(cells) - 2
            while i >= 0 and dirs[i] == d:
                run.append(cells[i])
                i -= 1
            return run
        if not whole_run:
            return [cells[0]]
        run = [cells[0]]
        d = dirs[0]
        i = 1
        while i < len(cells) and dirs[i - 1] == d:
            run.append(cells[i])
            i += 1
        return run

    def resolution(self, layout, paths):
        """For every pipe op in every room: which pipe does it bind to?

        Computed under both readings of 'the pipe segment attached to the room', plus the
        reading-order permutation of each room's incoming pipes (that is what R/U use)."""
        offsets = layout[0]
        out = {}
        for whole in (False, True):
            attach_in = {}
            attach_out = {}
            for p, (cells, dirs) in zip(self.pipes, paths):
                attach_out.setdefault(p.src_b, []).append(
                    (p.idx, self._attach(cells, dirs, False, whole)))
                attach_in.setdefault(p.dst_b, []).append(
                    (p.idx, self._attach(cells, dirs, True, whole)))
            for bi, b in enumerate(self.blocks):
                if b.kind != "room":
                    continue
                ox, oy = offsets[bi]
                for (dx, dy), ch in b.glyphs.items():
                    if ch not in PIPE_OPS:
                        continue
                    if not (0 < dx < b.w - 1 and 0 < dy < b.h - 1):
                        continue
                    pt = (ox + dx, oy + dy)
                    pool = attach_out.get(bi, []) if ch in OUT_OPS else attach_in.get(bi, [])
                    out[(whole, bi, dx, dy)] = _nearest(pt, pool)
            # R / U pick among READY incoming pipes in reading order rather than by
            # distance, so their rooms (and only theirs) must keep the permutation.
            for bi in self.rooms_with_ru:
                pool = attach_in.get(bi, [])
                order = sorted(pool, key=lambda it: min((c[1], c[0]) for c in it[1]))
                out[(whole, "order", bi, "in")] = tuple(pid for pid, _ in order)
        return out

    def _adjacency_clean(self, layout, paths):
        """No pipe cell may touch a room border except at its own two endpoints."""
        offsets = layout[0]
        borders = {}
        for bi, (b, (ox, oy)) in enumerate(zip(self.blocks, offsets)):
            for c in b.border(ox, oy):
                borders[c] = bi
        for p, (cells, dirs) in zip(self.pipes, paths):
            src, dst = self.ends(layout, p)
            for i, c in enumerate(cells):
                for d in DIRS4:
                    n = (c[0] + d[0], c[1] + d[1])
                    if n not in borders:
                        continue
                    if i == 0 and n == src:
                        continue
                    if i == len(cells) - 1 and n == dst:
                        continue
                    return False
        return True

    # ---- cheap block-only geometry (the search's inner loop) ------------------
    def block_cost(self, layout):
        """(box, area, pipe-endpoint manhattan) with NO routing — a lower bound on the
        real box, so the expensive route+resolve pass only ever sees promising layouts."""
        offsets = layout[0]
        xs0 = min(o[0] for o in offsets)
        ys0 = min(o[1] for o in offsets)
        xs1 = max(o[0] + b.w - 1 for b, o in zip(self.blocks, offsets))
        ys1 = max(o[1] + b.h - 1 for b, o in zip(self.blocks, offsets))
        w, h = xs1 - xs0 + 1, ys1 - ys0 + 1
        span = 0
        for p in self.pipes:
            a, d = self.ends(layout, p)
            span += abs(a[0] - d[0]) + abs(a[1] - d[1])
        return (max(w, h) ** 2, w * h, span)

    # ---- one full candidate --------------------------------------------------
    def build(self, layout, pipe_len="free", guard=None, margin=8, tighten=False):
        offsets = layout[0]
        if guard is None:
            guard = self.adjacency_ok_base
        if not self.blocks_disjoint(offsets):
            return None, "blocks overlap", None
        paths, bad = self.route_all(layout, pipe_len=pipe_len, margin=margin,
                                    tighten=tighten)
        if paths is None:
            return None, f"pipe {bad} unroutable", None
        if guard and not self._adjacency_clean(layout, paths):
            return None, "pipe grazes a room wall", None
        if self.resolution(layout, paths) != self.base_resolution:
            return None, "nearest-pipe resolution changed", None
        cells = self.draw(offsets, paths)
        # a glyph collision means two things wanted the same cell
        n_expected = sum(len(b.glyphs) for b in self.blocks) + len(self.orphans) + \
            sum(len(c) for c, _ in paths)
        if len(cells) != n_expected:
            return None, "glyph collision", None
        return cells, None, paths


def verify_topology(plan, cells, layout):
    """Re-parse the finished grid with the ORACLE and demand the same topology.

    Geometry checks are done on the router's own model of a pipe; the machine's parser is
    the one that counts. Two re-routed pipes that end up running side by side can merge or
    break in the oracle's reading, and the room then has no pipe on the side an `s`/`r`
    needs — a `no-pipe` crash on tick 2, with nothing wrong in the router's picture. This
    is what caught exactly that on gradebook."""
    # trim FIRST: a route may legitimately bulge above y=0 or left of x=0, and the
    # renderer indexes a plain list, so a negative coordinate silently wraps and eats a
    # room. The graded text is the trimmed one, so the check must look at the same grid.
    dx = min(0, min(x for x, _ in cells))
    dy = min(0, min(y for _, y in cells))
    shifted = {(x - dx, y - dy): ch for (x, y), ch in cells.items()}
    rows = render(shifted).split("\n")
    w = max((len(r) for r in rows), default=0)
    topo = LIFT.analyze([r.ljust(w) for r in rows])
    if topo.get("type") == "error":
        return f"oracle rejects the grid: {topo.get('message')}"
    got_rooms = topo.get("rooms") or []
    got_disp = topo.get("displays") or []
    want_rooms = sum(1 for b in plan.blocks if b.kind == "room")
    want_disp = len(plan.blocks) - want_rooms
    if len(got_rooms) != want_rooms or len(got_disp) != want_disp:
        return (f"topology changed: {len(got_rooms)} rooms / {len(got_disp)} displays, "
                f"want {want_rooms} / {want_disp}")
    if len(topo.get("pipes") or []) != len(plan.pipes):
        return f"pipe count changed: {len(topo.get('pipes') or [])} vs {len(plan.pipes)}"
    # map every oracle room back to the block that should be there, then compare the
    # multiset of (source block -> destination block) edges
    at = {}
    for gi, r in enumerate(got_rooms):
        for bi, (b, o) in enumerate(zip(plan.blocks, layout[0])):
            oo = (o[0] - dx, o[1] - dy)
            if b.kind == "room" and tuple(r["min"]) == oo and \
                    tuple(r["max"]) == (oo[0] + b.w - 1, oo[1] + b.h - 1):
                at[gi] = bi
    if len(at) != len(got_rooms):
        return "a room moved to an unexpected rectangle"
    for gi, d in enumerate(got_disp):     # the oracle reports a display endpoint as -1
        for bi, (b, o) in enumerate(zip(plan.blocks, layout[0])):
            oo = (o[0] - dx, o[1] - dy)
            if b.kind == "display" and tuple(d["min"]) == oo and \
                    tuple(d["max"]) == (oo[0] + b.w - 1, oo[1] + b.h - 1):
                break
        else:
            return "a display moved to an unexpected rectangle"
    disp = {bi for bi, b in enumerate(plan.blocks) if b.kind == "display"}
    got = sorted((at.get(p["src"], -1), at.get(p["dst"], -1)) for p in topo["pipes"])
    want = sorted((-1 if p.src_b in disp else p.src_b,
                   -1 if p.dst_b in disp else p.dst_b) for p in plan.pipes)
    if got != want:
        return f"pipe endpoints changed: {got} vs {want}"
    return None


def _nearest(pt, pool):
    best = None
    for pid, cells in pool:
        d, key = min((abs(cx - pt[0]) + abs(cy - pt[1]), (cy, cx)) for cx, cy in cells)
        k = (d, key)
        if best is None or k < best[0]:
            best = (k, pid)
    return None if best is None else best[1]


def box_of(cells):
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    w, h = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
    return w, h, max(w, h) ** 2


# ═══════════════════════════════════════════════════════════════════ grading


class Grader:
    def __init__(self, slug, cap=None, cases=None, workdir=None):
        self.slug, self.cap, self.cases = slug, cap, cases
        self.workdir = workdir
        self.cache = {}
        self.calls = 0

    def _run(self, text):
        fd, tmp = tempfile.mkstemp(suffix=".man", dir=self.workdir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            cmd = ["node", str(GRADER), self.slug, tmp, "--failfast"]
            if self.cap:
                cmd += ["--cap", str(self.cap)]
            if self.cases:
                cmd += ["--cases", str(self.cases)]
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=3600)
            line = ""
            for ln in p.stdout.splitlines():
                ln = ln.strip()
                if ln.startswith("{"):
                    line = ln
            if not line:
                return {"error": (p.stderr or p.stdout or "no output").strip()[:200]}
            return json.loads(line)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def grade(self, text):
        if text in self.cache:
            return self.cache[text]
        self.calls += 1
        self.cache[text] = self._run(text)
        return self.cache[text]

    def grade_many(self, texts, jobs):
        todo = [t for t in texts if t not in self.cache]
        uniq = list(dict.fromkeys(todo))
        if uniq:
            self.calls += len(uniq)
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
                for t, r in zip(uniq, ex.map(self._run, uniq)):
                    self.cache[t] = r
        return [self.cache[t] for t in texts]


def passed(res):
    return (isinstance(res, dict) and "error" not in res and res.get("score") is not None
            and res.get("total") and res.get("passed") == res.get("total"))


def fmt(res):
    fp = res.get("footprint") or {}
    at = res.get("avgTicks")
    return (f"{fp.get('w')}x{fp.get('h')} box {fp.get('box')} "
            f"avgTicks {at if at is None else round(at, 2)} score {res['score']:,.0f}")


# ═══════════════════════════════════════════════════════════════════ the search


def _moves(plan, layout, rng, span, pin_attach):
    """Move set. A single-block nudge alone cannot express `slide everything below the
    input room up by five`, which is the move that actually re-folds a stacked layout —
    so the set also contains SHEARS (translate every block past a cut line), GRAVITY
    (slide one block as far as it will legally go) and, crucially, SLIDING A PIPE'S
    ATTACHMENT along its room's border: with the attachment pinned, a room can only move
    on the axis its pipes already point along, and whole floorplans are unreachable."""
    offsets, attach = layout
    n = len(plan.blocks)
    cand = list(offsets)
    at = list(attach)
    kind = rng.random()
    if not pin_attach and kind < 0.25:                 # slide one attachment
        pi = rng.randrange(len(plan.pipes))
        end = rng.randrange(2)
        b = plan.pipes[pi].src_b if end == 0 else plan.pipes[pi].dst_b
        pair = list(at[pi])
        pair[end] = rng.choice(plan.border_offs[b])
        at[pi] = tuple(pair)
    elif kind < 0.6:                                   # nudge 1-2 blocks
        for _ in range(1 if rng.random() < 0.75 else 2):
            bi = rng.randrange(n)
            if rng.random() < 0.5:
                d = (rng.randint(-span, span), 0)
            else:
                d = (0, rng.randint(-span, span))
            cand[bi] = (cand[bi][0] + d[0], cand[bi][1] + d[1])
    elif kind < 0.85:                                  # shear: everything past a cut
        axis = 0 if rng.random() < 0.5 else 1
        coords = sorted({o[axis] for o in offsets})
        cut = rng.choice(coords)
        step = rng.randint(-span, span) or 1
        for i, o in enumerate(cand):
            if o[axis] >= cut:
                cand[i] = (o[0] + step, o[1]) if axis == 0 else (o[0], o[1] + step)
    else:                                              # gravity: pack one block
        bi = rng.randrange(n)
        d = rng.choice(DIRS4)
        for _ in range(span * 3):
            nxt = list(cand)
            nxt[bi] = (cand[bi][0] + d[0], cand[bi][1] + d[1])
            if not plan.blocks_disjoint(tuple(nxt)):
                break
            cand = nxt
    return (tuple(cand), tuple(at))


def search(plan, budget, seed, pipe_len, margin, span, verbose=False, time_limit=None,
           keep=400, pin_attach=False, restarts=6):
    """Anneal over (block offsets, pipe attachments) on the REAL cost.

    Every candidate is fully realised — routed, adjacency-guarded and re-resolved — so the
    cost is the finished program's `max(w,h)`, not a proxy. An unroutable layout is not
    thrown away but charged a small penalty over its block bounding box, because the good
    floorplans are often on the far side of an unroutable ridge (tcp only reaches 39x36
    by first detaching a pipe from a wall it currently needs)."""
    rng = random.Random(seed)
    base = plan.base_layout()
    good = {}                      # layout -> (cost, cells)   VALID layouts only
    seen = {}
    fails = {}
    t0 = time.time()
    tries = 0

    def evaluate(lay):
        if lay in seen:
            return seen[lay]
        if not plan.blocks_disjoint(lay[0]):
            seen[lay] = ((10 ** 6, 0, 0), None)
            return seen[lay]
        cells, err, paths = plan.build(lay, pipe_len=pipe_len, margin=margin)
        if cells is None:
            fails[err] = fails.get(err, 0) + 1
            bbox_, barea, _ = plan.block_cost(lay)
            side = int(bbox_ ** 0.5)
            seen[lay] = (((side + 3) ** 2, barea, 0), None)
            return seen[lay]
        w, h, box = box_of(cells)
        cost = (box, w * h, sum(len(c) for c, _ in paths))
        seen[lay] = (cost, cells)
        good[lay] = (cost, cells)
        return seen[lay]

    evaluate(base)
    per = max(1, budget // restarts)
    for r in range(restarts):
        cur = base if r == 0 else (min(good, key=lambda k: good[k][0]) if good else base)
        curcost = evaluate(cur)[0]
        for i in range(per):
            if time_limit and time.time() - t0 > time_limit:
                break
            tries += 1
            temp = max(0.01, 1.0 - i / per)
            cand = _moves(plan, cur, rng, span, pin_attach)
            cost = evaluate(cand)[0]
            if cost < curcost or rng.random() < 0.15 * temp:
                cur, curcost = cand, cost
            if verbose and tries % 500 == 0:
                bb = min(good.values(), key=lambda v: v[0])[0] if good else None
                print(f"    [{tries}] best {bb}  ({len(good)} valid, "
                      f"{time.time()-t0:.0f}s)", file=sys.stderr)
        if time_limit and time.time() - t0 > time_limit:
            break
    if verbose:
        print(f"    {tries} tries, {len(good)} valid; "
              f"failures {sorted(fails.items(), key=lambda kv: -kv[1])[:5]}", file=sys.stderr)
    if not good:
        return [], "no layout survived routing"
    return sorted(good.items(), key=lambda kv: kv[1][0])[:keep], None


# ═══════════════════════════════════════════════════════════════════ CLI


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--out")
    ap.add_argument("--budget", type=int, default=3000)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--span", type=int, default=6)
    ap.add_argument("--margin", type=int, default=8)
    ap.add_argument("--top", type=int, default=12, help="how many floorplans to grade")
    ap.add_argument("--cap", type=int)
    ap.add_argument("--cases")
    ap.add_argument("--pipe-len", choices=("free", "min", "exact"), default="free")
    ap.add_argument("--plan", help="json {offsets:[[x,y]..], attach:[[[sx,sy],[dx,dy]]..]}")
    ap.add_argument("--guard", action="store_true",
                    help="force the adjacency guard on even when the original violates it "
                         "(gradebook needs this: a re-routed pipe running alongside a "
                         "sub-room reads as attached to it and steals its s/r)")
    ap.add_argument("--tighten", action="store_true",
                    help="re-derive any pipe whose route leaves the blocks' bounding box")
    ap.add_argument("--pin-attach", action="store_true",
                    help="keep every pipe attached where it is on its room border")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--time-limit", type=float)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    plan = Plan(args.man)
    if args.guard:
        plan.adjacency_ok_base = True
    print(f"{Path(args.man).name}: {len(plan.blocks)} blocks "
          f"({sum(1 for b in plan.blocks if b.kind=='room')} rooms, "
          f"{sum(1 for b in plan.blocks if b.kind=='display')} displays), "
          f"{len(plan.pipes)} pipes, {len(plan.orphans)} orphan cells")

    # ---- the round-trip gate -------------------------------------------------
    want = "\n".join(r.rstrip() for r in plan.rows).rstrip("\n") + "\n"
    got = render(plan.draw(plan.base_offsets, plan.pipe_paths_original()))
    if got != want:
        gl, wl = got.split("\n"), want.split("\n")
        for i in range(min(len(gl), len(wl))):
            if gl[i] != wl[i]:
                print(f"  ROUND-TRIP MISMATCH at line {i}:\n    want |{wl[i]}|\n"
                      f"    got  |{gl[i]}|")
                break
        raise SystemExit("plan does not reproduce the input — refusing to place")
    print("  round-trip OK — blocks + pipes + orphans reproduce the program byte-for-byte")
    print(f"  adjacency guard: {'on' if plan.adjacency_ok_base else 'OFF (original grazes walls)'}")

    if args.plan:
        spec = json.loads(Path(args.plan).read_text())
        base_off, base_at = plan.base_layout()
        offsets = tuple(tuple(o) for o in spec.get("offsets", base_off))
        attach = tuple(tuple(tuple(e) for e in pr) for pr in spec.get("attach", base_at))
        lay = (offsets, attach)
        cells, err, _ = plan.build(lay, pipe_len=args.pipe_len, margin=args.margin,
                                   tighten=args.tighten)
        if cells is None:
            raise SystemExit(f"plan rejected: {err}")
        bad = verify_topology(plan, cells, lay)
        if bad:
            raise SystemExit(f"plan rejected by the oracle: {bad}")
        w, h, box = box_of(cells)
        text = render(trimmed(cells))
        out = Path(args.out or str(Path(args.man).with_suffix("")) + "-placed.man")
        if args.dry_run:
            print(text)
            print(f"  {w}x{h} box {box}")
            return 0
        g = Grader(args.slug, args.cap, args.cases, str(REPO / "solutions"))
        res = g.grade(text)
        print(f"  plan -> {fmt(res) if passed(res) else res}")
        if passed(res):
            out.write_text(text, encoding="utf-8")
            print(f"  wrote {out}")
        return 0

    base_cells = plan.draw(plan.base_offsets, plan.pipe_paths_original())
    bw, bh, bbox = box_of(base_cells)
    print(f"  baseline footprint {bw}x{bh} box {bbox}")
    if args.dry_run:
        ranked, err = search(plan, args.budget, args.seed, args.pipe_len,
                             args.margin, args.span, args.verbose, args.time_limit,
                             pin_attach=args.pin_attach)
        if err:
            raise SystemExit(err)
        for lay, (cost, cells) in ranked[:8]:
            w, h, box = box_of(cells)
            print(f"    box {box:6d} ({w}x{h}) pipecells {cost[2]:4d}  offsets {list(lay[0])}")
        return 0

    t0 = time.time()
    ranked, err = search(plan, args.budget, args.seed, args.pipe_len, args.margin,
                         args.span, args.verbose, args.time_limit,
                         pin_attach=args.pin_attach)
    if err:
        raise SystemExit(err)
    print(f"  search: {len(ranked)} legal floorplans in {time.time()-t0:.0f}s")
    cand = [(lay, cells) for lay, (cost, cells) in ranked if box_of(cells)[2] < bbox]
    if not cand:
        print("  no floorplan beats the baseline box — nothing to grade")
        return 0
    keep = []
    for lay, cells in cand:
        bad = verify_topology(plan, cells, lay)
        if bad:
            continue
        w, h, box = box_of(cells)
        print(f"    candidate box {box} ({w}x{h}) offsets {list(lay[0])}")
        keep.append((lay, cells))
        if len(keep) >= args.top:
            break
    cand = keep
    if not cand:
        print("  every smaller floorplan was rejected by the oracle's own parser")
        return 0

    g = Grader(args.slug, args.cap, args.cases, str(REPO / "solutions"))
    texts = [render(trimmed(c)) for _, c in cand]
    results = g.grade_many(texts, args.jobs)
    base = g.grade(want)
    if not passed(base):
        raise SystemExit(f"BASELINE FAILS LOCALLY: {base}")
    print(f"  baseline: {fmt(base)}")
    best = None
    for text, res in zip(texts, results):
        tag = fmt(res) if passed(res) else f"REJECT {res.get('error') or res}"
        print(f"    {tag}")
        if passed(res) and res["score"] < base["score"]:
            if best is None or res["score"] < best[1]["score"]:
                best = (text, res)
    if best is None:
        print("  nothing improved — baseline stands")
        return 0
    out = Path(args.out or str(Path(args.man).with_suffix("")) + "-placed.man")
    out.write_text(best[0], encoding="utf-8")
    print(f"  ACCEPTED {fmt(best[1])}  ->  {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
