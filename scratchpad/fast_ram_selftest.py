#!/usr/bin/env python3
"""Self-test for tools/fast_ram.py.

Stamps the RAM component plus the minimal driver the Memory problem needs (an ``I``
room feeding the command pipe and an ``O`` room fed by the reply pipe -- the Memory
input stream IS the component's wire protocol, ``[0,addr]`` / ``[1,addr,value]``),
writes ``solutions/memory/fast-ram-<size>.man`` and grades it:

    1. python3 tools/grade_fast.py memory <file>     (Rust pre-filter)
    2. node tools/grade.js memory <file>             (wasm oracle, the real judge)
    3. marginal cost = (ticks["interleaved cells"] - ticks["overwrite"]) / (125 - 5)
    4. a generality stress suite (private cases exist: the champion is 24/24 on the
       server against 7 public), and a build sweep over every downstream size.

    python3 scratchpad/fast_ram_selftest.py [size] [banks] [k]
    python3 scratchpad/fast_ram_selftest.py --sweep      # build every target size
"""
import json
import os
import random
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm            # noqa: E402
import fast_ram                   # noqa: E402
from layout import Layout         # noqa: E402

LM_CANDIDATES = (
    os.path.join(REPO, "interp", "target", "release", "lm"),
    "/Users/dmitrykorolev/projects/icfpc-2026-pfbits/interp/target/release/lm",
)


def lm_bin():
    for cand in LM_CANDIDATES:
        if os.path.exists(cand):
            return cand
    raise SystemExit("no Rust interpreter found; build interp/ with cargo")


def build_memory_solution(size=100, banks=None, k=None):
    """RAM + I/O rooms + the two pipes = a complete Memory solution."""
    program = lm.Program()
    ports = fast_ram.build(program, 0, 0, size=size, banks=banks, k=k)
    lay = Layout(program)

    # command: the caller owns the pipe. Two westward cells out of an I room.
    cx, cy = ports["command"]
    lay.put(cx, cy, "<")
    lay.put(cx + 1, cy, "<")
    program.input_room(cx + 2, cy - 1)

    # reply: the component's pipe starts on ``reply`` flowing east into an O room.
    rx, ry = ports["reply"]
    lay.put(rx, ry, ">")
    lay.put(*ports["reply_turn"], ">")
    program.output_room(ports["reply_turn"][0] + 1, ry - 1)
    return program, ports


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, **kw)


def run_case(path, tokens_in, tokens_out, cap=200000):
    """One (input, expected) pair through the Rust engine. -> (ok, settleTick, raw).

    ``--cap`` is essential: a deadlocked machine emits nothing and would otherwise
    spin to the default cap for minutes per case.
    """
    try:
        out = run([lm_bin(), "--grade", path, f"--cap={cap}",
                   "--input=" + " ".join(map(str, tokens_in)),
                   "--expected=" + " ".join(map(str, tokens_out))], timeout=120)
    except subprocess.TimeoutExpired:
        return False, None, "TIMEOUT (>120s wall)"
    raw = (out.stdout + out.stderr).strip()
    try:
        js = json.loads(raw)
    except json.JSONDecodeError:
        return False, None, raw
    return js.get("status") == "pass", js.get("settleTick"), raw


# ──────────────────────────────────────────────────────────────────────────────
# reference model + stress-case generation
# ──────────────────────────────────────────────────────────────────────────────
def reference(tokens, cells=100):
    """The Memory problem's semantics, used to label every generated stress case."""
    mem = [0] * cells
    out, i = [], 0
    while i < len(tokens):
        if tokens[i] == 0:
            out.append(mem[tokens[i + 1]])
            i += 2
        else:
            mem[tokens[i + 1]] = tokens[i + 2]
            i += 3
    return out


