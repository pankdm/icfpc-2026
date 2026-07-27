"""Ladder search: drive the BOX SIDE down, ticks as the tiebreak.

The plain score objective (box * ticks) cannot walk the ladder, because the box
is max(w,h)^2 and the design sits balanced at w = h = 73: any single knob that
takes a column off the width puts a row on the height, so every intermediate
step scores worse and coordinate descent never leaves the plateau.  This search
orders candidates lexicographically by (side, ticks) instead, so it accepts a
tick regression that buys a column and only then squeezes the ticks back.

`bestscore.json` is kept in parallel: the lowest box*ticks ever seen, which is
what actually ships.

Every candidate must still pass the 5 public cases AND the 53-case QUICK stress
subset (all four wall deaths, both corners, grow-50, self-hit, long-lap).

Usage: python3 rung.py <rounds> <seed> [statefile]
"""
import importlib.util, json, os, random, sys, tempfile, time
import multiprocessing as mp

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, REPO + "/tools")
OUT = REPO + "/scratchpad/snake3"
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 3
STATE = sys.argv[3] if len(sys.argv) > 3 else OUT + "/rung.json"
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold6.py")
MANOUT = STATE.replace(".json", ".man")
BESTF = STATE.replace(".json", "-best.json")
BESTMAN = STATE.replace(".json", "-best.man")
JOBS = int(os.environ.get("SNAKE_JOBS", "6"))

LSHIFT = {'D_COLL', 'D_HY', 'D_HX', 'D_REP'}
SHIFT = {'LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT', 'LOOPX', 'LOOPM', 'REPD', 'BD_OUT', 'BD_IN', 'IN_IN', 'WRAP_E'}
SPREAD = {'ST_OUT': 4, 'ST_IN': 4, 'ST_X0': 4, 'ST_W': 4, 'FEED_W': 5,
          'D_REP': 4, 'D_COLL': 2, 'D_HX': 3, 'D_HY': 3,
          'HW_RET': 4, 'HW_TICK': 4, 'HW_SPAWN': 4, 'HW_DIR': 4,
          'D_EAT': 4, 'D_NOEAT': 4, 'LOOPX': 4, 'LOOPM': 4, 'LOOPR': 4,
          'DEC1': 5, 'DEC2': 5, 'REPD': 4, 'BD_OUT': 4, 'BD_IN': 4, 'IN_IN': 4,
          'DRV_OUT': 4, 'WRAP_E': 4, 'DRVX': 2, 'DISX': 2, 'CY0': 2, 'CXL': 2}
RANGE = {'ST_OUT': (14, 32), 'ST_IN': (14, 34), 'ST_X0': (8, 28), 'ST_W': (3, 18),
         'FEED_W': (14, 36), 'HW_RET': (34, 58), 'HW_TICK': (26, 50),
         'HW_SPAWN': (28, 54), 'HW_DIR': (22, 46), 'D_EAT': (18, 42),
         'D_NOEAT': (20, 44), 'LOOPX': (26, 50), 'LOOPM': (25, 49),
         'LOOPR': (24, 48), 'DEC1': (8, 32), 'DEC2': (12, 36), 'REPD': (28, 52),
         'BD_OUT': (22, 46), 'BD_IN': (28, 52), 'IN_IN': (34, 58),
         'DRV_OUT': (36, 60), 'WRAP_E': (36, 60), 'DRVX': (1, 7),
         'DISX': (8, 18), 'CY0': (5, 12), 'CXL': (0, 16)}

PIN = os.environ.get("SNAKE_PIN_CXL")
if PIN is not None:
    # Pin the left inset: with CXL free, (side, ticks) descent always walks back
    # to CXL=0, which is a coordinate-descent fixpoint.  Pinning it makes the
    # search hunt for the ROW cuts that pay for the columns already taken.
    RANGE.pop('CXL', None)
    SPREAD.pop('CXL', None)

_mod = _gf = _QUICK = None
LM = REPO + "/interp/target/release/lm"


