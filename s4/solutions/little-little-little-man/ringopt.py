"""Ring-order optimiser: permute the state ring to minimise belt rotations.

The state ring is a rotating belt; every access costs (pos(target)-head) mod n
rotations of 2 littleman ops each.  Slot->position assignment is a free choice
(the ring is symmetric under relabelling), so this is a pure win: fewer emitted
ops (smaller box) and fewer executed ops (fewer ticks) with no semantic change.

  python3 ringopt.py stats            # where the ops go under the current order
  python3 ringopt.py search [iters]   # hill-climb a better order
"""
import os, random, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lllm_build as B


def flat_count(o):
    """(total ops, r/s ops, other)"""
    tot = rs = 0
    for x in o:
        if isinstance(x, tuple):
            if x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
                t, r = flat_count(x[1])
                tot += t; rs += r
            else:
                tot += 1
        else:
            tot += 1
            if x in ('r', 's'):
                rs += 1
    return tot, rs


def cost(order):
    B.STATE = list(order)
    B.POOL = [s for s in order if s.startswith('P')]
    ops = B.build()
    return flat_count(ops)


def stats():
    tot, rs = cost(B.STATE)
    print(f"order n={len(B.STATE)}  emitted={tot}  r/s={rs} ({100*rs/tot:.1f}%)  other={tot-rs}")
    for name, fn in [("fill", B.emit_fill), ("render", B.emit_render),
                     ("fetch", B.emit_fetch), ("tick", B.emit_tick)]:
        a = B.Asm(); fn(a)
        t, r = flat_count(a.ops)
        print(f"  {name:8s} emitted={t:6d} r/s={r:6d} ({100*r/max(t,1):.1f}%)")


def search(iters=400, seed=1):
    base = list(B.STATE)
    best = list(base)
    bt, _ = cost(best)
    print(f"start emitted={bt}")
    rng = random.Random(seed)
    n = len(base)
    t0 = time.time()
    it = 0
    while it < iters:
        it += 1
        cand = list(best)
        m = rng.random()
        if m < 0.5:                      # swap two slots
            i, j = rng.sample(range(n), 2)
            cand[i], cand[j] = cand[j], cand[i]
        elif m < 0.8:                    # move one slot elsewhere
            i = rng.randrange(n); j = rng.randrange(n)
            v = cand.pop(i); cand.insert(j, v)
        else:                            # reverse a segment
            i, j = sorted(rng.sample(range(n), 2))
            cand[i:j + 1] = cand[i:j + 1][::-1]
        try:
            ct, _ = cost(cand)
        except Exception:
            continue
        if ct < bt:
            bt = ct; best = cand
            print(f"  it{it:5d} emitted={bt}  ({time.time()-t0:.0f}s)")
    print(f"best emitted={bt}  ({100*bt/ (cost(base)[0]):.1f}% of start)")
    print("ORDER =", best)
    return best


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    if what == 'stats':
        stats()
    else:
        search(int(sys.argv[2]) if len(sys.argv) > 2 else 400,
               int(sys.argv[3]) if len(sys.argv) > 3 else 1)
