#!/usr/bin/env python3
"""Profile one LLM case with the Rust engine and print the tick attribution."""
import json, os, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp", "target", "release", "lm")
SPEC = os.path.join(REPO, "tests", "little-little-man.json")


def rounds_of(tc):
    rs = tc.get("rounds") or [tc]
    per_round_frames = [r.get("frames") or [] for r in rs]
    frames_json = json.dumps(per_round_frames) if any(per_round_frames) else ""
    return (" / ".join(" ".join(r.get("in") or []) for r in rs),
            " / ".join(" ".join(r.get("out") or []) for r in rs),
            frames_json)


def main(path, idx):
    spec = json.load(open(SPEC))
    cases = spec.get("publicTestData") or spec.get("testData") or spec["cases"]
    tc = cases[idx]
    inp, exp, frames = rounds_of(tc)
    out = subprocess.run(
        [LM, "--profile", path, f"--input={inp}", f"--expected={exp}",
         f"--frames={frames}", "--cap=30000000"],
        capture_output=True, text=True)
    err = out.stderr
    print(out.stdout[:500])
    import re, ast
    for line in err.splitlines():
        if line.startswith('PROFILE glyphs='):
            g = ast.literal_eval(line.split('=', 1)[1])
            tot = sum(v for _, v in g)
            print('total ticks by glyph', tot)
            for k, v in sorted(g, key=lambda t: -t[1])[:18]:
                print(f'  {k!r:6s} {v:>12,} {100*v/tot:5.1f}%')
        elif line.startswith('PROFILE stall_total='):
            print(line)
        elif line.startswith('PROFILE stalls='):
            st = ast.literal_eval(line.split('=', 1)[1])
            ctrl = [(xy, c) for xy, c in st if xy[1] < 690]
            svc = [(xy, c) for xy, c in st if xy[1] >= 690]
            print('controller stalls', f'{sum(c for _, c in ctrl):,}',
                  ' service/idle stalls', f'{sum(c for _, c in svc):,}')
            print('top controller stall cells (col, row, ticks, port-ish):')
            for (xy, c) in ctrl[:20]:
                print('  ', xy, f'{c:,}')


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
