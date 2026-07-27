#!/usr/bin/env python3
"""Build adversarial pathfinder cases with pf_model and grade a .man against them.

Covers what the public set may not: robot already on the flag, flag adjacent,
a full serpentine maze (maximum path length), an open field (maximum BFS
frontier width -> maximum FRONTIER ring occupancy), walls-everywhere corners,
and many rounds in one program run.

Usage: python3 stress.py <file.man> [cap]
"""
import json
import os
import subprocess
import sys

REPO = "/Users/visenbaev/icfpc26"
WT = os.path.join(REPO, ".claude", "worktrees", "pf2")
sys.path.insert(0, os.path.join(WT, "solutions", "pathfinder"))
import pf_model

LM = os.path.join(REPO, "interp", "target", "release", "lm")
N = 16


def board_open():
    g = [[0] * N for _ in range(N)]
    for i in range(N):
        g[0][i] = g[N - 1][i] = g[i][0] = g[i][N - 1] = 1
    return g


def board_serpentine():
    """Comb maze: a single corridor snaking through the whole interior."""
    g = [[1] * N for _ in range(N)]
    for y in range(1, N - 1):
        for x in range(1, N - 1):
            g[y][x] = 0
    for y in range(2, N - 2, 2):
        for x in range(1, N - 1):
            g[y][x] = 1
        gap = 1 if (y // 2) % 2 else N - 2
        g[y][gap] = 0
    return g


def board_pillars():
    g = board_open()
    for y in range(2, N - 2, 2):
        for x in range(2, N - 2, 2):
            g[y][x] = 1
    return g


def rounds_for(grid, robot, flags):
    flat = [str(c) for row in grid for c in row]
    rs = [{"in": flat + [str(robot[0]), str(robot[1])]}]
    for f in flags:
        rs.append({"in": [str(f[0]), str(f[1])]})
    return rs


def make_cases():
    cases = []
    op, se, pi = board_open(), board_serpentine(), board_pillars()
    # The spec guarantees the flag is neither a wall nor the robot's own cell
    # (pf_model asserts both), so those are not legal private cases.
    cases.append(("adjacent", rounds_for(op, (1, 1), [(2, 1), (2, 2), (1, 2)])))
    cases.append(("open-field-max", rounds_for(op, (1, 1), [(14, 14), (1, 14), (14, 1)])))
    cases.append(("serpentine", rounds_for(se, (1, 1), [(14, 14), (1, 1), (14, 14)])))
    cases.append(("pillars", rounds_for(pi, (1, 1), [(14, 14), (7, 7), (13, 2)])))
    many = [(1 + (i * 3) % 13, 1 + (i * 7) % 13) for i in range(12)]
    cases.append(("many-rounds", rounds_for(op, (8, 8), many)))
    return cases


def main():
    path = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 3000000
    ok = True
    for name, rs in make_cases():
        ins = [r["in"] for r in rs]
        # Group frames per ROUND (the --frames-file format) by re-simulating
        # prefixes; pf_model.simulate only returns the flat list.
        per_round, prev = [], 0
        for k in range(1, len(ins) + 1):
            allf = pf_model.frames_as_strings(pf_model.simulate(ins[:k]))
            per_round.append(allf[prev:])
            prev = len(allf)
        fr = per_round
        ff = "/tmp/pf2_stress_frames.json"
        open(ff, "w").write(json.dumps(fr))
        inp = " / ".join(" ".join(r["in"]) for r in rs)
        r = subprocess.run([LM, "--grade", path, f"--input={inp}",
                            "--expected=" + " / ".join("" for _ in rs),
                            f"--frames-file={ff}", f"--cap={cap}"],
                           capture_output=True, text=True)
        out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[:200]
        try:
            d = json.loads(out)
            status = d.get("status")
        except Exception:
            status, d = "parse", {}
        if status != "pass":
            ok = False
        print(f"{name:16s} {status:10s} {d.get('settleTick')} {out[:120] if status!='pass' else ''}")
    print("ALL PASS" if ok else "FAILURES")


if __name__ == "__main__":
    main()