def _init():
    global _mod, _gf, _QUICK
    if _mod is None:
        spec = importlib.util.spec_from_file_location("bsnake", BUILDER)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        import grade_fast
        _gf = grade_fast
        st = json.load(open(REPO + "/scratchpad/snake2/stress.json"))
        must = {"grow-50", "grow-45-then-selfhit", "grow-40", "long-lap",
                "grow-30-then-selfhit"}
        _QUICK = [c for c in st if c["nrounds"] <= 14 or c["name"] in must]


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


def _work(params):
    _init()
    fd, path = tempfile.mkstemp(suffix=".man", dir="/tmp")
    os.close(fd)
    try:
        try:
            prog, cap, nrows = _mod.fit(save_to=path, **params)
        except Exception:
            return None
        w, h, box = prog.footprint()
        r = _gf.grade("snake", path, cap=60000, jobs=1)
        if r.get("passed") != r.get("total") or not r.get("total"):
            return None
        if _run_cases(path, _QUICK) is not None:
            return None
        return (max(w, h), r["avgTicks"], box, r["score"], cap, params,
                open(path).read())
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _mk(base, k, v):
    p = dict(base)
    if k == 'CXL':
        d = v - p.get('CXL', 0)
        for kk in LSHIFT:
            if kk in p:
                p[kk] += d
    p[k] = v
    return p


def main():
    st = json.load(open(STATE))
    best = st["params"]
    key = (st["side"], st["ticks"])
    try:
        bscore = json.load(open(BESTF))["score"]
    except Exception:
        bscore = float("inf")
    rng = random.Random(SEED)
    pool = mp.Pool(JOBS)
    t0 = time.time()

    def offer(res):
        nonlocal key, best, bscore
        if not res:
            return False
        side, ticks, box, score, cap, params, man = res
        hit = False
        if score < bscore:
            bscore = score
            json.dump({"params": params, "score": score, "box": box,
                       "ticks": ticks, "cap": cap, "side": side},
                      open(BESTF, "w"), indent=1)
            open(BESTMAN, "w").write(man)
            print("  ** BEST score %d  side %d  ticks %.0f  cap %d" %
                  (score, side, ticks, cap), flush=True)
            hit = True
        if (side, ticks) < key:
            key, best = (side, ticks), params
            json.dump({"params": params, "score": score, "box": box,
                       "ticks": ticks, "cap": cap, "side": side},
                      open(STATE, "w"), indent=1)
            open(MANOUT, "w").write(man)
            print("  rung side %d ticks %.0f score %d cap %d" %
                  (side, ticks, score, cap), flush=True)
            hit = True
        return hit

    for rnd in range(ROUNDS):
        improved = False
        for k, (lo, hi) in RANGE.items():
            cands = [_mk(best, k, v) for v in range(lo, hi + 1) if v != best.get(k)]
            for res in pool.imap_unordered(_work, cands):
                improved |= offer(res)
        for wave in range(10):
            batch = []
            for _ in range(400):
                p = dict(best)
                if rng.random() < 0.3:
                    d = rng.choice([-2, -1, 1, 2])
                    p['CW'] += d
                    for kk in SHIFT:
                        if kk in p:
                            p[kk] += d
                for kk in rng.sample(list(SPREAD), rng.randint(1, 4)):
                    if kk in p:
                        if kk == 'CXL':
                            p = _mk(p, 'CXL', max(0, p['CXL'] +
                                                  rng.randint(-SPREAD[kk], SPREAD[kk])))
                        else:
                            p[kk] += rng.randint(-SPREAD[kk], SPREAD[kk])
                batch.append(p)
            for res in pool.imap_unordered(_work, batch):
                improved |= offer(res)
            print("  wave %d.%d side %d ticks %.0f best %d %.0fs" %
                  (rnd, wave, key[0], key[1], bscore, time.time() - t0), flush=True)
        if not improved:
            print("converged", flush=True)
            break
    print("RUNG", key, "BESTSCORE", bscore, json.dumps(best), flush=True)


if __name__ == "__main__":
    main()
