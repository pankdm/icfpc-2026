"""Build-only random sweep for a SMALLER BOX, then grade the survivors.

Build is ~60ms and grading ~200ms, and most random points do not even build,
so filter on footprint first and grade only candidates whose box beats the
threshold.  Writes every graded winner to scratchpad/snake2/win-<score>.man.
Usage: python3 search3.py <iters> <box_threshold> [seed]
"""
import importlib.util, json, os, random, sys, tempfile, time
import multiprocessing as mp

REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
OUT = "/Users/visenbaev/icfpc26/scratchpad/snake2"

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
BOXMAX = int(sys.argv[2]) if len(sys.argv) > 2 else 5329
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1

# every knob explicit, at the CW=51 optimum found by search2.py
CENTER = {'CW': 51, 'CY0': 8, 'ST_OUT': 23, 'ST_IN': 24, 'ST_X0': 19, 'ST_W': 9,
          'FEED_W': 27, 'D_REP': 11, 'D_COLL': 3, 'D_HX': 9, 'D_HY': 4,
          'HW_RET': 47, 'HW_TICK': 38, 'HW_SPAWN': 48, 'HW_DIR': 35,
          'D_EAT': 31, 'D_NOEAT': 32, 'LOOPX': 40, 'LOOPM': 39, 'LOOPR': 38,
          'DEC1': 20, 'DEC2': 25, 'REPD': 43, 'BD_OUT': 35, 'BD_IN': 41,
          'IN_IN': 47, 'DRV_OUT': 50, 'WRAP_E': 49, 'DRVX': 4, 'DISX': 14}
SHIFT = {'LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT', 'LOOPX', 'LOOPM', 'REPD', 'BD_OUT', 'BD_IN', 'IN_IN', 'WRAP_E'}
SPREAD = {  # knob -> max |delta| from centre
    'ST_OUT': 4, 'ST_IN': 4, 'ST_X0': 4, 'ST_W': 4, 'FEED_W': 5,
    'D_REP': 4, 'D_COLL': 2, 'D_HX': 3, 'D_HY': 3,
    'HW_RET': 4, 'HW_TICK': 4, 'HW_SPAWN': 4, 'HW_DIR': 4,
    'D_EAT': 4, 'D_NOEAT': 4, 'LOOPX': 4, 'LOOPM': 4, 'LOOPR': 4,
    'DEC1': 5, 'DEC2': 5, 'REPD': 4, 'BD_OUT': 4, 'BD_IN': 4, 'IN_IN': 4,
    'DRV_OUT': 4, 'WRAP_E': 4, 'DRVX': 2, 'DISX': 2, 'CY0': 2,
}
DEFAULTS = {}

_mod = None
_gf = None


def _init():
    global _mod, _gf
    if _mod is None:
        spec = importlib.util.spec_from_file_location(
            "bf2", REPO + "/solutions/snake/build_fold2_tuned.py")
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        _mod.MIN_CAP = 51
        import grade_fast
        _gf = grade_fast


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
        if box > BOXMAX:
            return None
        r = _gf.grade("snake", path, cap=60000, jobs=1)
        if r.get("passed") != r.get("total") or not r.get("total"):
            return ("BOXONLY", box, w, h, cap, params)
        return ("PASS", r["score"], box, r["avgTicks"], cap, params, open(path).read())
    finally:
        try: os.unlink(path)
        except OSError: pass


def gen(rng, center=None):
    center = center or CENTER
    p = dict(center)
    if rng.random() < 0.35:
        d = rng.choice([-3, -2, -1, 1])
        p['CW'] = center['CW'] + d
        for k in SHIFT:
            if k in p:
                p[k] += d
    for k in rng.sample(list(SPREAD), rng.randint(1, 4)):
        if k in p:
            p[k] += rng.randint(-SPREAD[k], SPREAD[k])
    return p


def main():
    rng = random.Random(SEED)
    pool = mp.Pool(8)
    best_score = float("inf")
    boxonly = {}
    t0 = time.time()
    done = 0
    while done < ITERS:
        batch = [gen(rng) for _ in range(500)]
        for res in pool.imap_unordered(_work, batch):
            if not res:
                continue
            if res[0] == "BOXONLY":
                boxonly[res[1]] = boxonly.get(res[1], 0) + 1
            else:
                _, score, box, ticks, cap, params, man = res
                if score < best_score:
                    best_score = score
                    open(OUT + "/win.man", "w").write(man)
                    json.dump({"params": params, "score": score, "box": box,
                               "ticks": ticks, "cap": cap},
                              open(OUT + "/win.json", "w"), indent=1)
                    print("PASS score %d box %d ticks %.0f cap %d" % (score, box, ticks, cap), flush=True)
        done += 500
        print("  %d/%d %.0fs best %s  boxonly(failing) %s" %
              (done, ITERS, time.time() - t0, best_score, sorted(boxonly.items())[:5]), flush=True)


if __name__ == "__main__":
    main()
