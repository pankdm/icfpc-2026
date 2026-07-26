#!/usr/bin/env python3
"""Benchmark tools/fast_ram.py at the sizes Semester 4 needs.

Measures, per size:
  * footprint of the BARE COMPONENT (no I/O rooms)   -> w, h, max(w,h)^2
  * streaming issue interval (ticks/op) by fitting settle = a + b*ops
  * single-access end-to-end latency (settle for 1 op)
  * the same numbers for tools/split_ram.py (the incumbent) where it builds

Everything runs on the Rust engine (17x faster, and the wasm oracle OOMs).
"""
import json
import os
import subprocess
import sys

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, os.path.join(REPO, "tools"))

import littleman as lm            # noqa: E402
from layout import Layout         # noqa: E402
import fast_ram                   # noqa: E402

LM = "/Users/dmitrykorolev/projects/icfpc-2026-pfbits/interp/target/release/lm"
SIZES = [30, 32, 100, 256, 288]


# ── harness ───────────────────────────────────────────────────────────────────
def wrap(ports, program):
    """command <- I room, reply -> O room. Same wiring as the selftest."""
    lay = Layout(program)
    cx, cy = ports["command"]
    lay.put(cx, cy, "<")
    lay.put(cx + 1, cy, "<")
    program.input_room(cx + 2, cy - 1)
    rx, ry = ports["reply"]
    lay.put(rx, ry, ">")
    lay.put(*ports["reply_turn"], ">")
    program.output_room(ports["reply_turn"][0] + 1, ry - 1)
    return program


def build_fast(size):
    program = lm.Program()
    ports = fast_ram.build(program, 0, 0, size=size)
    rows, _, plan = fast_ram.render_rows(size)
    comp = (plan["width"], plan["height"])
    return wrap(ports, program), comp, plan


def build_split(size, belt_count=8):
    import split_ram
    program = lm.Program()
    ports = split_ram.build(program, 0, 0, size=size, belt_count=belt_count)
    # component-only footprint: measure BEFORE adding I/O rooms
    txt = program.render()
    lines = [l.rstrip() for l in txt.split("\n")]
    w = max((len(l) for l in lines), default=0)
    h = len([l for l in lines if l.strip()]) and (max(i for i, l in enumerate(lines) if l.strip()) + 1)
    return program, ports, (w, h)


def footprint(program):
    txt = program.render()
    rows = txt.split("\n")
    xs, ys = [], []
    for y, row in enumerate(rows):
        for x, g in enumerate(row):
            if g != " ":
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0, 0
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def run_case(path, toks_in, toks_out, cap=400000, timeout=180):
    cmd = [LM, "--grade", path, f"--cap={cap}",
           "--input=" + " ".join(map(str, toks_in)),
           "--expected=" + " ".join(map(str, toks_out))]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "walltimeout"}
    raw = (p.stdout + p.stderr).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "unparsed", "raw": raw[:300]}


def reference(tokens, cells):
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


def read_stream(n, cells):
    """n reads striding over the whole address space (worst case for locality)."""
    toks = []
    for i in range(n):
        toks += [0, (i * 37) % cells]
    return toks


# ── measurements ──────────────────────────────────────────────────────────────
def tick_law(path, cells, ns=(1, 2, 4, 8, 16, 32, 64, 128, 256)):
    pts = []
    for n in ns:
        toks = read_stream(n, cells)
        js = run_case(path, toks, reference(toks, cells))
        if js.get("status") != "pass":
            pts.append((n, None, js.get("status")))
        else:
            pts.append((n, js["settleTick"], "pass"))
    good = [(n, t) for n, t, s in pts if t is not None]
    slope = None
    if len(good) >= 2:
        (n0, t0), (n1, t1) = good[0], good[-1]
        slope = (t1 - t0) / (n1 - n0)
    return pts, slope


def main():
    out = {}
    for size in SIZES:
        program, comp, plan = build_fast(size)
        path = f"/tmp/fastram-bench-{size}.man"
        open(path, "w").write(program.render() + "\n")
        fw, fh = footprint(program)
        pts, slope = tick_law(path, size)
        rec = dict(size=size, banks=plan["banks"], k=plan["k"],
                   comp_w=comp[0], comp_h=comp[1],
                   comp_box=max(comp) ** 2,
                   full_w=fw, full_h=fh, full_box=max(fw, fh) ** 2,
                   ring=fast_ram.worker_loop_ticks(plan["k"]),
                   workers=fast_ram.worker_count(plan["k"]),
                   points=pts, slope=slope,
                   latency1=pts[0][1])
        out[size] = rec
        print(json.dumps(rec), flush=True)
    open("/tmp/fastram-bench.json", "w").write(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
