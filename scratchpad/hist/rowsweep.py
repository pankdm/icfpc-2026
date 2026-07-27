#!/usr/bin/env python3
"""79x80-stream is width 79, height 80: ONE feeder row from 79x79 = 6241.

Sweep the encoder knobs that do not touch the decoder (phrase table weight,
DISP threshold, group caps) and report the feeder row count only -- the grid
build is skipped, so a candidate costs seconds instead of minutes.
"""
import itertools, sys, traceback

WT = "/Users/visenbaev/icfpc26/.claude/worktrees/hist-main"
sys.path.insert(0, WT + "/solutions/history-lesson")
sys.path.insert(0, WT + "/tools")
import build_ring as BR

BASE = dict(THRESHOLD=23, ESC=29,
            SMALL_FREE=[2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22],
            STOLEN=(8, 18, 23))


def feeder_rows(threshold, weight, ga_cap, gb_rows, small_free, stolen, W=79):
    old = (BR.THRESHOLD, BR.ESC, BR.SMALL_FREE, BR.STOLEN)
    BR.THRESHOLD, BR.ESC = threshold, 29
    BR.SMALL_FREE, BR.STOLEN = small_free, stolen
    try:
        sel = lambda s: BR.choose_phrases_weighted(s, table_weight=weight)
        symbols, ring, layout = BR.build_encoding(
            west_first=True, phrase_selector=sel,
            group_b_rows=gb_rows, group_a_cap=ga_cap)
        bands = BR.optimize_feeder(symbols, W)
        chunks = [c.value for b in bands for c in b.chunks]
        if not BR.verify(chunks, ring):
            return None, len(symbols), "verify-fail"
        rows = sum(b.rows for b in bands)
        return rows, len(symbols), None
    except Exception as e:
        return None, 0, f"{type(e).__name__}:{str(e)[:40]}"
    finally:
        BR.THRESHOLD, BR.ESC, BR.SMALL_FREE, BR.STOLEN = old


if __name__ == "__main__":
    r, n, err = feeder_rows(23, 1.25, 72, 3, BASE["SMALL_FREE"], BASE["STOLEN"])
    print(f"baseline (79x80): feeder_rows={r} symbols={n} err={err}", flush=True)
    best = r
    for weight in (1.0, 1.1, 1.15, 1.2, 1.25, 1.3, 1.4, 1.5, 1.75, 2.0):
        for ga in (70, 71, 72, 73):
            rr, nn, e = feeder_rows(23, weight, ga, 3,
                                    BASE["SMALL_FREE"], BASE["STOLEN"])
            flag = "  <== BETTER" if rr and best and rr < best else ""
            print(f"  w={weight:<5} ga={ga} rows={rr} syms={nn} "
                  f"{e or ''}{flag}", flush=True)
