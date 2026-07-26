#!/usr/bin/env python3
"""dce.py — DEAD-CODE ELIMINATION on a .man grid: erase instruction cells no man can reach.

`tools/lift.py` already recovers, per little man, the set of cells he can statically reach
by following the machine's own movement rules from his `@`. Union that over every man and
any non-space cell left over *inside a room interior* is code the program can never execute.
It costs nothing to run — but it costs SPACE, and space is the score: `max(w,h)^2 x avgTicks`.
Erasing it hands free cells to the placer, and now and then it empties a whole row or column,
which shrinks the box directly. So this pass deletes, then immediately re-tries the
blank-row / blank-column trims (and, with `--fold`, `tools/fold.py`'s line merges) that the
deletion may have unlocked.

WHY THE ANALYSIS DIRECTION IS THE SAFE ONE. `Lift.walk` is an OVER-approximation: at a
branch (`X`/`d`/`a`/`x`) it fans out to all three headings because which one fires depends on
runtime registers. It therefore reaches a superset of what really executes, so a cell it
calls unreachable is genuinely unreachable. The error it can make is calling a dead cell
live, which only costs us an optimization.

The one place that argument breaks is `Y`. `walk` starts only from `@`, so cells that are
only ever reached from a fork's birth positions are invisible to it and would be deleted as
"dead". This tool therefore REFUSES to run on a program containing `Y` unless you pass
`--allow-y` and accept the grade gate as your only protection.

NEVER DELETED, regardless of reachability:
  * anything outside a room interior — walls, corners, pipes, the blank margin;
  * every cell of a pipe path, and every cell of a display (its interior is pixel data);
  * `@`, `I`, `O`, and every backtick;
  * every cell spanned by a backtick literal. Literals are read HORIZONTALLY *and*
    VERTICALLY and may overlap, so both axes are scanned and the 8-neighbourhood of every
    backtick is protected too: blanking a digit beside a literal can silently change the
    value a crossing literal reads, and nothing but the grade gate would notice.

The grade gate is the real check. A candidate is kept only if it still passes EVERY public
case and does not score worse. The input file is never modified; output is <name>-dce.man,
written only when something actually improved.

  python3 tools/dce.py <slug> <file.man>              # delete, then trim/fold what that frees
  python3 tools/dce.py <slug> <file.man> --dry-run    # census only: no grading, no output
  python3 tools/dce.py <slug> <file.man> --fold       # also run fold.py's line merges after
"""

from __future__ import annotations

import argparse
import concurrent.futures
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

import fold as FOLD    # noqa: E402  (Fabric / apply_folds — the line-merge pass)
import lift as LIFT    # noqa: E402  (the front end: rooms, pipes, per-man reachability)
import polish as PO    # noqa: E402  (bbox / blank-line census / drop / atomic_write)

# Cells that are load-bearing no matter what the walk says.
KEEP_CHARS = set("@IO`")


