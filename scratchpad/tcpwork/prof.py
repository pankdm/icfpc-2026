#!/usr/bin/env python3
"""Run the rust engine's --profile on one named tcp public case."""
import json, os, subprocess, sys
REPO = "/Users/visenbaev/icfpc26"
LM = os.path.join(REPO, "interp/target/release/lm")

def case(name_sub):
    spec = json.load(open(os.path.join(REPO, "tests/tcp.json")))
    for tc in spec["publicTestData"]:
        if name_sub in tc["name"]:
            return tc
    raise SystemExit("no case " + name_sub)

def main():
    man = sys.argv[1]
    tc = case(sys.argv[2] if len(sys.argv) > 2 else "block-reversed")
    rs = tc["rounds"]
    inp = " / ".join(" ".join(r["in"]) for r in rs)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
    p = subprocess.run([LM, "--profile", man, f"--input={inp}", f"--expected={exp}", "--cap=5000000"],
                       capture_output=True, text=True)
    print(p.stdout[-6000:])
    if p.stderr: print("ERR", p.stderr[:2000], file=sys.stderr)

main()
