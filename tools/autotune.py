#!/usr/bin/env python3
"""autotune.py — sweep the integer knobs of a solution BUILDER and keep what scores better.

Nearly every 10-20% win in this repo's history was a constant tweak in a build*.py
(`pitch 16->14`, `band=30`, `XL=4`, `relay -13->-12`), found by hand. This automates it:
perturb an integer in the builder, regenerate the .man, grade it on the reference oracle,
keep the change only if it still passes EVERY case and scores strictly lower. Search runs
as parallel waves of single-knob moves until nothing improves.

>>> Full docs — how the search works, how to make a builder tunable, and what results to
>>> expect — are in tools/AUTOTUNE.md. Read that before extending this file.

    python3 tools/autotune.py <slug> <builder.py> [-- builder args...]

    --knobs A,B,C     only tune these knobs (by display name)
    --exclude A,B     never touch these
    --scope all|assign  'all' = every int literal (default); 'assign' = only NAME = <int>
    --max-knobs N     cap how many knobs are searched
    --deltas 1,2,4    step sizes to try each direction (default 1,2)
    --target x.man    which produced file to grade (default: the one the builder writes)
    --cases f.json    extra stress cases a candidate must ALSO pass (guards generality)
    --jobs N          parallel candidate evaluations (default 4)
    --passes N        max search waves (default 4)
    --budget SEC      stop starting new candidates after this many seconds
    --timeout SEC     per-candidate wall clock (default 120)
    --tick-factor N   reject candidates slower than N x the baseline avg ticks (default 4)
    --no-screen       skip the build-only screening pass
    --no-macros       disable macro knobs (coordinated block shifts)
    --no-cache        do not read/write .autotune-cache.json
    -v/--verbose      print rejected candidates too
    --dry-run         evaluate the baseline + list the knobs, then stop

SAFETY — this can never break an existing solution:
  * the builder runs in a TEMP SANDBOX (symlinks to tools/sim/tests + a copy of
    solutions/<slug>), so a build never writes into the real tree;
  * the baseline must pass all cases up front, else we refuse to tune;
  * a candidate is accepted only if passed == total AND score < best;
  * results are written to NEW files (<base>-tuned.man, <builder>_tuned.py) — nothing
    existing is ever overwritten.

GENERALITY WARNING: box (footprint) improvements are input-independent and therefore
always real. Tick improvements are measured on PUBLIC cases only; for timing-sensitive
multi-man designs a knob can pass public and still break a private case. Pass --cases
with a stress suite (n=1, empty, negatives, max size, multi-round) for anything whose
timing you do not fully trust.
"""
import argparse
import ast
import concurrent.futures as futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINKED = ("tools", "sim", "tests", "interpreter", "scratchpad")


# ── knob discovery / patching ────────────────────────────────────────────────
class Knob:
    """One tunable integer in the builder source.

    Identity is (lineno, ordinal) — "the n-th integer literal on line L" — which survives
    patching, because a patch only ever rewrites a span inside a single line. `name` is
    just for display (the variable it is assigned to, when there is one)."""

    def __init__(self, lineno, ordinal, col, end_col, value, name=None):
        self.lineno, self.ordinal = lineno, ordinal
        self.col, self.end_col, self.value = col, end_col, value
        self.name = name or f"L{lineno}#{ordinal}"

    @property
    def key(self):
        return (self.lineno, self.ordinal)

    def __repr__(self):
        return f"{self.name}={self.value}"


