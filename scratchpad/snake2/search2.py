"""Feasibility + score search at a PINNED controller width CW.

Phase 1: random multi-knob jumps until a CW-pinned build passes 5/5.
Phase 2: coordinate descent on that point.
Usage: python3 search2.py <CW> <min_cap> <phase1_iters>
"""
import importlib.util, json, os, random, sys, tempfile, time
import multiprocessing as mp

REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
OUT = "/Users/visenbaev/icfpc26/scratchpad/snake2"

CW = int(sys.argv[1]) if len(sys.argv) > 1 else 52
MINCAP = int(sys.argv[2]) if len(sys.argv) > 2 else 51
N1 = int(sys.argv[3]) if len(sys.argv) > 3 else 4000

BEST0 = {'ST_OUT': 23, 'FEED_W': 27, 'LOOPR': 40, 'ST_X0': 19, 'D_REP': 10,
         'D_HX': 9, 'HW_RET': 49, 'HW_TICK': 36, 'HW_SPAWN': 50, 'HW_DIR': 37,
         'D_EAT': 32, 'D_NOEAT': 33, 'DRV_OUT': 52, 'DRVX': 4, 'D_COLL': 3}
# shift the right-half columns with CW, as right_cols() would
SHIFT = {'LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT'}
START = {k: (v + (CW - 53) if k in SHIFT else v) for k, v in BEST0.items()}
START['CW'] = CW

KNOBS = {
    "ST_OUT": (16, 30), "ST_IN": (18, 32), "ST_X0": (12, 26), "ST_W": (4, 16),
    "FEED_W": (18, 34),
    "D_REP": (9, 20), "D_COLL": (1, 7), "D_HX": (3, 13), "D_HY": (2, 11),
    "HW_RET": (40, 56), "HW_TICK": (30, 48), "HW_SPAWN": (32, 52),
    "HW_DIR": (26, 44), "D_EAT": (24, 40), "D_NOEAT": (26, 42),
    "LOOPX": (32, 48), "LOOPM": (31, 47), "LOOPR": (30, 46),
    "DEC1": (12, 30), "DEC2": (16, 34), "REPD": (34, 50),
    "BD_OUT": (28, 44), "BD_IN": (34, 50), "IN_IN": (40, 56), "DRV_OUT": (42, 58),
    "WRAP_E": (42, 58), "DRVX": (1, 6), "DISX": (9, 16), "CY0": (6, 12),
}

_mod = None
_gf = None


def _init():
    global _mod, _gf
    if _mod is None:
        spec = importlib.util.spec_from_file_location(
            "bf2", REPO + "/solutions/snake/build_fold2_tuned.py")
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        _mod.MIN_CAP = MINCAP
        import grade_fast
        _gf = grade_fast


def evaluate(params):
    _init()
    fd, path = tempfile.mkstemp(suffix=".man", dir="/tmp")
    os.close(fd)
    try:
        try:
            _mod.fit(save_to=path, **params)
        except Exception:
            return None
        r = _gf.grade("snake", path, cap=60000, jobs=1)
        if r.get("passed") != r.get("total") or not r.get("total"):
            return None
        return (r["score"], r["footprint"]["box"], r["avgTicks"], open(path).read())
    finally:
        try: os.unlink(path)
        except OSError: pass


def _work(p):
    return p, evaluate(p)


def main():
    pool = mp.Pool(8)
    rng = random.Random(7 + CW)
    keys = list(KNOBS)
    best, best_score, best_man = None, float("inf"), None
    t0 = time.time()
    r = evaluate(START)
    if r:
        best, best_score, best_man = dict(START), r[0], r[3]
        print("pinned start works:", r[0], r[1], r[2], flush=True)
    # phase 1
    done = 0
    while done < N1 and best is None:
        batch = []
        for _ in range(400):
            p = dict(START)
            for k in rng.sample(keys, rng.randint(1, 6)):
                lo, hi = KNOBS[k]
                base = p.get(k)
                if base is None:
                    p[k] = rng.randint(lo, hi)
                else:
                    p[k] = max(lo, min(hi, base + rng.choice([-4, -3, -2, -1, 1, 2, 3, 4])))
            batch.append(p)
        for p, res in pool.imap_unordered(_work, batch):
            if res and res[0] < best_score:
                best, best_score, best_man = p, res[0], res[3]
                print("  feasible %d box %d ticks %.0f" % (res[0], res[1], res[2]), flush=True)
        done += 400
        print("  phase1 %d/%d %.0fs best=%s" % (done, N1, time.time() - t0, best_score), flush=True)
    if best is None:
        print("NO FEASIBLE BUILD at CW=%d" % CW, flush=True)
        return
    # phase 2: coordinate descent
    for rnd in range(6):
        improved = False
        for k, (lo, hi) in KNOBS.items():
            cands = []
            for v in range(lo, hi + 1):
                if v == best.get(k):
                    continue
                p = dict(best); p[k] = v
                cands.append(p)
            for p, res in pool.imap_unordered(_work, cands):
                if res and res[0] < best_score:
                    best, best_score, best_man = p, res[0], res[3]
                    improved = True
                    print("  %-9s -> %-3s score %d box %d ticks %.0f" %
                          (k, p[k], res[0], res[1], res[2]), flush=True)
            json.dump({"params": best, "score": best_score, "min_cap": MINCAP},
                      open(OUT + "/best_cw%d.json" % CW, "w"), indent=1)
            open(OUT + "/best_cw%d.man" % CW, "w").write(best_man)
        print("round %d best %d %.0fs" % (rnd, best_score, time.time() - t0), flush=True)
        if not improved:
            break
    print("BEST", best_score, best, flush=True)


if __name__ == "__main__":
    main()
