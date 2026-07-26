#!/usr/bin/env python3
"""Per-op tick cost microbenchmark for gradebook (direct `lm --grade`).

N=16 K=4 roster, then R rounds x P identical ops.  Marginal cost per op =
(ticks - roster_baseline) / (R*P).
usage: gb_bench.py [file.man] [--n N] [--k K]
"""
import json, random, subprocess, sys

REPO = "/Users/visenbaev/icfpc26"
LM = f"{REPO}/interp/target/release/lm"
MAN = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") \
    else f"{REPO}/solutions/gradebook/champion-f26bbd24.man"


def build(N, K, mk, rounds, per):
    random.seed(7)
    ids = random.sample(range(1000, 10000), N)
    st = {i: [random.randint(0, 100) for _ in range(K)] for i in ids}
    inp = [str(N), str(K)]
    for i in ids:
        inp.append(str(i))
        inp += [str(x) for x in st[i]]
    rin, rout = [" ".join(inp)], [""]
    for r in range(rounds):
        ops = [mk(ids, K, r * per + k) for k in range(per)]
        flat = [str(per)]
        outv = []
        for op in ops:
            flat += [str(x) for x in op]
            if op[0] == 1:
                outv.append(str(st[op[1]][op[2] - 1]))
            elif op[0] == 2:
                st[op[1]][op[2] - 1] = op[3]
            elif op[0] == 3:
                s = op[1]
                outv.append(str(sum(st[i][s - 1] for i in ids) // N))
            elif op[0] == 4:
                s = op[1]
                best = max(st[i][s - 1] for i in ids)
                outv.append(str(min(i for i in ids if st[i][s - 1] == best)))
        rin.append(" ".join(flat))
        rout.append(" ".join(outv))
    return " / ".join(rin), " / ".join(rout)


def run(man, inp, exp, cap=5_000_000):
    p = subprocess.run([LM, "--grade", man, f"--input={inp}", f"--expected={exp}",
                        f"--cap={cap}"], capture_output=True, text=True)
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"status": "err", "raw": (p.stdout + p.stderr)[:200]}


KINDS = {
    "GET": lambda ids, K, k: (1, ids[k % len(ids)], k % K + 1),
    "SET": lambda ids, K, k: (2, ids[k % len(ids)], k % K + 1, (k * 7) % 101),
    "AVG": lambda ids, K, k: (3, k % K + 1),
    "TOP": lambda ids, K, k: (4, k % K + 1),
}

if __name__ == "__main__":
    for (N, K) in [(16, 4), (16, 1), (4, 4), (4, 1)]:
        i0, e0 = build(N, K, None, 0, 0)
        base = run(MAN, i0, e0)
        bt = base.get("settleTick", 0)
        print(f"N={N} K={K}  roster-only ticks={bt} ({base['status']})")
        for name, mk in KINDS.items():
            R, P = 10, 8
            i1, e1 = build(N, K, mk, R, P)
            v = run(MAN, i1, e1)
            t = v.get("settleTick", 0)
            print(f"   {name}x{R*P:<3} {v['status']:6s} ticks={t:7d} "
                  f"marginal/op={(t - bt) / (R * P):8.1f}")
