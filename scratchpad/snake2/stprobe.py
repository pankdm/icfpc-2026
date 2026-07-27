"""Sweep CW x ST_X0 x FEED_W with the full gate.  ST_X0/ST_OUT/ST_IN are tied by
an assert so they must move together -- single-knob coordinate descent cannot
reach this region at all."""
import json, sys, itertools
import multiprocessing as mp
sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/snake2")
import search4 as S

BASE = json.load(open("/Users/visenbaev/icfpc26/scratchpad/snake2/w46_15_22.json"))["params"]
SHIFT = ['LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT', 'DRV_OUT']


def gen():
    for cw in range(42, 49):
        for st in range(8, 21):
            for gap in (3, 4):
                for fw in range(st + 4, st + 12):
                    kw = dict(BASE)
                    d = cw - BASE["CW"]
                    kw["CW"] = cw
                    for k in SHIFT:
                        kw[k] += d
                    kw["ST_X0"] = st
                    kw["ST_OUT"] = st + gap
                    kw["ST_IN"] = st + gap + 1
                    kw["FEED_W"] = fw
                    yield kw


def main():
    pool = mp.Pool(8)
    out = []
    for res in pool.imap_unordered(S._work, list(gen()), chunksize=4):
        if res:
            out.append(res)
            print("score %d box %d ticks %.0f cap %d  CW=%d ST_X0=%d FEED_W=%d" %
                  (res[0], res[1], res[2], res[3], res[4]["CW"], res[4]["ST_X0"],
                   res[4]["FEED_W"]), flush=True)
    out.sort(key=lambda r: (r[1], r[0]))
    for i, r in enumerate(out[:10]):
        open("/Users/visenbaev/icfpc26/scratchpad/snake2/top/s%d.man" % i, "w").write(r[5])
        json.dump({"params": r[4], "score": r[0], "box": r[1], "ticks": r[2], "cap": r[3]},
                  open("/Users/visenbaev/icfpc26/scratchpad/snake2/top/s%d.json" % i, "w"), indent=1)
        print("s%d box %d score %d" % (i, r[1], r[0]), flush=True)


if __name__ == "__main__":
    main()
