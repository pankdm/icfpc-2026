#!/usr/bin/env python3
"""emit.py — the optimizing compiler's BACK END (emitter + legality checker).

`tools/lift.py` recovers what a program *is*: rooms, pipes, and each man's basic blocks.
This turns that back into a grid. Placement passes sit on top: they choose WHERE each block
goes, and call `emit()` to realise the choice and `legal()` to reject it cheaply before
paying for a grade.

THE ROUND-TRIP GATE (this module's reason to exist). Before any pass is allowed to MOVE a
block, the emitter must reproduce the original program byte-for-byte when handed the
ORIGINAL placement. Without that, a failed grade after re-placement is unattributable —
you cannot tell a bad placement from a bad emitter. `--roundtrip` runs exactly that check.

Model:
  * a BLOCK is a straight run of cells emitted from an anchor, one cell per step in a
    fixed heading;
  * FIXED cells are everything the placer may not invent or move: room walls, pipe glyphs,
    display borders, I/O markers, literals and any cell outside a room;
  * a placement maps block id -> (x, y, heading), and emit() writes blocks over a canvas of
    fixed cells;
  * legal() rejects a placement that writes two different glyphs to one cell, puts a man's
    cell on a wall, or spills outside its room.

Deliberately NOT handled yet (the placer must not silently violate them):
  * a literal's digits read REVERSED when walked westward, so a literal block cannot simply
    be re-headed;
  * `r`/`s`/`q` bind to the NEAREST pipe by Manhattan distance with reading-order ties, so
    moving one can retarget it at a different pipe with no error;
  * pipe length is both latency and capacity, and some designs use a pipe as a FIFO store;
  * men in one room are timing-coupled — same-tick arrivals kill both.
Each of those is a correctness cliff the grade gate would catch, but only after a wasted
build, so a placer should pre-check them.
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

OPS = set("0123456789`MWbmq]+-*%/N&|~{}XdaxYHsSrRU")
TURNS = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1), "V": (0, 1)}
HEADINGS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows) if rows else 0
    return [r.ljust(w) for r in rows]


def lift(path):
    r = subprocess.run(["python3", os.path.join(REPO, "tools", "lift.py"), path, "--json"],
                       capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(f"lift failed: {(r.stderr or r.stdout)[:300]}")


class Canvas:
    """A grid under construction, with conflict detection."""

    def __init__(self):
        self.cells = {}
        self.conflicts = []

    def put(self, x, y, ch):
        if ch == " ":
            return
        old = self.cells.get((x, y))
        if old is not None and old != ch:
            self.conflicts.append(((x, y), old, ch))
        self.cells[(x, y)] = ch

    def render(self):
        if not self.cells:
            return ""
        xs = [x for x, _ in self.cells]
        ys = [y for _, y in self.cells]
        w, h = max(xs) + 1, max(ys) + 1
        grid = [[" "] * w for _ in range(h)]
        for (x, y), ch in self.cells.items():
            grid[y][x] = ch
        return "\n".join("".join(row).rstrip() for row in grid) + "\n"


def interior_of(ir):
    interior = set()
    for r in ir["rooms"]:
        (x0, y0), (x1, y1) = r["min"], r["max"]
        for y in range(y0 + 1, y1):
            for x in range(x0 + 1, x1):
                interior.add((x, y))
    return interior


def fixed_cells(rows, blocks):
    """Everything the placer may NOT move: every non-space cell not covered by a block.

    The contract has to be exhaustive or the emitter silently drops content — the round-trip
    gate caught exactly that three ways: the `I`/`O` marker of an I/O room sits INSIDE a room
    interior and belongs to no man's walk; the tail of a backtick literal falls outside the
    basic block that starts it; and a wall cell terminating a walk was being carried into a
    block. Defining fixed as "everything not in a block" makes all three impossible."""
    covered = {tuple(c) for b in blocks for c in b["cells"]}
    fixed = {}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != " " and (x, y) not in covered:
                fixed[(x, y)] = ch
    return fixed


def blocks_of(ir):
    """Flatten every man's blocks into placeable units, each with its original anchor.

    Cells outside a room interior are dropped: a walk terminates BY stepping onto a wall, so
    the wall cell gets recorded as the last thing seen, but it is structure, not code."""
    interior = interior_of(ir)
    out = []
    for mi, man in enumerate(ir["men"]):
        for bi, blk in enumerate(man["blocks"]):
            cells = [(tuple(p), c) for p, c in blk if tuple(p) in interior]
            if not cells:
                continue
            heading = None
            if len(cells) > 1:
                (x0, y0), (x1, y1) = cells[0][0], cells[1][0]
                heading = (x1 - x0, y1 - y0)
            out.append({"id": f"m{mi}b{bi}", "man": mi, "anchor": cells[0][0],
                        "heading": heading, "glyphs": [c for _, c in cells],
                        "cells": [p for p, _ in cells]})
    return out


def emit(fixed, blocks, placement):
    """Render fixed cells plus every block at its placed anchor/heading."""
    canvas = Canvas()
    for (x, y), ch in fixed.items():
        canvas.put(x, y, ch)
    for b in blocks:
        x, y, d = placement[b["id"]]
        step = d or (1, 0)
        for i, ch in enumerate(b["glyphs"]):
            canvas.put(x + step[0] * i, y + step[1] * i, ch)
    return canvas


def legal(canvas, ir, blocks, placement):
    """Cheap pre-grade rejection: conflicts, and blocks that leave their room."""
    problems = list(canvas.conflicts)
    rooms = ir["rooms"]
    for b in blocks:
        x, y, d = placement[b["id"]]
        step = d or (1, 0)
        for i in range(len(b["glyphs"])):
            px, py = x + step[0] * i, y + step[1] * i
            inside = any(r["min"][0] < px < r["max"][0] and r["min"][1] < py < r["max"][1]
                         for r in rooms)
            if not inside:
                problems.append(((px, py), "outside-room", b["id"]))
                break
    return problems


def original_placement(blocks):
    return {b["id"]: (b["anchor"][0], b["anchor"][1], b["heading"]) for b in blocks}


def roundtrip(path):
    """Emit the lifted IR at its ORIGINAL placement and demand a byte-identical program."""
    rows = load_rows(path)
    ir = lift(path)
    blocks = blocks_of(ir)
    fixed = fixed_cells(rows, blocks)
    placement = original_placement(blocks)
    canvas = emit(fixed, blocks, placement)
    problems = legal(canvas, ir, blocks, placement)
    got = canvas.render()
    want = "\n".join(r.rstrip() for r in rows).rstrip("\n") + "\n"
    ok = got == want
    print(f"{os.path.basename(path)}: {len(ir['rooms'])} rooms, {len(ir['men'])} men, "
          f"{len(blocks)} blocks, {len(fixed)} fixed cells")
    if problems:
        print(f"  legality complaints at original placement: {len(problems)} "
              f"(first: {problems[0]})")
    if ok:
        print("  ROUND-TRIP OK — emitter reproduces the program byte-for-byte")
        return True
    gl, wl = got.split("\n"), want.split("\n")
    print(f"  ROUND-TRIP MISMATCH: {len(gl)} lines emitted vs {len(wl)} expected")
    for i in range(min(len(gl), len(wl))):
        if gl[i] != wl[i]:
            print(f"    first differing line {i}:\n      want |{wl[i]}|\n      got  |{gl[i]}|")
            for j, (a, b) in enumerate(zip(wl[i], gl[i])):
                if a != b:
                    print(f"      first differing column {j}: want {a!r} got {b!r}")
                    break
            break
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("man", nargs="+")
    ap.add_argument("--roundtrip", action="store_true")
    args = ap.parse_args()
    failed = 0
    for path in args.man:
        if not roundtrip(path):
            failed += 1
    if failed:
        sys.exit(f"\n{failed}/{len(args.man)} programs did not round-trip — "
                 f"the emitter is not yet safe to place with")
    print(f"\nall {len(args.man)} programs round-trip")


if __name__ == "__main__":
    main()