def load_rows(path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8").replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max((len(r) for r in rows), default=0)
    return [r.ljust(w) for r in rows]


def render(rows: list[str]) -> str:
    return "\n".join(r.rstrip() for r in rows).rstrip("\n") + "\n"


# ------------------------------------------------------------------ the analysis

class DeadSet:
    """Everything needed to decide, per cell, `may this be blanked?`."""

    def __init__(self, rows: list[str]):
        self.rows = rows
        self.h = len(rows)
        self.w = len(rows[0]) if rows else 0
        lf = LIFT.Lift(rows)
        if lf.topo.get("type") == "error":
            raise SystemExit(f"analyze failed: {lf.topo.get('message')}")
        self.lift = lf
        self.rooms = lf.topo.get("rooms") or []
        self.displays = lf.topo.get("displays") or []
        self.pipes = lf.topo.get("pipes") or []
        self.starts = lf.starts()

        # --- reachability: the union over every man of lift.walk's static cell set.
        self.reach: set[tuple[int, int]] = set()
        self.per_man: list[int] = []
        for st in self.starts:
            cells, _edges = lf.walk(st)
            self.per_man.append(len(cells))
            self.reach |= set(cells)

        self.protected = self._protect()
        self.dead = self._dead()

    def at(self, x: int, y: int) -> str:
        if 0 <= y < self.h and 0 <= x < len(self.rows[y]):
            return self.rows[y][x]
        return " "

    def in_room_interior(self, x: int, y: int) -> bool:
        for r in self.rooms:
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 < x < x1 and y0 < y < y1:
                return True
        return False

    # ---- protection -------------------------------------------------------
    def _literal_cells(self) -> set[tuple[int, int]]:
        """Every cell a backtick literal could span, on BOTH axes.

        Backticks are paired in reading order along each row and each column, and the whole
        inclusive span of a pair is protected. The 8-neighbourhood of every backtick is
        protected as well: a literal is parsed in both directions and two literals may
        overlap, so a digit merely *beside* a backtick can be a digit *of* a literal read on
        the other axis. Over-protecting costs a missed deletion; under-protecting silently
        changes a constant."""
        out: set[tuple[int, int]] = set()
        ticks = [(x, y) for y in range(self.h) for x in range(len(self.rows[y]))
                 if self.rows[y][x] == "`"]
        for (x, y) in ticks:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    out.add((x + dx, y + dy))
        for y in range(self.h):
            xs = [x for x in range(len(self.rows[y])) if self.rows[y][x] == "`"]
            for a, b in zip(xs[0::2], xs[1::2]):
                out |= {(x, y) for x in range(a, b + 1)}
        for x in range(self.w):
            ys = [y for y in range(self.h) if self.at(x, y) == "`"]
            for a, b in zip(ys[0::2], ys[1::2]):
                out |= {(x, y) for y in range(a, b + 1)}
        return out

    def _protect(self) -> set[tuple[int, int]]:
        keep: set[tuple[int, int]] = set()
        for p in self.pipes:
            for seg in p["path"]:
                keep.add(tuple(seg["pos"]))
        for d in self.displays:                       # interior is pixel data, not code
            (x0, y0), (x1, y1) = d["min"], d["max"]
            keep |= {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
        for y in range(self.h):
            for x in range(len(self.rows[y])):
                if self.rows[y][x] in KEEP_CHARS:
                    keep.add((x, y))
        keep |= self._literal_cells()
        return keep

    def _dead(self) -> list[tuple[int, int]]:
        out = []
        for y in range(self.h):
            for x in range(len(self.rows[y])):
                if self.rows[y][x] == " ":
                    continue
                if not self.in_room_interior(x, y):
                    continue                          # walls, pipes, margin: not ours
                if (x, y) in self.reach or (x, y) in self.protected:
                    continue
                out.append((x, y))
        return out

    def has_y(self) -> bool:
        return any("Y" in r for r in self.rows)


def blank(rows: list[str], cells) -> list[str]:
    grid = [list(r) for r in rows]
    for (x, y) in cells:
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
            grid[y][x] = " "
    return ["".join(r) for r in grid]


# ------------------------------------------------------------------ grading

class Grader:
    """Same contract as polish.py's: one JSON line per candidate, cached, parallel."""

    def __init__(self, slug, cap, cases, workdir):
        self.slug, self.cap, self.cases = slug, cap, cases
        self.workdir = workdir
        self.cache: dict[str, dict] = {}
        self.calls = 0

    def _run(self, text: str) -> dict:
        fd, tmp = tempfile.mkstemp(suffix=".man", dir=self.workdir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            cmd = ["node", str(GRADER), self.slug, tmp, "--failfast"]
            if self.cap:
                cmd += ["--cap", str(self.cap)]
            if self.cases:
                cmd += ["--cases", str(self.cases)]
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=7200)
            line = ""
            for ln in p.stdout.splitlines():
                ln = ln.strip()
                if ln.startswith("{"):
                    line = ln
            if not line:
                return {"error": (p.stderr or p.stdout or "no output").strip()[:200]}
            return json.loads(line)
        except Exception as exc:  # noqa: BLE001 — a broken candidate must not kill the sweep
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def grade(self, text: str) -> dict:
        if text not in self.cache:
            self.calls += 1
            self.cache[text] = self._run(text)
        return self.cache[text]

    def grade_many(self, texts: list[str], jobs: int) -> list[dict]:
        uniq = list(dict.fromkeys(t for t in texts if t not in self.cache))
        if uniq:
            self.calls += len(uniq)
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
                for t, r in zip(uniq, ex.map(self._run, uniq)):
                    self.cache[t] = r
        return [self.cache[t] for t in texts]


ok = PO.ok
fmt = PO.fmt
key = PO.key


# ------------------------------------------------------------------ passes

def dce_pass(rows, dead, g, jobs, verbose) -> tuple[list[str], list[tuple[int, int]]]:
    """Blank every dead cell we can. Try the whole batch first, then cell by cell.

    Deleting dead code is semantically a no-op, so the batch is expected to pass outright;
    the per-cell fallback exists because `unreachable` is only as good as the topology the
    lift recovered, and one bad cell must not cost us the other ninety."""
    if not dead:
        return rows, []
    whole = render(blank(rows, dead))
    res = g.grade(whole)
    base = g.grade(render(rows))
    if ok(res) and res["score"] <= base["score"]:
        print(f"   batch: all {len(dead)} dead cells blanked at once -> {fmt(res)}")
        return blank(rows, dead), list(dead)

    print(f"   batch of {len(dead)} REJECTED "
          f"({fmt(res) if ok(res) else (res.get('error') or 'fails cases')}); "
          f"falling back to one cell at a time")
    texts = [render(blank(rows, [c])) for c in dead]
    each = g.grade_many(texts, jobs)
    good = [c for c, r in zip(dead, each) if ok(r) and r["score"] <= base["score"]]
    if verbose:
        for c, r in zip(dead, each):
            if c not in good:
                print(f"      x ({c[0]},{c[1]}) '{rows[c[1]][c[0]]}': "
                      f"{r.get('error') or 'fails cases'}")
    cur, kept = rows, []
    for c in good:                                    # cumulative, each step re-graded
        cand = blank(cur, [c])
        r = g.grade(render(cand))
        if ok(r) and r["score"] <= base["score"]:
            cur, _ = cand, kept.append(c)
    print(f"   per-cell: {len(kept)}/{len(dead)} dead cells blanked")
    return cur, kept


def trim_pass(rows, g, max_waves, verbose) -> list[str]:
    """Delete blank rows/columns and margins the deletion may have exposed. Grade-gated."""
    best = g.grade(render(rows))
    cur = rows
    trimmed, top, bot, left, _ = PO.trim_margins(cur)
    if (top or bot or left) and trimmed:
        r = g.grade(render(trimmed))
        if ok(r) and key(r) <= key(best):
            print(f"   trim margins: top={top} bottom={bot} left={left} -> {fmt(r)}")
            cur, best = trimmed, r
    for wave in range(max_waves):
        cands = ([("row", i) for i, row in enumerate(cur) if PO.row_kind(row) == "blank-row"]
                 + [("col", c) for c in range(PO.width(cur))
                    if PO.col_kind(cur, c) == "blank-col"])
        if not cands:
            break
        applied = 0
        for d, i in cands:
            cand = PO.drop(cur, {i} if d == "row" else set(), set() if d == "row" else {i})
            r = g.grade(render(cand))
            if ok(r) and key(r) <= key(best):
                print(f"   + drop blank {d} {i}: {fmt(r)}")
                cur, best, applied = cand, r, applied + 1
                break                                 # indices shift: recompute the census
            if verbose:
                print(f"   x blank {d} {i}: {r.get('error') or 'no better'}")
        if not applied:
            break
    return cur


def fold_pass(rows, g, max_waves) -> list[str]:
    """fold.py's line merges, which a freshly emptied cell can newly permit."""
    cur = rows
    best = g.grade(render(cur))
    for wave in range(max_waves):
        fab = FOLD.Fabric(cur)
        cands = [(1, i) for i in fab.folds(1)] + [(0, i) for i in fab.folds(0)]
        if not cands:
            break
        progressed = False
        for axis in (1, 0):
            idxs = [i for a, i in cands if a == axis]
            if not idxs:
                continue
            for group in ([idxs] if len(idxs) > 1 else []) + [[i] for i in idxs]:
                cand = FOLD.apply_folds(cur, axis, group)
                r = g.grade(render(cand))
                tag = "row" if axis == 1 else "col"
                if ok(r) and key(r) <= key(best):
                    print(f"   + fold {tag}s {group}: {fmt(r)}")
                    cur, best, progressed = cand, r, True
                    break
        if not progressed:
            break
    return cur


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("file")
    ap.add_argument("--out", default=None, help="output path (default <name>-dce.man)")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--cap", type=int, default=None,
                    help="tick cap per candidate; default 4x the baseline's worst case")
    ap.add_argument("--cases", default=None, help="extra cases JSON for grade_json.js")
    ap.add_argument("--fold", action="store_true", help="also run fold.py's line merges")
    ap.add_argument("--max-waves", type=int, default=12)
    ap.add_argument("--allow-y", action="store_true",
                    help="run even though the program forks; the grade gate is then the only check")
    ap.add_argument("--dry-run", action="store_true", help="census only: no grading, no output")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    src = Path(args.file).resolve()
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else src.with_name(src.stem + "-dce.man")
    if out == src:
        print("refusing to overwrite the input file", file=sys.stderr)
        return 2

    rows = load_rows(src)
    t0 = time.time()
    ds = DeadSet(rows)

    w0, h0, box0 = PO.footprint(rows)
    live = sum(1 for y in range(ds.h) for x in range(len(rows[y]))
               if rows[y][x] != " " and ds.in_room_interior(x, y))
    print(f"== dce {src.name}  [{args.slug}]   {w0}x{h0} box {box0}")
    print(f"   {len(ds.rooms)} rooms, {len(ds.displays)} displays, {len(ds.pipes)} pipes, "
          f"{len(ds.starts)} men")
    print(f"   room-interior glyphs: {live};  statically reachable cells: {len(ds.reach)}")
    print(f"   DEAD (unreachable, unprotected, in a room interior): {len(ds.dead)}")
    if args.verbose or args.dry_run:
        by_char: dict[str, int] = {}
        for (x, y) in ds.dead:
            by_char[rows[y][x]] = by_char.get(rows[y][x], 0) + 1
        if by_char:
            print("   by glyph: " + " ".join(f"{c!r}x{n}" for c, n in sorted(by_char.items())))
            for (x, y) in ds.dead[:80]:
                print(f"      ({x},{y}) {rows[y][x]!r}")

    if ds.has_y():
        msg = ("program contains `Y`: lift.walk only walks from `@`, so cells reached only "
               "from a fork's birth positions look unreachable and would be wrongly deleted")
        if not args.allow_y:
            print(f"   REFUSING — {msg}. Pass --allow-y to override.")
            return 1
        print(f"   WARNING — {msg}; --allow-y given, the grade gate is the only check.")

    if args.dry_run:
        print(f"   --dry-run: nothing graded, nothing written ({time.time() - t0:.1f}s)")
        return 0
    if not ds.dead:
        print("   nothing dead; the program is already fully reachable.")
        return 0

    with tempfile.TemporaryDirectory(prefix="dce-") as workdir:
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

        cur, killed = dce_pass(rows, ds.dead, g, args.jobs, args.verbose)
        if killed:
            cur = trim_pass(cur, g, args.max_waves, args.verbose)
            if args.fold:
                cur = fold_pass(cur, g, args.max_waves)

        final = g.grade(render(cur))
        print()
        print("== report")
        print(f"   dead cells found  : {len(ds.dead)}")
        print(f"   dead cells deleted: {len(killed)}")
        print(f"   before: {fmt(base)}")
        print(f"   after : {fmt(final) if ok(final) else final}")
        print(f"   {g.calls} candidate gradings in {time.time() - t0:.1f}s")
        if not ok(final) or key(final) >= key(base):
            print("   NO IMPROVEMENT — the deletions are score-neutral; nothing written.")
            print("   (Blanking dead code frees cells for the placer but only pays once a")
            print("    row/column empties or a fold becomes legal.)")
            return 0
        PO.atomic_write(out, render(cur))
        gain = 100 * (1 - final["score"] / base["score"])
        print(f"   score {base['score']:,.0f} -> {final['score']:,.0f} ({gain:.2f}% better)")
        print(f"   wrote {out}")
        print(f"   verify: node tools/grade.js {args.slug} {out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
