#!/usr/bin/env python3
"""Watch what flows through a chainfield pipe.

usage: python3 scratchpad/cf_trace.py <file.man> <steps> "<input>" [pipe_index]
Without pipe_index it lists every pipe with its src/dst cell so you can pick one.
With one, it prints the ordered stream of values that reached that pipe's dst.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LM = os.path.join(REPO, "interp", "target", "release", "lm")


def main():
    path, steps, inp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    which = int(sys.argv[4]) if len(sys.argv) > 4 else None
    p = subprocess.run([LM, path, str(steps), "--input=" + inp],
                       capture_output=True, text=True)
    lines = p.stdout.strip().split("\n")
    first = json.loads(lines[0])
    if which is None:
        for pi in first["pipes"] or []:
            print(pi["id"], "src", pi["src"], "dst", pi["dst"],
                  "srcRoom", pi["srcRoom"], "dstRoom", pi["dstRoom"])
        return
    seen = []
    prev = None
    for ln in lines:
        d = json.loads(ln)
        pipes = d.get("pipes") or []
        pipe = next((x for x in pipes if x["id"] == which), None)
        if pipe is None:
            continue
        vals = pipe["values"] or []
        n = len(vals) - 1
        last = None
        for v in vals:
            if v["index"] == n:
                last = v["value"]
        if last is not None and last != prev:
            seen.append((d["step"], last))
        prev = last
    print("stream:", [v for _, v in seen])
    print("ticks :", [t for t, _ in seen][:40])


main()
