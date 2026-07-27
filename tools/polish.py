#!/usr/bin/env python3
"""polish.py — grade-gated geometry polisher that edits a .man grid DIRECTLY.

Most of our tuning goes through the builder (`tools/autotune.py`), but several live
solutions are hand-written grids whose builder is missing or broken (tcp-sweep2,
manual-11x11, the LLLM/tcp champions). Nothing could touch those. This tool works on
the grid itself: it deletes rows/columns that look mechanically redundant, grades every
candidate with the real oracle, and keeps a deletion only when the program still passes
EVERY public case AND scores strictly lower.

Transforms (all greedy, all grade-gated):
  * blank      — delete a fully blank interior row / column
  * pipe-row   — delete a row whose only non-space content is '|'   (shrinks rooms in h)
  * dash-col   — delete a column whose only non-space content is '-' (shrinks rooms in w)
  * trim       — drop leading/trailing blank margins (free: footprint ignores them)

Re-flow: score = max(w,h)^2 * avgTicks, so only the BINDING dimension can shrink the box.
Candidates in the binding dimension are therefore screened first, and `--box-only` skips
the other dimension entirely (use it when you only care about the box, not about ticks —
a deletion in the non-binding dimension can still pay off by shortening walks, which is
why it is not skipped by default).

Search shape: per wave every single-deletion candidate is graded in parallel; the ones
that improve are then re-applied cumulatively (each application re-graded, so accepting a
batch is never unverified). Waves repeat until one finds nothing.

The input file is NEVER modified. Output goes to <name>-polished.man, written only if
something actually improved, and written atomically (tmp + rename) after every accepted
step, so an interrupt can never leave a half-written or unverified grid behind.

Usage:
  python3 tools/polish.py <slug> <file.man> [--jobs N] [--cap N] [--cases f.json]
                          [--out path] [--box-only] [--max-waves N] [--dry-run] [-v]
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
GRADER = REPO / "tools" / "grade_json.js"
FAST_GRADER = REPO / "tools" / "grade_fast.py"


# ---------------------------------------------------------------- grid helpers

def read_grid(path: Path) -> tuple[list[str], bool]:
    text = path.read_text(encoding="utf-8").replace("\r", "")
    trailing_nl = text.endswith("\n")
    rows = text.split("\n")
    if trailing_nl:
        rows.pop()
    return rows, trailing_nl


def render(rows: list[str], trailing_nl: bool) -> str:
    return "\n".join(rows) + ("\n" if trailing_nl else "")


def width(rows: list[str]) -> int:
    return max((len(r) for r in rows), default=0)


def col_chars(rows: list[str], c: int) -> list[str]:
    return [(r[c] if c < len(r) else " ") for r in rows]


def bbox(rows: list[str]) -> tuple[int, int, int, int] | None:
    """(y0, y1, x0, x1) of the non-space bounding box, or None for an empty grid."""
    y0 = x0 = 10**9
    y1 = x1 = -1
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != " ":
                y0 = min(y0, y)
                y1 = max(y1, y)
                x0 = min(x0, x)
                x1 = max(x1, x)
    if y1 < 0:
        return None
    return y0, y1, x0, x1


def footprint(rows: list[str]) -> tuple[int, int, int]:
    b = bbox(rows)
    if b is None:
        return 0, 0, 0
    y0, y1, x0, x1 = b
    w, h = x1 - x0 + 1, y1 - y0 + 1
    return w, h, max(w, h) ** 2


def trim_margins(rows: list[str]) -> tuple[list[str], int, int, int, int]:
    """Drop blank rows/cols outside the content bbox. Score-neutral by construction."""
    b = bbox(rows)
    if b is None:
        return rows, 0, 0, 0, 0
    y0, y1, x0, x1 = b
    kept = [r[x0:] for r in rows[y0 : y1 + 1]]
    kept = [r.rstrip() for r in kept]
    return kept, y0, len(rows) - 1 - y1, x0, 0


def drop(rows: list[str], dead_rows: set[int], dead_cols: set[int]) -> list[str]:
    out = []
    for i, row in enumerate(rows):
        if i in dead_rows:
            continue
        out.append("".join(ch for c, ch in enumerate(row) if c not in dead_cols) if dead_cols else row)
    return out


# ---------------------------------------------------------------- candidates

def row_kind(row: str) -> str | None:
    chars = set(row) - {" "}
    if not chars:
        return "blank-row"
    if chars == {"|"}:
        return "pipe-row"
    return None


def col_kind(rows: list[str], c: int) -> str | None:
    chars = [ch for ch in col_chars(rows, c) if ch != " "]
    if not chars:
        return "blank-col"
    if set(chars) == {"-"}:
        return "dash-col"
    return None


def candidates(rows: list[str], box_only: bool) -> list[tuple[str, int, str]]:
    """(dim, index, kind) sorted so the box-binding dimension is screened first."""
    w, h, _ = footprint(rows)
    row_cands = [("row", i, k) for i, r in enumerate(rows) if (k := row_kind(r))]
    col_cands = [("col", c, k) for c in range(width(rows)) if (k := col_kind(rows, c))]
    # Only the binding dimension can shrink max(w,h); screen it first. When the box is
    # square both dimensions bind (one deletion each), so neither is demoted.
    first, second = (row_cands, col_cands) if h >= w else (col_cands, row_cands)
    if box_only and h != w:
        second = []
    return first + second


# ---------------------------------------------------------------- grading

class Grader:
    def __init__(self, slug, cap, cases, workdir, verbose=False, engine="oracle"):
        self.slug, self.cap, self.cases = slug, cap, cases
        self.workdir = workdir
        self.verbose = verbose
        self.engine = engine
        self.cache: dict[str, dict] = {}
        self.calls = 0

    def _run(self, text: str) -> dict:
        fd, tmp = tempfile.mkstemp(suffix=".man", dir=self.workdir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            if self.engine == "fast":
                # The WASM oracle OOMs ("Go program has already exited") on
                # multi-million-tick programs such as LLLM, so those can only be
                # polished with the Rust engine.  Same JSON envelope.
                cmd = [sys.executable, str(FAST_GRADER), self.slug, tmp]
                if self.cap:
                    cmd += ["--cap", str(self.cap)]
                p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
                line = ""
                for ln in p.stdout.splitlines():
                    ln = ln.strip()
                    if ln.startswith("{"):
                        line = ln
                if not line:
                    return {"error": (p.stderr or p.stdout or "no output").strip()[:200]}
                return json.loads(line)
            cmd = ["node", str(GRADER), self.slug, tmp, "--failfast"]
            if self.cap:
                cmd += ["--cap", str(self.cap)]
            if self.cases:
                cmd += ["--cases", str(self.cases)]
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
            line = ""
            for ln in p.stdout.splitlines():
                ln = ln.strip()
                if ln.startswith("{"):
                    line = ln
            if not line:
                return {"error": (p.stderr or p.stdout or "no output").strip()[:200]}
            return json.loads(line)
        except Exception as exc:  # noqa: BLE001 - a broken candidate must not kill the sweep
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def grade(self, text: str) -> dict:
        if text in self.cache:
            return self.cache[text]
        self.calls += 1
        r = self._run(text)
        self.cache[text] = r
        return r

    def grade_many(self, texts: list[str], jobs: int) -> list[dict]:
        todo = [t for t in texts if t not in self.cache]
        uniq = list(dict.fromkeys(todo))
        if uniq:
            self.calls += len(uniq)
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
                for t, r in zip(uniq, ex.map(self._run, uniq)):
                    self.cache[t] = r
        return [self.cache[t] for t in texts]


def ok(res: dict) -> bool:
    return (
        isinstance(res, dict)
        and "error" not in res
        and res.get("score") is not None
        and res.get("total")
        and res.get("passed") == res.get("total")
    )


def key(res: dict) -> tuple[float, int]:
    """Ranking key: lower score wins; on a tie the smaller bbox area wins.

    The tiebreak is the RE-FLOW rule. On a square box no single deletion can shrink
    max(w,h), so pure steepest descent stalls at e.g. 10x10 even when 9x9 is reachable by
    deleting one row AND one column. A score-neutral deletion that shrinks the OTHER
    dimension is free (footprint is squared on the max), and it is what makes the next
    deletion in the binding dimension pay. Such lateral moves strictly shrink the area, so
    the search still terminates, and they can never make the score worse.
    """
    fp = res.get("footprint") or {}
    return (res["score"], (fp.get("w") or 0) * (fp.get("h") or 0))


def fmt(res: dict) -> str:
    fp = res.get("footprint") or {}
    at = res.get("avgTicks")
    return (
        f"{fp.get('w')}x{fp.get('h')} box {fp.get('box')} "
        f"avgTicks {at if at is None else round(at, 2)} score {res['score']:,.0f}"
    )


# ---------------------------------------------------------------- safety gate

def rebinds(original_path: Path, candidate_text: str) -> bool:
    """Would this candidate silently retarget a pipe operation?

    `s`/`r`/`q` bind to the NEAREST pipe by Manhattan distance with reading-order ties, so
    deleting a row or column between an op and its pipe can rebind it to a DIFFERENT pipe.
    Nothing errors: the program loads, runs, and quietly computes the wrong thing. If the
    public cases do not exercise that path it grades PASS and only fails on the private
    cases, where it costs the entire problem. So a grade is not sufficient evidence here."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".man")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(candidate_text)
        out = subprocess.run(["python3", str(REPO / "tools" / "pipecheck.py"),
                              str(original_path), tmp],
                             capture_output=True, text=True, cwd=str(REPO), timeout=300)
        return "REBOUND" in out.stdout
    except (OSError, subprocess.SubprocessError):
        return False          # checker unavailable: fall back to the grade gate alone
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------- output

