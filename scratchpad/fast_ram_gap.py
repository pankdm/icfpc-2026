#!/usr/bin/env python3
"""Idle-gap / dependent-chain rig for tools/fast_ram.py.

The self-test only ever drives the component from a saturated input pipe, which
measures the pipelined ISSUE INTERVAL (8 ticks/op).  Semester 4 consumers do not
stream: they read a cell, compute on it, and only then read again.  This rig puts
a programmable RATE LIMITER between the input room and the RAM's command port, so
requests arrive every G ticks instead of back to back.

      +---+ I room
      |   |
   RAM <--[ spacer loop ]<-- I
      command      period 2W-2 ticks per TOKEN

The spacer is a single man walking a (W x 3) racetrack:

      @v            man spawns facing east, drops into the loop
       >r>>>>>>v    'r' pulls one token off the input pipe
       ^s<<<<<<<    's' pushes it at the RAM, one lap later

so one token leaves every 2*(W-1) ticks and a 2-token READ is issued every
4*(W-1) ticks.  Two things fall out of a sweep over W:

  * settle(n) - (n-1)*G is constant  <=>  per-request latency does not depend on
    how idle the machine was  <=>  no worker die-off / starvation.
  * subtracting the same rig with the RAM replaced by a bare output room removes
    the spacer's own transit and boot, leaving the RAM's ROUND-TRIP LATENCY --
    the number a dependent-chain consumer actually pays.
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


def spacer(lay, x0, y0, w):
    """Rate limiter. Room top-left wall at (x0, y0); interior w x 3.

    Returns nothing; the caller wires (x0-1, y0+2) westward and (x0+w+2, y0+2)
    from the east.  Period = 2*(w-1) ticks per token.
    """
    prog = lay.p
    prog.room(x0, y0, w + 2, 5)
    ix, iy = x0 + 1, y0 + 1          # interior origin
    lay.put(ix, iy, "@")
    lay.put(ix + 1, iy, "v")
    lay.put(ix + 1, iy + 1, ">")
    lay.put(ix + 2, iy + 1, "r")
    for c in range(3, w - 1):
        lay.put(ix + c, iy + 1, ">")
    lay.put(ix + w - 1, iy + 1, "v")
    lay.put(ix + w - 1, iy + 2, "<")
    lay.put(ix + 2, iy + 2, "s")
    for c in range(3, w - 1):
        lay.put(ix + c, iy + 2, "<")
    lay.put(ix + 1, iy + 2, "^")


def build_rig(size, w, bare=False):
    """RAM + spacer, or (bare=True) spacer -> output room with no RAM at all."""
    program = lm.Program()
    lay = Layout(program)
    if bare:
        # output room where the RAM's command port would be, same row.
        cx, cy = 40, 2
        program.output_room(cx - 4, cy - 1)
        lay.put(cx - 1, cy, "<")
        lay.put(cx, cy, "<")
    else:
        ports = fast_ram.build(program, 0, 0, size=size)
        cx, cy = ports["command"]
        rx, ry = ports["reply"]
        lay.put(rx, ry, ">")
        lay.put(*ports["reply_turn"], ">")
        program.output_room(ports["reply_turn"][0] + 1, ry - 1)
    # command pipe: 3 cells flowing west, ending on the port
    for dx in range(3):
        lay.put(cx + dx, cy, "<")
    x0 = cx + 3
    spacer(lay, x0, cy - 2, w)
    # input pipe into the spacer's right wall
    lay.put(x0 + w + 2, cy, "<")
    lay.put(x0 + w + 3, cy, "<")
    program.input_room(x0 + w + 4, cy - 1)
    return program


def run(path, toks_in, toks_out, cap=2000000, timeout=300):
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
        return {"status": "unparsed", "raw": raw[:400]}


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


def stream(n, cells):
    return [t for i in range(n) for t in (0, (i * 37) % cells)]


def main():
    sizes = [int(a) for a in sys.argv[1:]] or [32, 288]
    widths = [4, 6, 11, 26, 51, 101, 251, 501]
    n = 8
    out = {}
    for size in sizes:
        rows = []
        for w in widths:
            gap_tok = 2 * (w - 1)
            gap_op = 2 * gap_tok
            prog = build_rig(size, w)
            path = f"/tmp/fastram-gap-{size}-{w}.man"
            open(path, "w").write(prog.render() + "\n")
            toks = stream(n, size)
            js = run(path, toks, reference(toks, size))
            settle = js.get("settleTick")
            # same spacer, no RAM: pure spacer transit + boot for the same stream
            bprog = build_rig(size, w, bare=True)
            bpath = f"/tmp/fastram-gapbare-{size}-{w}.man"
            open(bpath, "w").write(bprog.render() + "\n")
            bjs = run(bpath, toks, toks)   # bare rig echoes the token stream
            bsettle = bjs.get("settleTick")
            rows.append(dict(w=w, gap_op=gap_op, status=js.get("status"),
                             settle=settle, bare_status=bjs.get("status"),
                             bare_settle=bsettle,
                             intercept=None if settle is None else settle - (n - 1) * gap_op,
                             rt=None if (settle is None or bsettle is None) else settle - bsettle))
            print(size, rows[-1], flush=True)
        out[size] = rows
    open("/tmp/fastram-gap.json", "w").write(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()


# ── realistic stimulus: whole OPS are spaced, tokens inside an op are not ──────
def pair_spacer(lay, x0, y0, w):
    """Rate limiter that buffers a WHOLE READ (2 tokens) and emits it as a burst.

    This is what a stateflow consumer actually does: one man sends [0, addr] back
    to back, then goes away and computes for a while.  Period = 2*(w-1) ticks per
    OP; the two tokens leave 2 ticks apart.

        >rMr>>>>v      r;M(B=A);r  -- buffer both tokens
        ^sWsW<<<<      W;s;W;s     -- burst them out, then a full lap of silence
    """
    prog = lay.p
    prog.room(x0, y0, w + 2, 5)
    ix, iy = x0 + 1, y0 + 1
    lay.put(ix, iy, "@")
    lay.put(ix + 1, iy, "v")
    for c, g in ((1, ">"), (2, "r"), (3, "M"), (4, "r")):
        lay.put(ix + c, iy + 1, g)
    for c in range(5, w - 1):
        lay.put(ix + c, iy + 1, ">")
    lay.put(ix + w - 1, iy + 1, "v")
    lay.put(ix + w - 1, iy + 2, "<")
    for c in range(6, w - 1):
        lay.put(ix + c, iy + 2, "<")
    for c, g in ((5, "W"), (4, "s"), (3, "W"), (2, "s"), (1, "^")):
        lay.put(ix + c, iy + 2, g)


def build_pair_rig(size, w, bare=False):
    program = lm.Program()
    lay = Layout(program)
    if bare:
        cx, cy = 40, 2
        program.output_room(cx - 4, cy - 1)
        lay.put(cx - 1, cy, "<")
        lay.put(cx, cy, "<")
    else:
        ports = fast_ram.build(program, 0, 0, size=size)
        cx, cy = ports["command"]
        rx, ry = ports["reply"]
        lay.put(rx, ry, ">")
        lay.put(*ports["reply_turn"], ">")
        program.output_room(ports["reply_turn"][0] + 1, ry - 1)
    for dx in range(3):
        lay.put(cx + dx, cy, "<")
    x0 = cx + 3
    pair_spacer(lay, x0, cy - 2, w)
    lay.put(x0 + w + 2, cy, "<")
    lay.put(x0 + w + 3, cy, "<")
    program.input_room(x0 + w + 4, cy - 1)
    return program