def stress_cases(cells=100, seed=20260726):
    """Shape-of-input stress, not value stress -- private cases probe generality."""
    rnd = random.Random(seed)
    hi = cells - 1
    cases = []

    def add(name, toks):
        # A stream with NO read produces no output, and a program that never outputs
        # never "settles" -- lm --grade would then run to the tick cap and appear to
        # hang. That is a harness artefact, not a component property, so every
        # write-only shape gets one trailing read appended: it keeps the shape AND
        # checks the final state actually landed.
        expect = reference(toks, cells)
        if not expect:
            toks = list(toks) + [0, 0]
            expect = reference(toks, cells)
        cases.append((name, toks, expect))

    # --- degenerate / minimum -------------------------------------------------
    add("minimum stream (2 tokens)", [0, 0])
    add("single write, no read", [1, 0, 5])
    add("read the top address only", [0, hi])

    # --- boundary values ------------------------------------------------------
    add("extreme values", [1, 0, -1000000, 1, hi, 1000000, 0, 0, 0, hi])
    add("zero written over nonzero", [1, 7, 123, 1, 7, 0, 0, 7])
    add("every value boundary", sum(([1, i % cells, v] for i, v in enumerate(
        (-1000000, -999999, -1, 0, 1, 999999, 1000000))), [])
        + sum(([0, i % cells] for i in range(7)), []))

    # --- address coverage -----------------------------------------------------
    add("write then read all cells",
        sum(([1, a, a * 7 - 300] for a in range(cells)), [])
        + sum(([0, a] for a in range(cells)), []))
    add("read every cell fresh", sum(([0, a] for a in range(cells)), []))

    # --- same-address hazards (the write-commit window is 7 ticks) ------------
    add("same-address hammer read", [0, 0] * 100)
    add("same-address hammer top", [0, hi] * 100)
    add("write-read alternating same cell",
        sum(([1, 42 % cells, i, 0, 42 % cells] for i in range(60)), []))
    add("write twice then read", sum(([1, 3, i, 1, 3, i + 1, 0, 3] for i in range(40)), []))

    # --- reply-ordering hazards (4-tick decode skew vs 8-tick cadence) -------
    add("descending addresses by 1", sum(([0, a] for a in range(hi, -1, -1)), []))
    add("descending addresses by 2", sum(([0, a] for a in range(hi, -1, -2)), []))
    add("ascending addresses by 2", sum(([0, a] for a in range(0, cells, 2)), []))
    add("same offset across banks",
        sum(([0, a] for a in range(0, cells, max(1, cells // 8))), []) * 8)

    # --- op-mix / trailing shapes --------------------------------------------
    add("all writes, no read", sum(([1, a % cells, a] for a in range(120)), []))
    add("reads then writes", sum(([0, a % cells] for a in range(60)), [])
        + sum(([1, a % cells, a] for a in range(60)), []))
    add("many trailing writes", [1, 5, 9, 0, 5] + sum(([1, a % cells, a] for a in range(80)), []))

    # --- maximum-size random streams (spec caps the stream at 1000 tokens) ---
    for trial in range(4):
        toks = []
        while len(toks) < 995:
            if rnd.random() < 0.5:
                toks += [0, rnd.randrange(cells)]
            else:
                toks += [1, rnd.randrange(cells), rnd.randint(-1000000, 1000000)]
        add(f"max-size random stream #{trial}", toks)

    # a max-size stream that is ALL reads (the densest possible reply traffic)
    add("max-size all reads", sum(([0, rnd.randrange(cells)] for _ in range(500)), []))
    return cases


# ──────────────────────────────────────────────────────────────────────────────
# the three reported measurements
# ──────────────────────────────────────────────────────────────────────────────
def marginal_ticks(path):
    """(interleaved - overwrite) / (125 - 5): exactly how the champion was measured."""
    spec = json.load(open(os.path.join(REPO, "tests", "memory.json")))
    cases = {c["name"]: c for c in spec["publicTestData"]}
    ticks = {}
    for name in ("overwrite", "interleaved cells"):
        c = cases[name]
        ok, tick, raw = run_case(path, c["in"], c["out"])
        ticks[name] = (ok, tick, raw)
    return ticks


def op_count(tokens):
    n, i = 0, 0
    while i < len(tokens):
        i += 2 if tokens[i] == 0 else 3
        n += 1
    return n


def tick_law(path, cells=100):
    """Fit settleTick = startup + slope*ops over a range of pure-read streams."""
    points = []
    for n in (1, 2, 4, 8, 16, 32, 64, 128, 256):
        toks = sum(([0, i % cells] for i in range(n)), [])
        ok, tick, _ = run_case(path, toks, reference(toks, cells))
        if not ok:
            return None, points
        points.append((n, tick))
    (n0, t0), (n1, t1) = points[0], points[-1]
    slope = (t1 - t0) / (n1 - n0)
    return (slope, t0 - slope * n0), points


DOWNSTREAM_SIZES = (30, 32, 100, 256, 288)


def size_sweep(sizes=DOWNSTREAM_SIZES, functional=True):
    """Build EVERY downstream size and actually exercise all of its cells.

    Sizes other than 100 cannot be graded against the ``memory`` slug (that problem
    is fixed at 100 cells), so each instance is driven directly through the Rust
    engine with streams whose addresses span 0..size-1. Building is not evidence;
    this is.
    """
    fails_total = 0
    for size in sizes:
        program, ports = build_memory_solution(size)
        w, h, box = program.footprint()
        path = os.path.join("/tmp", f"fast-ram-sweep-{size}.man")
        program.save(path)
        plan = fast_ram.render_rows(size)[2]
        line = (f"  size {size:4d}: banks={plan['banks']} k={plan['k']:2d} "
                f"box={w}x{h}={box:6d} ring={fast_ram.worker_loop_ticks(plan['k'])} "
                f"workers={fast_ram.worker_count(plan['k'])}")
        if not functional:
            print(line + "  (built only)", flush=True)
            continue
        rnd = random.Random(7)
        tests = {
            "write+read all cells":
                sum(([1, a, a * 3 - 7] for a in range(size)), [])
                + sum(([0, a] for a in range(size)), []),
            "read all fresh": sum(([0, a] for a in range(size)), []),
            "descending": sum(([0, a] for a in range(size - 1, -1, -1)), []),
            "hammer addr 0": [0, 0] * 80,
            "hammer top addr": [0, size - 1] * 80,
            "extreme values": [1, 0, -1000000, 1, size - 1, 1000000, 0, 0, 0, size - 1],
            "random mix": sum(
                ([0, rnd.randrange(size)] if rnd.random() < 0.5
                 else [1, rnd.randrange(size), rnd.randint(-1000000, 1000000)]
                 for _ in range(200)), []),
        }
        fails = []
        for name, toks in tests.items():
            expect = reference(toks, size)
            if not expect:
                toks, expect = toks + [0, 0], reference(toks + [0, 0], size)
            ok, tick, raw = run_case(path, toks, expect)
            if not ok:
                fails.append((name, raw[:90]))
        fails_total += len(fails)
        print(f"{line} -> {len(tests) - len(fails)}/{len(tests)} pass", flush=True)
        for name, raw in fails:
            print(f"       FAIL {name}: {raw}", flush=True)
    return fails_total


def main():
    if "--sweep" in sys.argv:
        print("=== every downstream size: built AND functionally exercised ===")
        return 1 if size_sweep() else 0

    size = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    banks = int(sys.argv[2]) if len(sys.argv) > 2 else None
    k = int(sys.argv[3]) if len(sys.argv) > 3 else None
    program, ports = build_memory_solution(size, banks, k)
    w, h, box = program.footprint()
    path = os.path.join(REPO, "solutions", "memory", f"fast-ram-{size}.man")
    program.save(path)
    print(f"wrote {path}  box {w}x{h} = {box}  ports={ports}")

    print("\n=== 1. tools/grade_fast.py (Rust pre-filter) ===")
    out = run([sys.executable, "tools/grade_fast.py", "memory", path])
    print(out.stdout.strip() or out.stderr.strip())

    print("\n=== 2. tools/grade.js (wasm oracle -- the real judge) ===")
    out = run(["node", "tools/grade.js", "memory", path])
    print(out.stdout.strip() or out.stderr.strip())

    print("\n=== 3. marginal ticks/op ===")
    t = marginal_ticks(path)
    for name, (ok, tick, raw) in t.items():
        print(f"  {name}: {raw}")
    a, b = t["interleaved cells"][1], t["overwrite"][1]
    if a and b:
        print(f"  (interleaved {a} - overwrite {b}) / (125 - 5) = {(a - b) / 120:.4f} ticks/op")

    fit, points = tick_law(path, min(size, 100))
    if fit:
        slope, startup = fit
        print(f"  tick law over 1..256 reads: settle = {startup:.0f} + {slope:.3f}*ops")
        print(f"  points: {points}")

    print("\n=== 4. generality stress (private cases exist: champion is 24/24) ===")
    cells = min(size, 100)
    cases = stress_cases(cells)
    fails = 0
    for name, toks, expect in cases:
        ok, tick, raw = run_case(path, toks, expect)
        n = op_count(toks)
        if ok:
            print(f"  PASS  {name:34s} {len(toks):4d} tok / {n:3d} ops  settle={tick}", flush=True)
        else:
            fails += 1
            print(f"  FAIL  {name:34s} {len(toks):4d} tok / {n:3d} ops  {raw[:110]}", flush=True)
    print(f"\n  stress: {len(cases) - fails}/{len(cases)} pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
