#!/usr/bin/env python3
"""grade_fast.py — grade a .man with the Rust engine, in the same envelope as grade_json.js.

Measured ~17x faster than the WASM oracle (0.07s vs 1.19s for sudoku's six cases), because
it skips a Go/WASM boot per invocation. That multiplies every search: most candidates a
search generates are rejects, and paying the oracle to reject them is the dominant cost.

USE IT AS A PRE-FILTER, NOT AS THE JUDGE. `interp/` is a reimplementation and still has one
known divergence from the reference (`fork-into-wall`, per `node sim/difftest.js`), so:

    fast reject  -> discard the candidate (cheap, and rejects are the common case)
    fast pass    -> RE-GRADE with tools/grade_json.js before believing it

`--verify` does exactly that pairing and reports any disagreement, which is also how you
re-validate the engine after touching `interp/`.

  python3 tools/grade_fast.py <slug> <file.man> [--cap N] [--verify]

Build the engine first: cd interp && cargo build --release
"""
import argparse
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LM = os.path.join(REPO, "interp", "target", "release", "lm")


def rounds_of(tc):
    """(input, expected, framesJson) exactly as tools/lib.js buildCase() forms them.

    Display problems express their expectation as FRAMES, not integers. Omitting them does
    not fail loudly — the engine simply has nothing to match, so it never settles and runs to
    the tick cap, reporting `pass` with avgTicks = cap. That looked like an engine bug on
    plotter (32.8e9 vs the oracle's 202e6) and was this omission."""
    rs = tc.get("rounds") or [tc]
    per_round_frames = [r.get("frames") or [] for r in rs]
    frames_json = json.dumps(per_round_frames) if any(per_round_frames) else ""
    return (" / ".join(" ".join(r.get("in") or []) for r in rs),
            " / ".join(" ".join(r.get("out") or []) for r in rs),
            frames_json)


def footprint(path):
    rows = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
    ys = [i for i, r in enumerate(rows) if r.strip()]
    if not ys:
        return {"w": 0, "h": 0, "box": 0}
    w = max(len(r) for r in rows)
    xs = [x for x in range(w) if any(len(r) > x and r[x] != " " for r in rows)]
    W, H = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    return {"w": W, "h": H, "box": max(W, H) ** 2}


def grade(slug, man, cap=None):
    spec_path = os.path.join(REPO, "tests", f"{slug}.json")
    if not os.path.exists(spec_path):
        return {"error": f"no cached spec tests/{slug}.json"}
    if not os.path.exists(LM):
        return {"error": "rust engine not built (cd interp && cargo build --release)"}
    spec = json.load(open(spec_path))
    cases = spec.get("publicTestData") or []
    tick_cap = cap or spec.get("tickCap") or 5_000_000
    results, ticks = [], []
    for tc in cases:
        inp, exp, frames = rounds_of(tc)
        cmd = [LM, "--grade", man, f"--input={inp}", f"--expected={exp}", f"--cap={int(tick_cap)}"]
        if frames:
            cmd.append(f"--frames={frames}")
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        try:
            v = json.loads((p.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"error": f"engine: {(p.stderr or p.stdout or '')[:120]}"}
        results.append({"name": tc.get("name", "(case)"), **v})
        if v.get("status") == "pass":
            ticks.append(v.get("settleTick") or 0)
    passed = sum(1 for r in results if r.get("status") == "pass")
    fp = footprint(man)
    avg = (sum(ticks) / len(ticks)) if ticks else None
    score = None
    if passed == len(results) and results:
        score = fp["box"] if spec.get("scoring") == "footprint" else (
            fp["box"] * avg if avg is not None else None)
    return {"passed": passed, "total": len(results), "footprint": fp,
            "avgTicks": avg, "score": score, "results": results}


def oracle(slug, man, cap=None):
    cmd = ["node", os.path.join(REPO, "tools", "grade_json.js"), slug, man]
    if cap:
        cmd += ["--cap", str(int(cap))]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=1800)
    try:
        return json.loads((p.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (p.stderr or "oracle failed")[:120]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--cap", type=int)
    ap.add_argument("--verify", action="store_true",
                    help="also grade with the oracle and report any disagreement")
    args = ap.parse_args()

    t0 = time.time()
    fast = grade(args.slug, args.man, args.cap)
    t_fast = time.time() - t0
    if not args.verify:
        print(json.dumps(fast))
        return
    t0 = time.time()
    slow = oracle(args.slug, args.man, args.cap)
    t_slow = time.time() - t0
    print(f"rust   {t_fast:6.2f}s  {fast.get('passed')}/{fast.get('total')} "
          f"score {fast.get('score')}")
    print(f"oracle {t_slow:6.2f}s  {slow.get('passed')}/{slow.get('total')} "
          f"score {slow.get('score')}   ({t_slow / max(t_fast, 1e-6):.1f}x slower)")
    same = (fast.get("passed") == slow.get("passed") and fast.get("total") == slow.get("total")
            and (fast.get("score") is None) == (slow.get("score") is None)
            and (fast.get("score") is None
                 or abs(fast["score"] - slow["score"]) <= max(1.0, 1e-6 * slow["score"])))
    print("AGREE" if same else "DISAGREE — trust the oracle, and re-check interp/")
    sys.exit(0 if same else 1)


if __name__ == "__main__":
    main()
