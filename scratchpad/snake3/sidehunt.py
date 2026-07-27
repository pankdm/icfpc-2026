"""Build-only hunt for a SMALLER BOX, then grade only the survivors.

The rung search grades every candidate (5 public + 53 stress = 58 engine runs)
even though the overwhelming majority never get the box below 73.  Building is
~1000x cheaper than grading, and the box is known from the build alone, so:

  phase 1  random/structured knob draws -> keep only footprints with side <= LIMIT
  phase 2  grade the survivors (public 5, then the 53-case QUICK stress gate)

Usage: python3 sidehunt.py <limit> <draws> <seed>
"""
import importlib.util, json, os, random, sys, tempfile, time
import multiprocessing as mp

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, REPO + "/tools")
OUT = REPO + "/scratchpad/snake3"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 72
DRAWS = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold8.py")
JOBS = int(os.environ.get("SNAKE_JOBS", "4"))
LM = REPO + "/interp/target/release/lm"

BASE = {'CW': 50, 'ST_OUT': 22, 'FEED_W': 25, 'LOOPR': 37, 'ST_X0': 19, 'D_REP': 29, 'HW_RET': 46, 'HW_TICK': 35, 'HW_SPAWN': 47, 'HW_DIR': 34, 'D_EAT': 30, 'D_NOEAT': 21, 'DRV_OUT': 49, 'DRVX': 4, 'CY0': 8, 'D_HY': 15, 'ST_IN': 23, 'D_HX': 15, 'IN_IN': 45, 'D_COLL': 10, 'CXL': 8}
LSHIFT = ['D_COLL', 'D_HY', 'D_HX', 'D_REP']
SHIFT = ['LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT', 'LOOPX', 'LOOPM', 'REPD', 'BD_OUT', 'BD_IN', 'IN_IN', 'WRAP_E']
JITTER = {'ST_OUT': 6, 'ST_IN': 6, 'ST_X0': 6, 'ST_W': 6, 'FEED_W': 12,
          'HW_RET': 8, 'HW_TICK': 8, 'HW_SPAWN': 9, 'HW_DIR': 8, 'D_EAT': 8,
          'D_NOEAT': 8, 'LOOPX': 6, 'LOOPM': 6, 'LOOPR': 6, 'DEC1': 9, 'DEC2': 9,
          'REPD': 8, 'BD_OUT': 6, 'BD_IN': 6, 'IN_IN': 6, 'DRV_OUT': 6,
          'WRAP_E': 6, 'DRVX': 3, 'CY0': 3, 'ST_X0': 6, 'ST_OUT': 4, 'ST_IN': 4, 'D_REP': 4, 'D_HX': 3, 'D_HY': 3,
          'D_COLL': 2}

HARDCAP = 200
_mod = None


def _init():
    global _mod
    if _mod is None:
        spec = importlib.util.spec_from_file_location("bsnake", BUILDER)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)


def _build(params):
    """Return (side, w, h, cap, params) or None -- BUILD ONLY, no grading."""
    _init()
    try:
        prog, cap, nrows = _mod.fit(**params)
    except Exception:
        return None
    w, h, box = prog.footprint()
    s = max(w, h)
    if s > HARDCAP:
        return None
    return (s, w, h, cap, params)


def draw(rng):
    p = dict(BASE)
    cxl = rng.randint(max(0, BASE['CXL'] - 6), BASE['CXL'] + 8)
    d0 = cxl - BASE['CXL']
    for k in LSHIFT:
        if k in p:
            p[k] += d0
    p['CXL'] = cxl
    d = rng.randint(-2, 2)
    if d:
        p['CW'] += d
        for k in SHIFT:
            if k in p:
                p[k] += d
    for k in rng.sample(list(JITTER), rng.randint(1, 6)):
        if k in p:
            p[k] += rng.randint(-JITTER[k], JITTER[k])
    return p


def main():
    rng = random.Random(SEED)
    pool = mp.Pool(JOBS)
    t0 = time.time()
    hits = []
    import collections
    hist = collections.Counter()
    batch = [draw(rng) for _ in range(DRAWS)]
    for res in pool.imap_unordered(_build, batch, chunksize=32):
        if res:
            hist[res[0]] += 1
            if res[0] <= LIMIT:
                hits.append(res)
    print("phase1: %d/%d builds with side <= %d in %.0fs"
          % (len(hits), DRAWS, LIMIT, time.time() - t0), flush=True)
    print("side histogram:", sorted(hist.items())[:12], flush=True)
    json.dump([{"side": h[0], "w": h[1], "h": h[2], "cap": h[3], "params": h[4]}
               for h in sorted(hits, key=lambda h: h[:4])], open(OUT + "/side%d.json" % LIMIT, "w"),
              indent=1)


if __name__ == "__main__":
    main()
