"""Batch evaluator for reverse-a-list candidates.

For each .man: run per-n single-round probes (n=1..16), stress rounds, and the 8
public cases. Emits one compact JSON line per program.
"""
import json, subprocess, sys, os, random
from concurrent.futures import ProcessPoolExecutor

LM = "/Users/visenbaev/icfpc26/interp/target/release/lm"
SPEC = "/Users/visenbaev/icfpc26/tests/reverse-a-list.json"

def run(prog, rounds, cap=200000):
    inp = " / ".join(" ".join(str(v) for v in r[0]) for r in rounds)
    exp = " / ".join(" ".join(str(v) for v in r[1]) for r in rounds)
    p = subprocess.run([LM, "--grade", prog, "--input=" + inp, "--expected=" + exp,
                        "--cap=%d" % cap], capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"status": "err", "settleTick": -1, "reason": p.stdout[:200] + p.stderr[:200]}

def mkround(vals):
    return ([len(vals)] + list(vals), list(reversed(vals)))

def probes():
    """(name, rounds) list."""
    out = []
    rnd = random.Random(12345)
    for n in range(1, 17):
        vals = [rnd.randint(-1000000, 1000000) for _ in range(n)]
        out.append(("n%d" % n, [mkround(vals)]))
    # multi-round batches
    out.append(("mr_123", [mkround([5]), mkround([7, 8]), mkround([1, 2, 3])]))
    out.append(("mr_desc", [mkround(list(range(1, 17))), mkround([9, 9, 9]), mkround([4])]))
    out.append(("mr_1616", [mkround(list(range(100, 116))), mkround(list(range(200, 216)))]))
    out.append(("mr_odd", [mkround([1, 2, 3]), mkround([4, 5, 6, 7, 8]), mkround([9])]))
    out.append(("mr_evens", [mkround([1, 2]), mkround([3, 4, 5, 6]), mkround([7] * 8)]))
    out.append(("dups", [mkround([4] * 16)]))
    out.append(("extreme", [mkround([-1000000, 0, 1000000, -999999])]))
    out.append(("zeros", [mkround([0] * 9)]))
    return out

PROBES = probes()

def public_cases():
    d = json.load(open(SPEC))
    cs = []
    for tc in d["publicTestData"]:
        rounds = [([int(x) for x in r["in"]], [int(x) for x in r["out"]]) for r in tc["rounds"]]
        cs.append((tc["name"], rounds))
    return cs

PUB = public_cases()

def evaluate(prog, quick=False):
    res = {"prog": prog}
    # footprint
    lines = open(prog).read().split("\n")
    minx, maxx, miny, maxy = 10**9, -1, 10**9, -1
    for y, l in enumerate(lines):
        for x, ch in enumerate(l):
            if ch != " ":
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    w = maxx - minx + 1; h = maxy - miny + 1
    res["w"], res["h"], res["box"] = w, h, max(w, h) ** 2
    vec = []
    fails = []
    for name, rounds in PROBES:
        r = run(prog, rounds, cap=60000)
        ok = r.get("status") == "pass"
        vec.append("1" if ok else ("T" if r.get("status") == "timeout" else
                                   "C" if r.get("status") in ("crash", "loaderror") else "0"))
        if not ok:
            fails.append(name + ":" + str(r.get("status")) + "/" + str(r.get("reason"))[:30])
        if quick and not ok:
            break
    res["vec"] = "".join(vec)
    res["nfail"] = res["vec"].count("0") + res["vec"].count("T") + res["vec"].count("C")
    res["fails"] = fails[:4]
    if res["nfail"] == 0:
        tot = 0; npass = 0; pub_ok = True
        for name, rounds in PUB:
            r = run(prog, rounds)
            if r.get("status") != "pass":
                pub_ok = False; res.setdefault("fails", []).append("PUB " + name)
                break
            tot += r["settleTick"]; npass += 1
        res["pub"] = npass
        if pub_ok:
            res["avg"] = tot / npass
            res["score"] = res["box"] * res["avg"]
    return res

def main():
    progs = sys.argv[1:]
    with ProcessPoolExecutor(max_workers=10) as ex:
        for r in ex.map(evaluate, progs):
            print(json.dumps(r))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
