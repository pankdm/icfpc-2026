"""Iterated search: coordinate descent + random multi-knob jumps, re-centering
on every improvement.  Reads/writes scratchpad/snake2/win.json + win.man.
Usage: python3 search4.py <rounds> <seed> [statefile]
"""
import importlib.util, json, os, random, sys, tempfile, time
import multiprocessing as mp

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, REPO + "/tools")
OUT = "/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/snake4"
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 11
STATE = sys.argv[3] if len(sys.argv) > 3 else OUT + "/win.json"
MANOUT = STATE.replace(".json", ".man")

SHIFT = {'LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT', 'LOOPX', 'LOOPM', 'REPD', 'BD_OUT', 'BD_IN', 'IN_IN', 'WRAP_E'}
SPREAD = {'ST_OUT': 4, 'ST_IN': 4, 'ST_X0': 4, 'ST_W': 4, 'FEED_W': 5,
          'D_REP': 4, 'D_COLL': 2, 'D_HX': 3, 'D_HY': 3,
          'HW_RET': 4, 'HW_TICK': 4, 'HW_SPAWN': 4, 'HW_DIR': 4,
          'D_EAT': 4, 'D_NOEAT': 4, 'LOOPX': 4, 'LOOPM': 4, 'LOOPR': 4,
          'DEC1': 5, 'DEC2': 5, 'REPD': 4, 'BD_OUT': 4, 'BD_IN': 4, 'IN_IN': 4,
          'DRV_OUT': 4, 'WRAP_E': 4, 'DRVX': 2, 'DISX': 2, 'CY0': 2,
          'FEED_T': 4, 'FEED_W2': 4, 'RET_E': 4, 'BD_X0': 4, 'BD_W': 3,
          'FEED_E': 4}
RANGE = {'ST_OUT': (14, 32), 'ST_IN': (14, 34), 'ST_X0': (8, 28), 'ST_W': (3, 18),
         'FEED_W': (14, 36), 'D_REP': (6, 22), 'D_COLL': (1, 8), 'D_HX': (3, 14),
         'D_HY': (2, 12), 'HW_RET': (34, 58), 'HW_TICK': (26, 50),
         'HW_SPAWN': (28, 54), 'HW_DIR': (22, 46), 'D_EAT': (18, 42),
         'D_NOEAT': (20, 44), 'LOOPX': (26, 50), 'LOOPM': (25, 49),
         'LOOPR': (24, 48), 'DEC1': (8, 32), 'DEC2': (12, 36), 'REPD': (28, 52),
         'BD_OUT': (22, 46), 'BD_IN': (28, 52), 'IN_IN': (34, 58),
         'DRV_OUT': (36, 60), 'WRAP_E': (36, 60), 'DRVX': (1, 7),
         'DISX': (8, 18), 'CY0': (5, 12), 'FEED_T': (18, 46),
         'FEED_W2': (14, 40), 'RET_E': (32, 58), 'BD_X0': (16, 42),
         'BD_W': (5, 20), 'FEED_E': (24, 50)}

_mod = None
_gf = None
_QUICK = None
_FULL = None
LM = REPO + "/interp/target/release/lm"
QUICK_ROUNDS = 14        # cases up to this many rounds gate every candidate


def _init():
    global _mod, _gf, _QUICK, _FULL
    if _mod is None:
        spec = importlib.util.spec_from_file_location(
            "bf2", os.environ.get("SNAKE_BUILDER",
                                  REPO + "/solutions/snake/build_fold7.py"))
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        _mod.MIN_CAP = 51
        import grade_fast
        _gf = grade_fast
        st = json.load(open(OUT + "/stress.json"))
        # capacity + long-game shapes must gate every candidate too, or a build
        # with too small a body ring sails through the short cases.
        must = {"grow-50", "grow-45-then-selfhit", "grow-40", "long-lap",
                "grow-30-then-selfhit"}
        _QUICK = [c for c in st if c["nrounds"] <= QUICK_ROUNDS or c["name"] in must]
        _FULL = [c for c in st if not (c["nrounds"] <= QUICK_ROUNDS or c["name"] in must)]


def _run_cases(path, cases, cap=60000):
    import subprocess
    for c in cases:
        p = subprocess.run([LM, "--grade", path, "--input=" + c["input"],
                            "--expected=" + c["expected"], "--cap=%d" % cap,
                            "--frames=" + c["frames"]],
                           capture_output=True, text=True, timeout=300)
        try:
            v = json.loads((p.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return c["name"]
        if v.get("status") != "pass":
            return c["name"]
    return None


def _work(params, full=False):
    _init()
    fd, path = tempfile.mkstemp(suffix=".man", dir="/tmp")
    os.close(fd)
    try:
        try:
            prog, cap, nrows = _mod.fit(save_to=path, **params)
        except Exception:
            return None
        w, h, box = prog.footprint()
        if box > BOXMAX:
            return None
        r = _gf.grade("snake", path, cap=60000, jobs=1)
        if r.get("passed") != r.get("total") or not r.get("total"):
            return None
        if _run_cases(path, _QUICK) is not None:
            return None
        if full and _run_cases(path, _FULL) is not None:
            return None
        return (r["score"], box, r["avgTicks"], cap, params, open(path).read())
    finally:
        try: os.unlink(path)
        except OSError: pass


BOXMAX = 100000


def save(best, score, box, ticks, cap, man):
    json.dump({"params": best, "score": score, "box": box, "ticks": ticks,
               "cap": cap}, open(STATE, "w"), indent=1)
    open(MANOUT, "w").write(man)


def main():
    st = json.load(open(STATE))
    best, best_score = st["params"], st["score"]
    rng = random.Random(SEED)
    pool = mp.Pool(8)
    t0 = time.time()
    for rnd in range(ROUNDS):
        improved = False
        # --- coordinate descent ---
        for k, (lo, hi) in RANGE.items():
            cands = [dict(best, **{k: v}) for v in range(lo, hi + 1) if v != best.get(k)]
            for res in pool.imap_unordered(_work, cands):
                if res and res[0] < best_score:
                    best_score, best = res[0], res[4]
                    improved = True
                    save(best, res[0], res[1], res[2], res[3], res[5])
                    print("  cd %-9s -> %-3s score %d box %d ticks %.0f" %
                          (k, res[4][k], res[0], res[1], res[2]), flush=True)
        # --- random multi-knob ---
        for wave in range(12):
            batch = []
            for _ in range(500):
                p = dict(best)
                if rng.random() < 0.3:
                    d = rng.choice([-2, -1, 1, 2])
                    p['CW'] += d
                    for kk in SHIFT:
                        if kk in p:
                            p[kk] += d
                for kk in rng.sample(list(SPREAD), rng.randint(1, 4)):
                    if kk in p:
                        p[kk] += rng.randint(-SPREAD[kk], SPREAD[kk])
                batch.append(p)
            for res in pool.imap_unordered(_work, batch):
                if res and res[0] < best_score:
                    best_score, best = res[0], res[4]
                    improved = True
                    save(best, res[0], res[1], res[2], res[3], res[5])
                    print("  rj score %d box %d ticks %.0f cap %d" %
                          (res[0], res[1], res[2], res[3]), flush=True)
        print("round %d best %d %.0fs" % (rnd, best_score, time.time() - t0), flush=True)
        if not improved:
            print("converged", flush=True)
            break
    print("BEST", best_score, json.dumps(best), flush=True)


if __name__ == "__main__":
    main()