def _umask() -> int:
    u = os.umask(0)
    os.umask(u)
    return u


def atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o644 & ~_umask())  # mkstemp gives 0600; .man files are normal files
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("file")
    ap.add_argument("--jobs", type=int, default=8, help="parallel gradings (default 8)")
    ap.add_argument("--cap", type=int, default=None,
                    help="tick cap per case; default 4x the baseline's worst case, 0 = oracle default")
    ap.add_argument("--cases", default=None, help="extra cases JSON, passed to grade_json.js")
    ap.add_argument("--out", default=None, help="output path (default <name>-polished.man)")
    ap.add_argument("--box-only", action="store_true",
                    help="only try deletions in the dimension that binds max(w,h)")
    ap.add_argument("--max-waves", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true", help="never write the output file")
    ap.add_argument("--engine", choices=("oracle", "fast"), default="oracle",
                    help="fast = tools/grade_fast.py (Rust); required for programs "
                         "the WASM oracle OOMs on, e.g. LLLM")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    src = Path(args.file).resolve()
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else src.with_name(src.stem + "-polished.man")
    if out == src:
        print("refusing to overwrite the input file", file=sys.stderr)
        return 2

    rows, trailing_nl = read_grid(src)
    t0 = time.time()

    with tempfile.TemporaryDirectory(prefix="polish-") as workdir:
        # --- baseline (uncapped, so the cap we derive is honest)
        base_g = Grader(args.slug, args.cap if args.engine == "fast" else None,
                        args.cases, workdir, args.verbose, args.engine)
        base = base_g.grade(render(rows, trailing_nl))
        if not ok(base):
            print(f"BASELINE DOES NOT PASS: {json.dumps(base)[:300]}")
            return 1
        worst = max((r.get("settleTick") or 0) for r in base.get("results", [])) or 0
        cap = args.cap if args.cap is not None else max(1000, worst * 4)
        if cap == 0:
            cap = None
        g = Grader(args.slug, cap, args.cases, workdir, args.verbose, args.engine)
        g.cache[render(rows, trailing_nl)] = base

        w0, h0, _ = footprint(rows)
        print(f"== polish {src.name}  [{args.slug}]")
        print(f"   baseline: {fmt(base)}  ({base['passed']}/{base['total']} public)")
        print(f"   tick cap for candidates: {cap}   jobs {args.jobs}")

        # --- trim margins (free; verified, must not make the score worse)
        removed: list[str] = []
        trimmed, top, bot, left, _ = trim_margins(rows)
        if (top or bot or left) and trimmed:
            r = g.grade(render(trimmed, trailing_nl))
            if ok(r) and r["score"] <= base["score"]:
                rows = trimmed
                if top or bot:
                    removed.append(f"trim {top} top / {bot} bottom blank line(s)")
                if left:
                    removed.append(f"trim {left} left blank column(s)")
                print(f"   trim margins: top={top} bottom={bot} left={left} -> {fmt(r)}")
            elif args.verbose:
                print(f"   trim margins rejected: {json.dumps(r)[:160]}")

        census: dict[str, int] = {}
        for _d, _i, k in candidates(rows, False):
            census[k] = census.get(k, 0) + 1
        print("   candidates: " + (", ".join(f"{v} {k}" for k, v in sorted(census.items()))
                                   if census else "none (no blank/'|'-only rows, no blank/'-'-only columns)"))

        best = g.grade(render(rows, trailing_nl))
        if not ok(best):
            print("   post-trim grid does not pass; abandoning trim")
            rows, _ = read_grid(src)
            best = base
        start_score = base["score"]
        wrote = False

        # --- greedy waves
        for wave in range(1, args.max_waves + 1):
            cands = candidates(rows, args.box_only)
            if not cands:
                if args.verbose:
                    print(f"   wave {wave}: no candidates")
                break
            w, h, _ = footprint(rows)
            binder = "height" if h > w else ("width" if w > h else "square (both)")
            texts = [render(drop(rows, {i} if d == "row" else set(), set() if d == "row" else {i}), trailing_nl)
                     for d, i, _k in cands]
            print(f"   wave {wave}: {len(cands)} candidate(s), box {w}x{h} bound by {binder}, "
                  f"score {best['score']:,.0f}")
            res = g.grade_many(texts, args.jobs)

            scored = []
            for (d, i, k), r in zip(cands, res):
                if ok(r) and key(r) < key(best):
                    scored.append((key(r), d, i, k))
                elif args.verbose:
                    why = "error" if "error" in r else ("fail" if not ok(r) else f"score {r['score']:,.0f}")
                    print(f"      - {k} {d} {i}: {why}")
            scored.sort()
            if not scored:
                print(f"   wave {wave}: no improving deletion")
                break

            # Re-apply cumulatively; every accepted step is graded again, so a batch is
            # never taken on faith (two individually-good deletions can interact).
            dead_rows: set[int] = set()
            dead_cols: set[int] = set()
            applied = 0
            for _k, d, i, kind in scored:
                dr = dead_rows | ({i} if d == "row" else set())
                dc = dead_cols | (set() if d == "row" else {i})
                cand = drop(rows, dr, dc)
                r = g.grade(render(cand, trailing_nl))
                if ok(r) and key(r) < key(best) and rebinds(src, render(cand, trailing_nl)):
                    print(f"      x {kind} {d} {i}: REJECTED — silently rebinds a pipe op")
                    continue
                if ok(r) and key(r) < key(best):
                    gain = "" if r["score"] < best["score"] else "  [free re-flow, score unchanged]"
                    dead_rows, dead_cols = dr, dc
                    best = r
                    applied += 1
                    removed.append(f"{kind} {d} {i} (of the wave-{wave} grid) -> {fmt(r)}{gain}")
                    print(f"      + drop {kind} {d} {i}: {fmt(r)}{gain}")
                    # Only publish a grid that actually beats the input's score.
                    if not args.dry_run and r["score"] < start_score:
                        atomic_write(out, render(cand, trailing_nl))
                        wrote = True
                elif args.verbose:
                    print(f"      x {kind} {d} {i}: rejected on re-apply")
            if not applied:
                break
            rows = drop(rows, dead_rows, dead_cols)

        # --- report
        print()
        print("== report")
        if best["score"] >= start_score:
            print(f"   NOTHING IMPROVED. {src.name} is already tight under these transforms.")
            print(f"   baseline {fmt(base)}")
            print(f"   {g.calls} candidate gradings in {time.time() - t0:.1f}s")
            if wrote:  # cannot happen, but never leave a stale file behind
                out.unlink(missing_ok=True)
            return 0
        for line in removed:
            print(f"   - {line}")
        print(f"   before: {fmt(base)}")
        print(f"   after : {fmt(best)}")
        print(f"   score {start_score:,.0f} -> {best['score']:,.0f} "
              f"({100 * (1 - best['score'] / start_score):.2f}% better)")
        print(f"   {g.calls} candidate gradings in {time.time() - t0:.1f}s")
        if args.dry_run:
            print("   --dry-run: nothing written")
        elif wrote:
            print(f"   wrote {out}")
            print(f"   verify: node tools/grade.js {args.slug} {out}")
            if any(("pipe-row" in line or "dash-col" in line) for line in removed):
                print("   ⚠ pipe-row/dash-col deletions SHRINK ROOMS. Only the PUBLIC cases gated"
                      " this; a private case with more men or a longer tape could now overflow."
                      " Re-run with --cases <stress.json> before submitting.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
