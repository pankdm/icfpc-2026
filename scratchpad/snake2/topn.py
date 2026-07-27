"""Sample gated candidates near the current best and keep the top N distinct
grids, so each can be run through tools/shrink.py (the shrink win is a property
of the GRID, not of the pre-shrink score).
Usage: python3 topn.py <n_samples> <n_keep> <state.json> <outdir>
"""
import json, os, random, sys, time
import multiprocessing as mp
sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/snake2")
import search4 as S

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
KEEP = int(sys.argv[2]) if len(sys.argv) > 2 else 8
STATE = sys.argv[3] if len(sys.argv) > 3 else "/Users/visenbaev/icfpc26/scratchpad/snake2/g8.json"
OUTDIR = sys.argv[4] if len(sys.argv) > 4 else "/Users/visenbaev/icfpc26/scratchpad/snake2/top"


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    st = json.load(open(STATE))
    base = st["params"]
    rng = random.Random(4242)
    pool = mp.Pool(8)
    seen = {}
    t0 = time.time()
    done = 0
    while done < N:
        batch = []
        for _ in range(400):
            p = dict(base)
            for k in rng.sample(list(S.SPREAD), rng.randint(1, 3)):
                if k in p:
                    p[k] += rng.randint(-S.SPREAD[k], S.SPREAD[k])
            batch.append(p)
        for res in pool.imap_unordered(S._work, batch):
            if res:
                score, box, ticks, cap, params, man = res
                if man not in seen or seen[man][0] > score:
                    seen[man] = (score, box, ticks, params)
        done += 400
        print("  %d/%d %.0fs distinct %d" % (done, N, time.time() - t0, len(seen)), flush=True)
    best = sorted(seen.items(), key=lambda kv: kv[1][0])[:KEEP]
    for i, (man, (score, box, ticks, params)) in enumerate(best):
        open("%s/c%d.man" % (OUTDIR, i), "w").write(man)
        json.dump({"params": params, "score": score, "box": box, "ticks": ticks},
                  open("%s/c%d.json" % (OUTDIR, i), "w"), indent=1)
        print("c%d score %d box %d ticks %.0f" % (i, score, box, ticks), flush=True)


if __name__ == "__main__":
    main()
