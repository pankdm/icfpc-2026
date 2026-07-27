"""Pin CW to a target and hunt for ANY passing build, then descend.
Usage: python3 pin.py <CW> <iters> [seed] [center.json] [out.json]
"""
import json, random, sys, time
import multiprocessing as mp
sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/snake2")
import search4 as S

CWT = int(sys.argv[1])
ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 3
CENTER_F = sys.argv[4] if len(sys.argv) > 4 else "/Users/visenbaev/icfpc26/scratchpad/snake2/win.json"
OUTF = sys.argv[5] if len(sys.argv) > 5 else "/Users/visenbaev/icfpc26/scratchpad/snake2/pin%d.json" % CWT


def main():
    st = json.load(open(CENTER_F))
    c = dict(st["params"])
    d = CWT - c["CW"]
    c["CW"] = CWT
    for k in S.SHIFT:
        if k in c:
            c[k] += d
    rng = random.Random(SEED)
    pool = mp.Pool(8)
    best, best_score, t0, done = None, float("inf"), time.time(), 0
    r = S._work(c)
    if r:
        best, best_score = r[4], r[0]
        json.dump({"params": best, "score": r[0], "box": r[1], "ticks": r[2], "cap": r[3]},
                  open(OUTF, "w"), indent=1)
        open(OUTF.replace(".json", ".man"), "w").write(r[5])
        print("pinned centre passes:", r[0], r[1], r[2], flush=True)
    while done < ITERS:
        batch = []
        for _ in range(500):
            p = dict(best) if best else dict(c)
            for kk in rng.sample(list(S.SPREAD), rng.randint(1, 5)):
                if kk in p:
                    p[kk] += rng.randint(-S.SPREAD[kk], S.SPREAD[kk])
            p["CW"] = CWT
            batch.append(p)
        for res in pool.imap_unordered(S._work, batch):
            if res and res[0] < best_score:
                best, best_score = res[4], res[0]
                json.dump({"params": best, "score": res[0], "box": res[1],
                           "ticks": res[2], "cap": res[3]}, open(OUTF, "w"), indent=1)
                open(OUTF.replace(".json", ".man"), "w").write(res[5])
                print("  score %d box %d ticks %.0f cap %d" % (res[0], res[1], res[2], res[3]), flush=True)
        done += 500
        if done % 5000 == 0:
            print("  %d/%d %.0fs best %s" % (done, ITERS, time.time() - t0, best_score), flush=True)
    print("DONE", best_score, flush=True)


if __name__ == "__main__":
    main()
