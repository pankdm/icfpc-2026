#!/usr/bin/env python3
"""fold.py — the PLACER's intra-room pass: merge two adjacent grid lines into one.

`tools/polish.py` can delete a row/column that is *empty* (blank, all-`|`, all-`-`).
Every champion has already had those taken. What is left is rows that each hold two or
three glyphs in disjoint columns and are only separate because nobody ever tried to slide
them together. Folding row r+1 up into row r removes one row from the program — and one
tick from every walk that crossed it — for free.

WHEN A FOLD IS SAFE. Two adjacent lines may share one line iff, for every column:

  * they are not BOTH occupied (two glyphs cannot share a cell); and
  * a glyph of one does not land in the other's TRAVERSAL PATH. This is the rule that
    matters. A blank cell is shareable — a man's heading comes from the man, not the cell,
    so two walks may cross on a blank — but a man gliding east along row r would now step
    on the op that used to sit safely one row below him. Traversal is recovered per man
    from `lift.walk`, so it is the machine's own movement rules, not a guess.

  * every room and display the fold cuts must be crossed strictly through its INTERIOR
    (so it just gets one row shorter); folding a wall into its interior deletes the room;
  * no pipe may have cells in both lines — a vertical pipe run that loses a cell loses a
    tick of latency AND a slot of capacity, and some designs read a pipe's depth with `q`;
  * a display's interior is fixed by the assignment, so displays are never folded through.

Everything is then grade-gated exactly like `polish.py`: a fold survives only if the
program still passes EVERY public case and does not score worse. Output is a NEW file.

  python3 tools/fold.py <slug> <file.man>            # greedy fold, rows then columns
  python3 tools/fold.py <slug> <file.man> --dry-run  # just list the legal folds
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
GRADER = REPO / "tools" / "grade_json.js"
FAST_GRADER = REPO / "tools" / "grade_fast.py"

import lift as LIFT  # noqa: E402


def load_rows(path):
    text = Path(path).read_text(encoding="utf-8").replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max((len(r) for r in rows), default=0)
    return [r.ljust(w) for r in rows]


class Fabric:
    """The grid plus everything a fold has to respect: traversal, rooms, pipes."""

    def __init__(self, rows):
        self.rows = rows
        self.h = len(rows)
        self.w = len(rows[0]) if rows else 0
        lf = LIFT.Lift(rows)
        if lf.topo.get("type") == "error":
            raise SystemExit(f"analyze failed: {lf.topo.get('message')}")
        self.rooms = lf.topo.get("rooms") or []
        self.displays = lf.topo.get("displays") or []
        self.pipes = lf.topo.get("pipes") or []
        self.hor, self.ver = set(), set()
        for st in lf.starts():
            _cells, edges = lf.walk(st)
            for a, b in edges:
                (self.hor if a[1] == b[1] else self.ver).add(a)
                (self.hor if a[1] == b[1] else self.ver).add(b)
        self.occ = {(x, y) for y in range(self.h) for x in range(len(rows[y]))
                    if rows[y][x] != " "}
        # A room's two side walls occupy EVERY row it spans, so a naive "both occupied"
        # test rejects every interior fold. Folding one interior row out just makes the
        # wall one cell shorter, which is exactly what we want, so border cells carrying
        # the same glyph on both lines are exempt.
        self.border = {}
        for lo, hi, kind in self._boxes():
            (x0, y0), (x1, y1) = lo, hi
            for x in range(x0, x1 + 1):
                self.border[(x, y0)] = self.border[(x, y1)] = kind
            for y in range(y0, y1 + 1):
                self.border[(x0, y)] = self.border[(x1, y)] = kind

    # ---- per-axis views ------------------------------------------------------
    def _boxes(self):
        for r in self.rooms:
            yield r["min"], r["max"], "room"
        for d in self.displays:
            yield d["min"], d["max"], "display"

    def can_fold(self, axis, i):
        """May line i+1 be folded into line i?  axis 0 = columns, 1 = rows."""
        a, b = i, i + 1
        span = self.h if axis == 0 else self.w
        cross = self.ver if axis == 0 else self.hor   # the path a glyph would land in
        for k in range(span):
            ca = (a, k) if axis == 0 else (k, a)
            cb = (b, k) if axis == 0 else (k, b)
            oa, ob = ca in self.occ, cb in self.occ
            if oa and ob:
                if (ca in self.border and cb in self.border
                        and self.rows[ca[1]][ca[0]] == self.rows[cb[1]][cb[0]]):
                    continue
                return "both occupied"
            if oa and cb in cross:
                return "glyph lands in a walk"
            if ob and ca in cross:
                return "glyph lands in a walk"
        for lo, hi, kind in self._boxes():
            l, h = (lo[axis], hi[axis])
            if h < a or l > b:
                continue
            if kind == "display":
                return "cuts a display"
            if not (l < a and b < h):
                return "cuts a room wall"
        for p in self.pipes:
            ks = {s["pos"][axis] for s in p["path"]}
            if a in ks and b in ks:
                return "shortens a pipe"
        return None

    def folds(self, axis):
        out = []
        span = self.w if axis == 0 else self.h
        for i in range(span - 1):
            if self.can_fold(axis, i) is None:
                out.append(i)
        return out


def apply_folds(rows, axis, idxs):
    """Fold each line idx+1 into idx (idxs must be pairwise non-adjacent)."""
    grid = [list(r) for r in rows]
    if axis == 0:
        grid = [list(c) for c in zip(*grid)]           # transpose: columns become rows
    drop = set()
    for i in sorted(idxs):
        if i in drop or i + 1 in drop:
            continue
        for k in range(len(grid[i])):
            if grid[i + 1][k] != " ":
                grid[i][k] = grid[i + 1][k]
        drop.add(i + 1)
    grid = [r for j, r in enumerate(grid) if j not in drop]
    if axis == 0:
        grid = [list(c) for c in zip(*grid)]
    return ["".join(r) for r in grid]


def render(rows):
    return "\n".join(r.rstrip() for r in rows).rstrip("\n") + "\n"


class Grader:
    def __init__(self, slug, cap=None, cases=None, engine="oracle"):
        self.slug, self.cap, self.cases = slug, cap, cases
        self.engine = engine
        self.cache = {}

    def grade(self, text):
        if text in self.cache:
            return self.cache[text]
        fd, tmp = tempfile.mkstemp(suffix=".man", dir=str(REPO / "solutions"))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            if self.engine == "fast":
                # the WASM oracle OOMs on multi-million-tick programs (LLLM)
                cmd = [sys.executable, str(FAST_GRADER), self.slug, tmp]
                if self.cap:
                    cmd += ["--cap", str(self.cap)]
            else:
                cmd = ["node", str(GRADER), self.slug, tmp, "--failfast"]
                if self.cap:
                    cmd += ["--cap", str(self.cap)]
                if self.cases:
                    cmd += ["--cases", str(self.cases)]
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=7200)
            line = ""
            for ln in p.stdout.splitlines():
                if ln.strip().startswith("{"):
                    line = ln.strip()
            res = json.loads(line) if line else {"error": (p.stderr or "no output")[:200]}
        except Exception as exc:  # noqa: BLE001
            res = {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        self.cache[text] = res
        return res


def passed(res):
    return ("error" not in res and res.get("score") is not None
            and res.get("total") and res.get("passed") == res.get("total"))


def fmt(res):
    fp = res.get("footprint") or {}
    return (f"{fp.get('w')}x{fp.get('h')} box {fp.get('box')} "
            f"avgTicks {round(res.get('avgTicks') or 0, 2)} score {res['score']:,.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--out")
    ap.add_argument("--cap", type=int)
    ap.add_argument("--cases")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-waves", type=int, default=8)
    ap.add_argument("--engine", choices=("oracle", "fast"), default="oracle",
                    help="fast = tools/grade_fast.py (Rust); needed where the WASM oracle OOMs")
    args = ap.parse_args()

    rows = load_rows(args.man)
    g = Grader(args.slug, args.cap, args.cases, args.engine)
    base = None if args.dry_run else g.grade(render(rows))
    if base is not None:
        if not passed(base):
            raise SystemExit(f"BASELINE FAILS LOCALLY: {base}")
        print(f"baseline: {fmt(base)}")

    best_rows, best = rows, base
    for wave in range(args.max_waves):
        fab = Fabric(best_rows)
        cands = [(1, i) for i in fab.folds(1)] + [(0, i) for i in fab.folds(0)]
        print(f"  wave {wave}: {sum(1 for a,_ in cands if a==1)} row folds, "
              f"{sum(1 for a,_ in cands if a==0)} column folds")
        if args.dry_run:
            for axis, i in cands:
                print(f"    fold {'col' if axis==0 else 'row'} {i+1} into {i}")
            return 0
        if not cands:
            break
        progressed = False
        for axis in (1, 0):
            idxs = [i for a, i in cands if a == axis]
            if not idxs:
                continue
            # try the whole batch first; a batch that fails is re-tried one fold at a time
            for group in ([idxs] if len(idxs) > 1 else []) + [[i] for i in idxs]:
                cand = apply_folds(best_rows, axis, group)
                res = g.grade(render(cand))
                tag = "row" if axis == 1 else "col"
                if passed(res) and (best is None or res["score"] <= best["score"]):
                    print(f"    accept {tag} folds {group}: {fmt(res)}")
                    best_rows, best = cand, res
                    progressed = True
                    break
                print(f"    reject {tag} folds {group}: "
                      f"{fmt(res) if passed(res) else (res.get('error') or 'fails cases')}")
        if not progressed:
            break

    if best is None or best_rows is rows:
        print("nothing folded")
        return 0
    out = Path(args.out or str(Path(args.man).with_suffix("")) + "-folded.man")
    out.write_text(render(best_rows), encoding="utf-8")
    print(f"FOLDED {fmt(best)}  ->  {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
