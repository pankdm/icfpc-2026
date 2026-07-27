"""Find a VALID build at a forced CW (narrower controller => narrower box).
Random-restart over the knobs that CW disturbs, gated on build+public+QUICK."""
import json, os, random, sys, tempfile
import multiprocessing as mp
sys.path.insert(0, "/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/snake4")
import search4 as S

CW = int(sys.argv[1])
N = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 7
BASE = json.load(open(S.OUT + "/win.json"))["params"]
OUTF = S.OUT + "/narrow%d.json" % CW

SHIFT = ['LOOPR','HW_RET','HW_TICK','HW_SPAWN','HW_DIR','D_EAT','D_NOEAT','DRV_OUT',
         'LOOPX','LOOPM','REPD','BD_OUT','BD_IN','IN_IN','WRAP_E']
JIT = {'ST_OUT':3,'ST_IN':3,'ST_X0':3,'ST_W':3,'FEED_W':5,'D_REP':4,'D_COLL':2,
       'D_HX':3,'D_HY':3,'HW_RET':3,'HW_TICK':3,'HW_SPAWN':4,'HW_DIR':3,'D_EAT':3,
       'D_NOEAT':3,'DRV_OUT':3,'DRVX':2,'CY0':2,'FEED_T':4,'FEED_W2':4,'RET_E':4,
       'BD_X0':4,'BD_W':3,'FEED_E':4,'IN_IN':4,'LOOPX':3,'LOOPM':3,'LOOPR':3,
       'DEC1':4,'DEC2':4,'REPD':3,'BD_OUT':3,'WRAP_E':3,'DISX':2}

def gen(seed):
    rng = random.Random(seed)
    p = dict(BASE)
    d = CW - p['CW']
    p['CW'] = CW
    for k in SHIFT:
        if k in p: p[k] += d
    for k in rng.sample(list(JIT), rng.randint(1, 5)):
        if k in p: p[k] += rng.randint(-JIT[k], JIT[k])
        else: p[k] = None
    return {k: v for k, v in p.items() if v is not None}

if __name__ == "__main__":
    pool = mp.Pool(6)
    cands = [gen(SEED*1000003 + i) for i in range(N)]
    best = None
    for res in pool.imap_unordered(S._work, cands):
        if res and (best is None or res[0] < best[0]):
            best = res
            json.dump({"params": res[4], "score": res[0], "box": res[1],
                       "ticks": res[2], "cap": res[3]}, open(OUTF, "w"), indent=1)
            open(OUTF.replace(".json", ".man"), "w").write(res[5])
            print("CW=%d score %d box %d ticks %.0f cap %d" % (CW, res[0], res[1], res[2], res[3]), flush=True)
    print("done", CW, best[:4] if best else None)
