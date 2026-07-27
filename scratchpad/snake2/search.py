"""Multi-knob graded search over solutions/snake/build_fold2_tuned.py geometry.

Each candidate: fit() the builder with a knob dict, grade_fast on all 5 public
cases, keep only 5/5 passes, minimise box*avgTicks.
Usage: python3 search.py <mode> [iters]
  mode = coord | rand
"""
import importlib.util, json, os, random, sys, tempfile, time
import multiprocessing as mp

REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
sys.path.insert(0, REPO + "/solutions/snake")
OUT = "/Users/visenbaev/icfpc26/scratchpad/snake2"

BASE = dict(CW=53, ST_OUT=23, FEED_W=27, LOOPR=40)

# knob -> (lo, hi) search range.  Absolute column values unless noted.
KNOBS = {
    "CW": (48, 60),
    "CY0": (6, 12),
    "ST_OUT": (18, 30), "ST_IN": (18, 32), "ST_X0": (12, 26), "ST_W": (4, 16),
    "FEED_W": (20, 34),
    "D_REP": (10, 20), "D_COLL": (1, 6), "D_HX": (4, 12), "D_HY": (2, 10),
    "HW_RET": (44, 56), "HW_TICK": (34, 48), "HW_SPAWN": (36, 50),
    "HW_DIR": (30, 42), "D_EAT": (26, 38), "D_NOEAT": (28, 40),
    "LOOPX": (36, 48), "LOOPM": (35, 47), "LOOPR": (34, 46),
    "DEC1": (14, 30), "DEC2": (18, 34), "REPD": (38, 50),
    "BD_OUT": (31, 43), "BD_IN": (37, 49), "IN_IN": (43, 55), "DRV_OUT": (45, 57),
    "WRAP_E": (45, 57),
    "DRVX": (1, 6), "DISX": (9, 16),
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
        import grade_fast
        _gf = grade_fast


def evaluate(params):
    _init()
    fd, path = tempfile.mkstemp(suffix=".man", dir="/tmp")
    os.close(fd)
    try:
        kw = dict(params)
        try:
            _mod.fit(save_to=path, **kw)
        except Exception as e:
            return None
        r = _gf.grade("snake", path, cap=60000, jobs=1)
        if r.get("passed") != r.get("total") or not r.get("total"):
            return None
        score = r["score"]
        return (score, r["footprint"]["box"], r["avgTicks"],
                open(path).read())
    finally:
        try: os.unlink(path)
        except OSError: pass


def _work(p):
    return p, evaluate(p)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "coord"
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    best = dict(BASE)
    r0 = evaluate(best)
    print("baseline", r0[0], r0[1], r0[2], flush=True)
    best_score, best_man = r0[0], r0[3]
    pool = mp.Pool(8)
    t0 = time.time()
    if mode == "coord":
        for rnd in range(iters):
            improved = False
            for k, (lo, hi) in KNOBS.items():
                cur = best.get(k)
                cands = []
                for v in range(lo, hi + 1):
                    if v == cur:
                        continue
                    p = dict(best); p[k] = v
                    cands.append(p)
                for p, res in pool.imap_unordered(_work, cands):
                    if res and res[0] < best_score:
                        best_score, best_man = res[0], res[3]
                        best = p
                        improved = True
                        print("  %-9s -> %-3s  score %d box %d ticks %.0f" %
                              (k, p[k], res[0], res[1], res[2]), flush=True)
                json.dump({"params": best, "score": best_score},
                          open(OUT + "/best.json", "w"), indent=1)
                open(OUT + "/best.man", "w").write(best_man)
            print("round %d done, best %d, %.0fs" % (rnd, best_score, time.time() - t0), flush=True)
            if not improved:
                break
    else:
        rng = random.Random(12345)
        keys = list(KNOBS)
        batch = []
        for i in range(iters):
            p = dict(best)
            for k in rng.sample(keys, rng.randint(2, 5)):
                lo, hi = KNOBS[k]
                p[k] = max(lo, min(hi, p.get(k, (lo + hi) // 2) + rng.choice([-3, -2, -1, 1, 2, 3])))
            batch.append(p)
            if len(batch) >= 400 or i == iters - 1:
                for p2, res in pool.imap_unordered(_work, batch):
                    if res and res[0] < best_score:
                        best_score, best_man = res[0], res[3]
                        best = p2
                        print("  rand score %d box %d ticks %.0f %s" %
                              (res[0], res[1], res[2], p2), flush=True)
                        json.dump({"params": best, "score": best_score},
                                  open(OUT + "/best.json", "w"), indent=1)
                        open(OUT + "/best.man", "w").write(best_man)
                batch = []
                print("  ...%d/%d  best %d  %.0fs" % (i + 1, iters, best_score, time.time() - t0), flush=True)
    print("BEST", best_score, best, flush=True)


if __name__ == "__main__":
    main()