def _signed_int(node):
    """(value, node_to_replace) for an int literal or a negated int literal, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value, node
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int) and not isinstance(node.operand.value, bool)):
        return -node.operand.value, node
    return None


def find_knobs(src, scope="all"):
    """scope='assign': only `NAME = <int>` (at any nesting depth).
       scope='all':    every integer literal in the file — the magic numbers that
                       actually encode geometry in this codebase."""
    tree = ast.parse(src)
    named = {}          # (lineno, col) -> variable name, for display
    spans = []          # (lineno, col, end_col, value)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            got = _signed_int(node.value)
            if got:
                named[(got[1].lineno, got[1].col_offset)] = node.targets[0].id
    for node in ast.walk(tree):
        got = _signed_int(node)
        if not got:
            continue
        value, span = got
        # a negated literal is owned by its UnaryOp; skip the bare operand
        if isinstance(node, ast.Constant) and any(
                isinstance(p, ast.UnaryOp) and p.operand is node for p in ast.walk(tree)):
            continue
        if scope == "assign" and (span.lineno, span.col_offset) not in named:
            continue
        spans.append((span.lineno, span.col_offset, span.end_col_offset, value))

    knobs, per_line = [], {}
    skip_lines = {i + 1 for i, line in enumerate(src.splitlines())
                  if "sys.path" in line or "_REPO" in line}
    for lineno, col, end_col, value in sorted(set(spans)):
        if lineno in skip_lines:
            continue
        ordinal = per_line.get(lineno, 0)
        per_line[lineno] = ordinal + 1
        knobs.append(Knob(lineno, ordinal, col, end_col, value, named.get((lineno, col))))
    return knobs


class MacroKnob:
    """A COORDINATED shift of many literals at once — "slide this whole block N columns".

    A single literal cannot express the move that usually matters. Geometry here is written
    as calls like `L.put(x, y, ch)` / `hrun(x, y, …)`, so the x (or y) coordinate of every
    such call inside one function IS a block. Shifting a block into dead space is a move
    that has repeatedly paid by hand; a per-literal search cannot reach it at all.

    `value` is a delta (always 0 at rest); applying d rewrites every span to its own value+d.
    The key embeds the current span sum, so after an accepted shift the knob is a NEW key and
    can be shifted again — otherwise `tried` would pin a block after one step."""

    def __init__(self, scope, axis, spans):
        self.scope, self.axis = scope, axis
        self.spans = spans                      # [(lineno, col, end_col, value)]
        self.value = 0
        self.name = f"{scope}.{'xy'[axis]}<{len(spans)}>"

    @property
    def key(self):
        return ("macro", self.scope, self.axis, sum(s[3] for s in self.spans))

    def __repr__(self):
        return f"{self.name}+0"


def find_macro_knobs(src, min_spans=3):
    """One macro knob per (enclosing function, axis) over calls whose first two positional
    args are int literals — i.e. the coordinate pairs that draw a block."""
    tree = ast.parse(src)
    scopes = [("module", tree)] + [(n.name, n) for n in ast.walk(tree)
                                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    out = []
    for scope_name, node in scopes:
        per_axis = {0: [], 1: []}
        for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
            pos = call.args
            if len(pos) < 2:
                continue
            got = [_signed_int(a) for a in pos[:2]]
            if not all(got):
                continue
            for axis in (0, 1):
                value, span = got[axis]
                per_axis[axis].append((span.lineno, span.col_offset, span.end_col_offset, value))
        for axis, spans in per_axis.items():
            spans = sorted(set(spans))
            if len(spans) >= min_spans:
                out.append(MacroKnob(scope_name, axis, spans))
    return out


def _replace_span(lines, lineno, col, end_col, value):
    line = lines[lineno - 1]
    text = f"({value})" if value < 0 and col > 0 and line[col - 1].isalnum() else repr(value)
    lines[lineno - 1] = line[:col] + text + line[end_col:]


def patch(src, knob, value):
    """Rewrite a knob to `value` (a delta for macro knobs), leaving everything else alone."""
    lines = src.splitlines(keepends=True)
    if isinstance(knob, MacroKnob):
        # right-to-left so earlier spans keep their offsets
        for lineno, col, end_col, old in sorted(knob.spans, reverse=True):
            _replace_span(lines, lineno, col, end_col, old + value)
    else:
        _replace_span(lines, knob.lineno, knob.col, knob.end_col, value)
    return "".join(lines)


# Every glyph a littleman program may legally contain: structural, I/O, and the whole
# instruction set. A builder's chatter ("footprint (69, 130, 16900)") contains characters
# outside this set, which is what separates a printed grid from the noise around it.
GLYPHS = set("+-|=:IO0123456789`MWbmq]*%/N&~{}<>^vVXdaxYHsSrRU@. \t")


def grid_from_text(text):
    """Pull a littleman grid out of a builder's stdout, or None.

    Takes the longest run of consecutive lines that are made only of legal glyphs and
    contains at least one room corner, so surrounding log lines are ignored."""
    best, run = [], []
    for line in (text or "").splitlines():
        if line.strip() and set(line) <= GLYPHS:
            run.append(line.rstrip())
        else:
            if len(run) > len(best):
                best = run
            run = []
    if len(run) > len(best):
        best = run
    if len(best) >= 3 and any("+" in ln for ln in best) and any("|" in ln or ":" in ln for ln in best):
        return "\n".join(best) + "\n"
    return None


# ── sandbox ──────────────────────────────────────────────────────────────────
class Sandbox:
    """A throwaway repo view: symlinked tools/sim/tests + a private copy of the solution
    dir. Builders resolve _REPO from __file__, so everything they write lands in here."""

    def __init__(self, slug, builder_rel):
        self.slug, self.builder_rel = slug, builder_rel
        self.root = tempfile.mkdtemp(prefix=f"autotune-{slug}-")
        for d in LINKED:
            src = os.path.join(REPO, d)
            if os.path.exists(src):
                os.symlink(src, os.path.join(self.root, d))
        os.makedirs(os.path.join(self.root, "solutions"), exist_ok=True)
        shutil.copytree(os.path.join(REPO, "solutions", slug),
                        os.path.join(self.root, "solutions", slug))
        self.builder = os.path.join(self.root, builder_rel)

    def snapshot(self):
        """{relpath: mtime_ns} for every .man in the sandbox. mtime (not content) is the
        write signal — the baseline build reproduces its .man byte-for-byte."""
        out = {}
        for root, _dirs, files in os.walk(os.path.join(self.root, "solutions")):
            for f in files:
                if f.endswith(".man"):
                    p = os.path.join(root, f)
                    try:
                        out[os.path.relpath(p, self.root)] = os.stat(p).st_mtime_ns
                    except OSError:
                        pass
        return out

    def build(self, source, extra_args, timeout):
        """Write a patched builder, run it, and return {relpath: bytes} of .man files it wrote."""
        before = self.snapshot()
        open(self.builder, "w", encoding="utf-8").write(source)
        try:
            r = subprocess.run([sys.executable, self.builder_rel] + extra_args,
                               cwd=self.root, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, "builder timeout"
        after = self.snapshot()
        touched = [k for k, v in after.items() if before.get(k) != v]
        if touched:
            return {k: open(os.path.join(self.root, k), "rb").read() for k in touched}, None
        # Some builders PRINT the grid rather than saving it, and some save to a temp file
        # and delete it. Those are perfectly good builders, so fall back to reading the grid
        # off stdout — in this repo that alone more than doubled the number of reachable
        # problems, so it matters more than any search heuristic.
        if r.returncode == 0:
            grid = grid_from_text(r.stdout or "")
            if grid:
                return {"<stdout>": grid.encode()}, None
        err = (r.stderr or r.stdout or "").strip().splitlines()
        return None, ("builder wrote nothing" if r.returncode == 0
                      else f"builder failed: {err[-1] if err else r.returncode}")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


# ── grading ──────────────────────────────────────────────────────────────────
def grade(slug, man_path, cases, timeout, cap=None):
    cmd = ["node", os.path.join(REPO, "tools", "grade_json.js"), slug, man_path]
    if cases:
        cmd += ["--cases", cases]
    if cap:
        cmd += ["--cap", str(int(cap))]
    cmd += ["--failfast"]
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "grade timeout"}
    line = (r.stdout or "").strip().splitlines()
    if not line:
        return {"error": (r.stderr or "oracle died").strip().splitlines()[-1:] or "oracle died"}
    try:
        return json.loads(line[-1])
    except json.JSONDecodeError:
        return {"error": "unparseable grader output"}


class GradeCache:
    """Grade each DISTINCT .man once, and remember it across runs (tl-651q).

    Most knob perturbations are inert (the grid comes out byte-identical) or collide with
    another candidate's grid, and grading is ~3x the cost of a build — so keying on grid
    content is most of the tuner's throughput. The on-disk half means a re-run, a resumed
    sweep, or a second agent never re-grades a grid that has already been graded."""

    PATH = os.path.join(REPO, ".autotune-cache.json")

    def __init__(self, slug, persist=True):
        self.slug, self.persist = slug, persist
        self._by_hash = {}
        self._lock = __import__("threading").Lock()
        self.hits = 0
        self._dirty = 0
        if persist and os.path.exists(self.PATH):
            try:
                self._by_hash = json.load(open(self.PATH)).get(slug, {})
            except (OSError, ValueError):
                self._by_hash = {}
        self.preloaded = len(self._by_hash)

    @staticmethod
    def _key(man_text):
        import hashlib
        return hashlib.sha1(man_text.encode()).hexdigest()[:16]

    def get(self, man_text, compute):
        h = self._key(man_text)
        with self._lock:
            if h in self._by_hash:
                self.hits += 1
                return self._by_hash[h]
        res = compute()
        with self._lock:
            self._by_hash[h] = res
            self._dirty += 1
            if self.persist and self._dirty >= 25:
                self._flush()
        return res

    def _flush(self):
        try:
            all_slugs = {}
            if os.path.exists(self.PATH):
                try:
                    all_slugs = json.load(open(self.PATH))
                except ValueError:
                    pass
            all_slugs[self.slug] = self._by_hash
            tmp = self.PATH + ".tmp"
            json.dump(all_slugs, open(tmp, "w"))
            os.replace(tmp, self.PATH)
            self._dirty = 0
        except OSError:
            pass

    def close(self):
        with self._lock:
            if self.persist and self._dirty:
                self._flush()


def checkpoint(slug, target, builder_rel, best_src, best_man, accepted, base, best):
    """Persist the best-so-far the MOMENT it is accepted (tl-r269).

    A crash mid-sweep otherwise discards a confirmed win and the whole run has to be
    repeated. Returns the paths written."""
    stem = os.path.splitext(os.path.basename(target))[0].removesuffix("-tuned")
    man_out = os.path.join(REPO, os.path.dirname(target), f"{stem}-tuned.man")
    src_out = os.path.join(REPO, os.path.splitext(builder_rel)[0].removesuffix("_tuned") + "_tuned.py")
    try:
        open(man_out, "w", encoding="utf-8").write(best_man.rstrip("\n") + "\n")
        open(src_out, "w", encoding="utf-8").write(best_src)
        json.dump({"slug": slug, "target": target, "builder": builder_rel,
                   "baseline_score": base.get("score"), "best_score": best.get("score"),
                   "accepted": [{"knob": n, "from": w, "to": v, "score": s}
                                for n, w, v, s in accepted]},
                  open(os.path.join(REPO, os.path.dirname(target), f"{stem}-tuned.json"), "w"), indent=1)
    except OSError as e:
        print(f"  (checkpoint failed: {e})")
    return man_out, src_out


def evaluate(slug, builder_rel, source, args, target, cases, cache=None, baseline_man=None, cap=None):
    """Build + grade one candidate in its own sandbox. Returns (result, man_text).

    Short-circuits before the (expensive) oracle call when the build fails or when the
    knob turned out to be inert — i.e. produced exactly the baseline grid."""
    sbx = Sandbox(slug, builder_rel)
    try:
        written, err = sbx.build(source, args.builder_args, args.timeout)
        if err:
            return {"error": err}, None
        rel = target if target in written else next(iter(written))
        man_text = written[rel].decode("utf-8", "replace")
        if baseline_man is not None and man_text == baseline_man:
            return {"inert": True, "target": rel}, man_text

        def run():
            tmp = os.path.join(sbx.root, "_cand.man")
            open(tmp, "w", encoding="utf-8").write(man_text)
            r = grade(slug, tmp, cases, args.timeout, cap)
            r["target"] = rel
            return r

        return (cache.get(man_text, run) if cache else run()), man_text
    finally:
        sbx.cleanup()


def build_only(slug, builder_rel, source, args):
    """Build a candidate WITHOUT grading it — ~4x cheaper than a full evaluate()."""
    sbx = Sandbox(slug, builder_rel)
    try:
        written, err = sbx.build(source, args.builder_args, args.timeout)
        if err:
            return None, err
        return next(iter(written.values())).decode("utf-8", "replace"), None
    finally:
        sbx.cleanup()


def box_of(man_text):
    rows = man_text.rstrip("\n").split("\n")
    ys = [i for i, r in enumerate(rows) if r.strip()]
    if not ys:
        return 0
    width = max(len(r) for r in rows)
    xs = [x for x in range(width) if any(len(r) > x and r[x] != " " for r in rows)]
    if not xs:
        return 0
    return max(xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1) ** 2


def screen(knobs, slug, builder_rel, source, args, baseline_man):
    """Classify every knob with BUILD-ONLY probes (+1 / -1) — no oracle at all.

    Two full sweeps showed 67-71% of candidates dying in the builder and up to 5% coming out
    inert, so most of a search's budget is spent proving the same knobs useless over and over.
    A knob is dropped only when BOTH directions break the build or leave the grid untouched;
    one working direction is enough to keep it. Costs 2 builds/knob (~0.17s each) and no
    grading, so it is a rounding error next to what it saves."""
    t0 = time.time()
    probes = [(k, d) for k in knobs for d in (1, -1)]
    verdict = {}
    with futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        jobs = {ex.submit(build_only, slug, builder_rel, patch(source, k, k.value + d), args): (k, d)
                for k, d in probes}
        for f in futures.as_completed(jobs):
            k, d = jobs[f]
            try:
                man, err = f.result()
            except Exception as e:
                man, err = None, str(e)
            state = "break" if err else ("inert" if man == baseline_man else "live")
            box = box_of(man) if state == "live" else None
            prev = verdict.get(k.name)
            # keep the best verdict across the two directions
            if prev is None or (prev[0] != "live" and state == "live"):
                verdict[k.name] = (state, box)
    live = [k for k in knobs if verdict.get(k.name, ("break",))[0] == "live"]
    base_box = box_of(baseline_man)
    shrinkers = [k for k in live if (verdict[k.name][1] or base_box) < base_box]
    counts = {s: sum(1 for v in verdict.values() if v[0] == s) for s in ("live", "inert", "break")}
    print(f"screened {len(knobs)} knobs in {time.time() - t0:.1f}s: {counts['live']} live, "
          f"{counts['inert']} inert, {counts['break']} always-break "
          f"→ searching {len(live)} ({len(shrinkers)} can shrink the box)")
    # box-shrinkers first: a smaller box is an input-independent win
    return sorted(live, key=lambda k: (k not in shrinkers, k.name))


def is_win(res, best_score):
    return (not res.get("error") and not res.get("inert")
            and res.get("score") is not None
            and res["passed"] == res["total"] and res["score"] < best_score)


def fmt(res):
    if res.get("error"):
        return str(res["error"])[:60]
    fp = res.get("footprint") or {}
    box = f"{fp.get('w')}x{fp.get('h')}={fp.get('box')}"
    if res["passed"] != res["total"]:
        return f"FAIL {res['passed']}/{res['total']}  box {box}"
    return f"{res['passed']}/{res['total']}  box {box}  ticks {res['avgTicks']:.0f}  score {res['score']:,.0f}"


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("builder")
    ap.add_argument("builder_args", nargs="*", help="args passed through to the builder")
    ap.add_argument("--knobs")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--scope", choices=("all", "assign"), default="all",
                    help="'all' = every int literal (default); 'assign' = only NAME = <int>")
    ap.add_argument("--max-knobs", type=int, default=0)
    ap.add_argument("--deltas", default="1,2")
    ap.add_argument("-v", "--verbose", action="store_true", help="print rejected candidates too")
    ap.add_argument("--target")
    ap.add_argument("--cases")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--passes", type=int, default=4)
    ap.add_argument("--budget", type=float, default=float("inf"))
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--no-screen", action="store_true",
                    help="skip the build-only screening pass (it drops inert/always-breaking knobs)")
    ap.add_argument("--no-cache", action="store_true", help="do not read/write .autotune-cache.json")
    ap.add_argument("--no-macros", action="store_true",
                    help="disable macro knobs (coordinated block shifts)")
    ap.add_argument("--tick-factor", type=float, default=4.0,
                    help="reject candidates slower than this x the baseline avg ticks (default 4)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    builder_rel = os.path.relpath(os.path.abspath(args.builder), REPO)
    source = open(os.path.join(REPO, builder_rel), encoding="utf-8").read()
    deltas = [int(d) for d in args.deltas.split(",") if d.strip()]
    t_start = time.time()

    # ── baseline ────────────────────────────────────────────────────────────
    print(f"baseline: building {builder_rel} …")
    base, base_man = evaluate(args.slug, builder_rel, source, args, args.target, args.cases)
    print(f"  {fmt(base)}   [{base.get('target', '?')}]")
    if base.get("error") or base["passed"] != base["total"] or base.get("score") is None:
        sys.exit("refusing to tune: the baseline build does not pass every case "
                 "(fix the builder, or point --target at the right .man)")
    target = base["target"]

    committed = os.path.join(REPO, target)
    if os.path.exists(committed):
        same = open(committed, encoding="utf-8").read().rstrip("\n") == base_man.rstrip("\n")
        print(f"  reproduces committed {target}: {'yes' if same else 'NO — builder is out of sync'}")

    # ── knobs ───────────────────────────────────────────────────────────────
    knobs = find_knobs(source, args.scope)
    if args.knobs:
        want = {k.strip() for k in args.knobs.split(",")}
        knobs = [k for k in knobs if k.name in want]
    if args.exclude:
        skip = {k.strip() for k in args.exclude.split(",")}
        knobs = [k for k in knobs if k.name not in skip]
    if args.max_knobs and len(knobs) > args.max_knobs:
        print(f"({len(knobs)} knobs found, tuning the first {args.max_knobs} — raise --max-knobs)")
        knobs = knobs[:args.max_knobs]
    macros = [] if args.no_macros else find_macro_knobs(source)
    shown = ", ".join(str(k) for k in knobs[:10]) + (" …" if len(knobs) > 10 else "")
    print(f"knobs ({len(knobs)}, scope={args.scope}): {shown or '(none found)'}")
    if macros:
        print(f"macro knobs ({len(macros)}): {', '.join(m.name for m in macros[:10])}"
              f"{' …' if len(macros) > 10 else ''}")
    if args.dry_run or not (knobs or macros):
        return

    if knobs and not args.no_screen:
        knobs = screen(knobs, args.slug, builder_rel, source, args, base_man)
    allowed = {k.name for k in knobs} | {m.name for m in macros}
    print()
    if not allowed:
        print("nothing left to search after screening")
        return

    # Cap candidate runs relative to the baseline: a build needing >N x the baseline ticks
    # cannot beat it on score unless its box shrank by the same factor, and letting broken
    # candidates run to the 5M default cap is what made the first version crawl.
    tick_cap = int(base["avgTicks"] * args.tick_factor) + 200 if base.get("avgTicks") else None
    if tick_cap:
        print(f"candidate tick cap: {tick_cap:,} ({args.tick_factor}x baseline avg)")

    best_src, best, best_man = source, base, base_man
    cache = GradeCache(args.slug, persist=not args.no_cache)
    if cache.preloaded:
        print(f"grade cache: {cache.preloaded} grids remembered from earlier runs")
    tried = set()      # (knob.key, value) already evaluated — never pay for it twice
    accepted = []
    out_of_budget = False

    # Steepest descent in fully-parallel waves: every single-knob perturbation of the
    # current best is independent, so one wave = one barrier (not one per knob), which is
    # where the parallelism actually comes from. Apply the single best win, then re-wave.
    for wave in range(1, args.passes + 1):
        # Re-derive from the current best: columns shift under a patch, and a macro knob's
        # key changes once its block has moved (which is what lets a block move twice).
        live = [k for k in find_knobs(best_src, args.scope) if k.name in allowed]
        if not args.no_macros:
            live += [m for m in find_macro_knobs(best_src) if m.name in allowed]
        plan = []
        for k in live:
            for d in deltas:
                for s in (1, -1):
                    v = k.value + s * d
                    if v != k.value and (k.key, v) not in tried:
                        plan.append((k, v))
        if not plan:
            print(f"wave {wave}: every knob setting already tried — converged")
            break

        print(f"wave {wave}: {len(plan)} candidates over {len(live)} knobs "
              f"(jobs={args.jobs}) …")
        stats = {"inert": 0, "buildfail": 0, "fail": 0, "ok": 0}
        results = []
        with futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            pending = {}
            for k, v in plan:
                if time.time() - t_start > args.budget:
                    out_of_budget = True
                    break
                src = patch(best_src, k, v)
                pending[ex.submit(evaluate, args.slug, builder_rel, src, args, target,
                                  args.cases, cache, best_man, tick_cap)] = (k, v, src)
            for f in futures.as_completed(pending):
                k, v, src = pending[f]
                try:
                    res, man = f.result()
                except Exception as e:                      # a broken builder, not our bug
                    res, man = {"error": f"{type(e).__name__}: {e}"}, None
                tried.add((k.key, v))
                if res.get("inert"):
                    stats["inert"] += 1
                elif res.get("error"):
                    stats["buildfail"] += 1
                elif res["passed"] != res["total"]:
                    stats["fail"] += 1
                else:
                    stats["ok"] += 1
                results.append((k, v, res, src, man))
                if args.verbose and not res.get("inert"):
                    print(f"    {k.name:>14} {k.value:>6} -> {v:<6} {fmt(res)}")

        wins = [(r["score"], k, v, r, s, m) for k, v, r, s, m in results if is_win(r, best["score"])]
        print(f"  {stats['ok']} valid, {stats['fail']} fail, {stats['inert']} inert, "
              f"{stats['buildfail']} build-error, {cache.hits} cache hits"
              f"{f' — {len(wins)} improve' if wins else ' — no improvement'}")
        if wins:
            wins.sort(key=lambda w: w[0])
            score, k, v, res, src, man = wins[0]
            print(f"  ACCEPT {k.name} {k.value} -> {v}:  {fmt(res)}")
            accepted.append((k.name, k.value, v, score))
            best_src, best, best_man = src, res, man

            # LINE SEARCH (tl-w6g1): a win means this knob is pointing somewhere good —
            # keep stepping the same way while it keeps paying, instead of restarting the
            # whole wave for each single step. "If one column helps, five might."
            step, at = v - k.value, v
            while not out_of_budget and time.time() - t_start <= args.budget:
                nxt = at + step
                live_k = next((x for x in find_knobs(best_src, args.scope) if x.key == k.key), None) \
                    if not isinstance(k, MacroKnob) else \
                    next((x for x in find_macro_knobs(best_src) if x.name == k.name), None)
                if live_k is None or (k.key, nxt) in tried:
                    break
                probe = patch(best_src, live_k, nxt if not isinstance(k, MacroKnob) else step)
                res2, man2 = evaluate(args.slug, builder_rel, probe, args, target,
                                      args.cases, cache, best_man, tick_cap)
                tried.add((k.key, nxt))
                if not is_win(res2, best["score"]):
                    break
                print(f"  ACCEPT {k.name} -> {nxt} (line search):  {fmt(res2)}")
                accepted.append((k.name, at, nxt, res2["score"]))
                best_src, best, best_man = probe, res2, man2
                at = nxt

            checkpoint(args.slug, target, builder_rel, best_src, best_man, accepted, base, best)
        if out_of_budget:
            print("budget exhausted")
            break
        if not wins:
            print("converged — no single-knob change improves the score")
            break

    # ── report / write ──────────────────────────────────────────────────────
    print()
    if not accepted:
        cache.close()
        print(f"no improvement found (baseline score {base['score']:,.0f})")
        return
    gain = base["score"] / best["score"]
    print(f"BEST {base['score']:,.0f} -> {best['score']:,.0f}  ({gain:.2f}x)")
    for name, was, now, score in accepted:
        print(f"   {name}: {was} -> {now}   (score {score:,.0f})")

    # re-tuning an already-tuned artifact stays on the same names (no _tuned_tuned chain);
    # the previous version is recoverable from git, which is where tuned artifacts belong
    stem = os.path.splitext(os.path.basename(target))[0].removesuffix("-tuned")
    man_out = os.path.join(REPO, os.path.dirname(target), f"{stem}-tuned.man")
    src_out = os.path.join(REPO, os.path.splitext(builder_rel)[0].removesuffix("_tuned") + "_tuned.py")
    resuming = os.path.abspath(src_out) == os.path.abspath(os.path.join(REPO, builder_rel))
    for path in ([] if resuming else (man_out, src_out)):
        if os.path.exists(path):
            print(f"\nrefusing to overwrite {os.path.relpath(path, REPO)} — move it aside and re-run")
            return
    open(man_out, "w", encoding="utf-8").write(best_man.rstrip("\n") + "\n")
    open(src_out, "w", encoding="utf-8").write(best_src)
    cache.close()
    print(f"\nwrote {os.path.relpath(man_out, REPO)}\n      {os.path.relpath(src_out, REPO)}")
    print(f"verify:  node tools/grade.js {args.slug} {os.path.relpath(man_out, REPO)}")


if __name__ == "__main__":
    main()
