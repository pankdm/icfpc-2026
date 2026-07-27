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
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold6.py")
JOBS = int(os.environ.get("SNAKE_JOBS", "4"))
LM = REPO + "/interp/target/release/lm"

BASE = dict(CW=52, CXL=0, ST_OUT=23, ST_IN=24, ST_X0=19, ST_W=9, FEED_W=28,
            LOOPR=39, LOOPX=41, LOOPM=40, D_REP=12, D_COLL=2, D_HY=5, D_HX=8,
            HW_RET=48, HW_TICK=37, HW_SPAWN=31, HW_DIR=36, D_EAT=32, D_NOEAT=23,
            DRV_OUT=51, DRVX=4, DEC1=20, DEC2=25, REPD=44, BD_OUT=36, BD_IN=42,
            IN_IN=48, WRAP_E=50, CY0=8)
LSHIFT = ['D_COLL', 'D_HY', 'D_HX', 'D_REP']
SHIFT = ['LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT', 'LOOPX', 'LOOPM', 'REPD', 'BD_OUT', 'BD_IN', 'IN_IN', 'WRAP_E']
JITTER = {'ST_OUT': 3, 'ST_IN': 3, 'ST_X0': 3, 'ST_W': 3, 'FEED_W': 4,
          'HW_RET': 4, 'HW_TICK': 4, 'HW_SPAWN': 5, 'HW_DIR': 4, 'D_EAT': 4,
          'D_NOEAT': 4, 'LOOPX': 3, 'LOOPM': 3, 'LOOPR': 3, 'DEC1': 5, 'DEC2': 5,
          'REPD': 4, 'BD_OUT': 3, 'BD_IN': 3, 'IN_IN': 3, 'DRV_OUT': 3,
          'WRAP_E': 3, 'DRVX': 2, 'CY0': 1}

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
    cxl = rng.randint(0, 8)
    for k in LSHIFT:
        p[k] += cxl
    p['CXL'] = cxl
    d = rng.randint(-2, 2)
    if d:
        p['CW'] += d
        for k in SHIFT:
            p[k] += d
    for k in rng.sample(list(JITTER), rng.randint(1, 6)):
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
               for h in sorted(hits)], open(OUT + "/side%d.json" % LIMIT, "w"),
              indent=1)


if __name__ == "__main__":
    main()
