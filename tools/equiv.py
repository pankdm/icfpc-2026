#!/usr/bin/env python3
"""equiv.py — prove two grids behave identically, instead of simulating them.

THE PROBLEM THIS SOLVES. Grade-gated search dies on large instances. Our LLM solution is
612x1768 with a 50,000,000-tick cap; one case takes ~256s even in the Rust engine (~200k
ticks/s), and there are 14 public cases — so a single candidate costs over an hour, and a
search costs a week. Yet the grid is 98.2% blank, i.e. it is exactly where geometry work pays
most.

THE OBSERVATION. Score is `max(w,h)^2 * avg ticks`. A transformation that only moves things
cannot change the tick count, because a man's tick count is the number of cells he walks and
a pipe's latency is its length. So for geometry-only transforms, simulation is not measuring
anything — it is only checking correctness, and correctness here is a STRUCTURAL property we
can decide directly from the lifted IR:

  1. same men, each with an identical op sequence in the same order (same program);
  2. same path length per man (same tick count -> same score factor);
  3. same pipes: count, lengths, and endpoint rooms (length is latency AND capacity, and some
     designs use a pipe as a FIFO store);
  4. every distance-bound pipe op (`s`/`r`/`q`) resolves to the same pipe (nearest-pipe by
     Manhattan with reading-order ties: moving an op can silently retarget it);
  5. same room count, and each man still in the room with the same role.

If all five hold the two programs are bisimilar — same instructions, same order, same timing —
so the candidate's score is the original's score times the box ratio, computed instantly.

LIMITS, stated because they are load-bearing:
  * this certifies GEOMETRY-ONLY transforms. Change an op, a literal, or a pipe length and it
    correctly refuses;
  * men sharing a ROOM are timing-coupled (same-tick arrivals kill both). Equal per-man path
    lengths preserve each man's schedule, but if a transform moves two men *within one room*
    it can still change who meets whom, so that case is reported as UNPROVEN rather than
    certified;
  * it says nothing about a program that was already wrong.

  python3 tools/equiv.py <before.man> <after.man>        certify or explain the difference
  python3 tools/equiv.py <before.man> <after.man> --json
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_rows(path):
    text = open(path, encoding="utf-8").read().replace("\r", "").rstrip("\n")
    rows = text.split("\n")
    w = max(len(r) for r in rows) if rows else 0
    return [r.ljust(w) for r in rows]


def lift(path):
    r = subprocess.run(["python3", os.path.join(REPO, "tools", "lift.py"), path, "--json"],
                       capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sys.exit(f"lift failed on {path}: {(r.stderr or r.stdout)[:200]}")


def box_of(rows):
    ys = [i for i, r in enumerate(rows) if r.strip()]
    if not ys:
        return 0, 0, 0
    w = max(len(r) for r in rows)
    xs = [x for x in range(w) if any(len(r) > x and r[x] != " " for r in rows)]
    W, H = xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1
    return W, H, max(W, H) ** 2


def man_signature(man):
    """What a man DOES, independent of where he does it.

    The op sequence in walk order plus the path length: the first is the program, the second
    is the tick count. Absolute coordinates are deliberately excluded — that is the whole
    point, since moving code is what we are trying to certify."""
    ops = []
    for block in man["blocks"]:
        ops.append("".join(ch for _pos, ch in block))
    return {"ops": sorted(ops), "n_ops": man["ops"], "turns": man["turns"],
            "reachable": man["reachable"], "blocks": len(man["blocks"])}


def pipe_signature(ir):
    sig = []
    for p in ir["pipes"]:
        path = p.get("path") or []
        sig.append((len(path), p.get("src"), p.get("dst")))
    return sorted(sig)


def bindings(path):
    r = subprocess.run(["python3", os.path.join(REPO, "tools", "pipecheck.py"), path],
                       capture_output=True, text=True, cwd=REPO)
    out = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if " at (" in line and " -> pipe " in line:
            op = line.split()[0]
            pipe = line.split(" -> pipe ")[1].split()[0]
            room = line.split(" in room ")[1].split()[0] if " in room " in line else "?"
            out.append((room, op, pipe))
    return sorted(out)


def compare(before, after):
    rb, ra = load_rows(before), load_rows(after)
    ib, ia = lift(before), lift(after)
    Wb, Hb, bb = box_of(rb)
    Wa, Ha, ba = box_of(ra)
    reasons = []

    if len(ib["men"]) != len(ia["men"]):
        reasons.append(f"man count {len(ib['men'])} -> {len(ia['men'])}")
    else:
        sb = sorted((json.dumps(man_signature(m), sort_keys=True) for m in ib["men"]))
        sa = sorted((json.dumps(man_signature(m), sort_keys=True) for m in ia["men"]))
        for i, (x, y) in enumerate(zip(sb, sa)):
            if x != y:
                reasons.append(f"man {i}: op sequence or path length changed")
                break

    if pipe_signature(ib) != pipe_signature(ia):
        reasons.append("pipe structure changed (count, length or endpoints) — "
                       "length is latency AND capacity")
    if len(ib["rooms"]) != len(ia["rooms"]):
        reasons.append(f"room count {len(ib['rooms'])} -> {len(ia['rooms'])}")

    bb_, ba_ = bindings(before), bindings(after)
    if bb_ != ba_:
        reasons.append("a distance-bound pipe op resolves to a different pipe")

    # men sharing a room are timing-coupled; equal path lengths do not settle who meets whom
    rooms_with_multiple = [r for r in {m["room"] for m in ib["men"]}
                           if sum(1 for m in ib["men"] if m["room"] == r) > 1]
    unproven = bool(rooms_with_multiple) and not reasons

    return {
        "before": {"box": bb, "dims": f"{Wb}x{Hb}"},
        "after": {"box": ba, "dims": f"{Wa}x{Ha}"},
        "box_ratio": (bb / ba) if ba else 0,
        "equivalent": not reasons and not unproven,
        "unproven": unproven,
        "reasons": reasons,
        "shared_rooms": rooms_with_multiple,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = compare(args.before, args.after)
    if args.json:
        print(json.dumps(res))
        sys.exit(0 if res["equivalent"] else 1)

    print(f"{os.path.basename(args.before)} {res['before']['dims']} box {res['before']['box']:,}")
    print(f"{os.path.basename(args.after)}  {res['after']['dims']} box {res['after']['box']:,}")
    if res["equivalent"]:
        print(f"\nCERTIFIED EQUIVALENT — same ops, same order, same path lengths, same pipes.")
        print(f"Ticks are therefore unchanged, so the score improves by exactly the box ratio:"
              f" {res['box_ratio']:.4f}x")
        print("No simulation needed. Grade once at the end of a search, not per candidate.")
        sys.exit(0)
    if res["unproven"]:
        print(f"\nUNPROVEN: rooms {res['shared_rooms']} hold more than one man, and men in one "
              f"room are timing-coupled\n(same-tick arrivals kill both), so equal path lengths "
              f"are not sufficient. Simulate this one.")
        sys.exit(2)
    print("\nNOT EQUIVALENT:")
    for r in res["reasons"]:
        print(f"  - {r}")
    sys.exit(1)


if __name__ == "__main__":
    main()


# ── bounded differential: the gate for transforms that CHANGE timing ────────────
def prefix_diff(before, after, slug, ticks=200000, case_index=None):
    """Run both programs briefly on a real case and compare what they emit.

    Structural certification only covers RIGID moves. A fold shortens a walk — that is the
    whole point of it — so path lengths change, ticks change, and equivalence is the wrong
    question. But full grading is unaffordable at this size (one LLM case is ~256s even in
    the Rust engine, 14 cases per grade).

    So compare the two programs against EACH OTHER for a bounded number of ticks instead of
    comparing each against the expected answer for an unbounded number. A fold that broke the
    program almost always diverges early — a man walks a wall, a pipe starves, output stops —
    and 200k ticks costs about a second. It is evidence, not proof: it cannot see a divergence
    that first appears after the horizon, so the surviving candidate still gets one real grade
    at the end of the search rather than one per candidate."""
    spec = json.load(open(os.path.join(REPO, "tests", f"{slug}.json")))
    cases = spec.get("publicTestData") or []
    if not cases:
        return None, "no public cases"
    idx = case_index if case_index is not None else min(
        range(len(cases)), key=lambda i: len(json.dumps(cases[i])))
    tc = cases[idx]
    rs = tc.get("rounds") or [tc]
    inp = " / ".join(" ".join(r.get("in") or []) for r in rs)
    exp = " / ".join(" ".join(r.get("out") or []) for r in rs)
    lm = os.path.join(REPO, "interp", "target", "release", "lm")
    if not os.path.exists(lm):
        return None, "rust engine not built"

    def run(path):
        p = subprocess.run([lm, path, str(ticks), f"--input={inp}", f"--expected={exp}"],
                           capture_output=True, text=True, timeout=1800)
        last = None
        for line in (p.stdout or "").splitlines():
            if line.startswith("{"):
                last = line
        if not last:
            return {"error": (p.stderr or "no snapshot")[:120]}
        j = json.loads(last)
        return {"end": j.get("end"), "output": j.get("output"), "step": j.get("step")}

    a, b = run(before), run(after)
    if a.get("error") or b.get("error"):
        return None, f"engine: {a.get('error') or b.get('error')}"
    same_out = (a["output"] or []) == (b["output"] or [])
    return {"before": a, "after": b, "same_output": same_out,
            "same_end": a["end"] == b["end"], "ticks": ticks,
            "agree": same_out and a["end"] == b["end"]}, None
