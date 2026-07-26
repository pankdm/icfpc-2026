#!/usr/bin/env python3
"""Probe the three primitives the carousel matmul depends on."""
import os
import subprocess
import sys

REPO = os.path.abspath(__file__).split("/scratchpad/")[0]
sys.path.insert(0, REPO + "/tools")
import littleman as lm  # noqa: E402

LM = REPO + "/interp/target/release/lm"
OUT = "/private/tmp/claude-502/-Users-dmitrykorolev-projects-icfpc-2026/0580956d-53cb-4ded-b43a-408e532171a2/scratchpad"


def run(p, name, inp, exp):
    path = f"{OUT}/{name}.man"
    p.save(path)
    r = subprocess.run([LM, "--grade", path, f"--input={inp}", f"--expected={exp}",
                        "--cap=3000"], capture_output=True, text=True)
    print(f"  {name:<22} in=[{inp}] exp=[{exp}] -> {r.stdout.strip()[:160]}")
    return r.stdout


# ---- probe 1: does `s` preserve A?  does `*` preserve B? -------------------
# r(A=x) M(B=x) r(A=y) *(A=x*y, B=?) W(A=B) s s
# if `*` preserves B then after W, A == x, and two `s` emit it twice if `s`
# preserves A.  input 3 5 -> expect "3 3".
def probe1():
    p = lm.Program()
    p.room(0, 0, 11, 3)
    p.text(1, 1, "@rMr*Wss")
    p.input_room(0, 5)
    p.output_room(6, 5)
    p.pipe([(1, 4), (1, 3)], end_direction="N")        # I -> main (bottom wall)
    p.pipe([(7, 3), (7, 4)], end_direction="S")        # main -> O (top wall of O)
    run(p, "probe1_regs", "3 5", "3 3")


# ---- probe 2: can a pipe connect a room to ITSELF? ------------------------
# read x, send to the self-loop, receive it back, send to output.
def probe2():
    p = lm.Program()
    p.room(0, 2, 11, 3)
    p.text(1, 3, "@rs.rs")
    p.input_room(0, 7)
    p.output_room(7, 7)
    p.pipe([(1, 6), (1, 5)], end_direction="N")        # I -> main
    p.pipe([(8, 5), (8, 6)], end_direction="S")        # main -> O
    # self loop: leaves top wall at x=3, re-enters top wall at x=6
    p.pipe([(3, 1), (3, 0), (6, 0), (6, 1)], end_direction="S")
    run(p, "probe2_selfloop", "7", "7")


# ---- probe 3: two men in one room on a shared loop (the carousel core) ----
# a 8-cell loop, one man, echoing input to output forever-ish.
def probe3():
    p = lm.Program()
    p.room(0, 2, 8, 4)
    p.text(1, 3, "@r>>v")        # top row of the loop
    p.put(6, 3, "v")
    p.text(1, 4, "^s<<")
    p.input_room(0, 7)
    p.output_room(5, 7)
    p.pipe([(1, 6), (1, 5)], end_direction="N")
    p.pipe([(6, 6), (6, 7)], end_direction="S")
    run(p, "probe3_loop", "4 9", "4 9")


print("probe results (Rust engine):")
probe1()
probe2()
probe3()
