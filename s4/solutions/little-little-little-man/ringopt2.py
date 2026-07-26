"""Ring-order search for the v2 op stream.

Slot -> ring-position assignment is a free choice (the belt is symmetric under
relabelling), and every access costs `(pos(target) - head) mod n` rotations of two
ops each -- so a better order is a pure win in both emitted ops (box) and executed
ops (ticks).  Objective: static emitted ops, which tracks both.

  python3 ringopt2.py [iters] [seed]
"""
import os, random, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lllm_build2 as B


def flat(o):
    n = 0
    for x in o:
        if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
            n += flat(x[1])
        else:
            n += 1
    return n


def cost(order):
    B.STATE = list(order)
    return flat(B.build())


def search(iters, seed):
    base = list(B.STATE)
    best = list(base)
    bt = cost(best)
    print("start", bt)
    rng = random.Random(seed)
    n = len(base)
    t0 = time.time()
    for it in range(iters):
        cand = list(best)
        m = rng.random()
        if m < 0.5:
            i, j = rng.sample(range(n), 2)
            cand[i], cand[j] = cand[j], cand[i]
        elif m < 0.8:
            i, j = rng.randrange(n), rng.randrange(n)
            cand.insert(j, cand.pop(i))
        else:
            i, j = sorted(rng.sample(range(n), 2))
            cand[i:j + 1] = cand[i:j + 1][::-1]
        try:
            ct = cost(cand)
        except Exception:
            continue
        if ct < bt:
            bt, best = ct, cand
            print(f"  it{it:5d} {bt}  ({time.time()-t0:.0f}s)")
    print(f"best {bt} ({100*bt/cost(base):.1f}% of start)")
    print("STATE =", best)
    return best


if __name__ == '__main__':
    search(int(sys.argv[1]) if len(sys.argv) > 1 else 3000,
           int(sys.argv[2]) if len(sys.argv) > 2 else 3)
