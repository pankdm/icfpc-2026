#!/usr/bin/env python3
"""Try to take ONE row out of the 79x80-stream build.  Prints footprints only."""
import os
import sys
import traceback

HL = "/Users/visenbaev/icfpc26/scratchpad/hist2/hl2"
sys.path.insert(0, HL)
os.chdir(HL)
import build_ring as BR


def attempt(tag, **kw):
    old = (BR.THRESHOLD, BR.ESC, BR.SMALL_FREE, BR.STOLEN)
    BR.THRESHOLD, BR.ESC = 23, 29
    BR.SMALL_FREE = [2, 4, 5, 6, 7, 8, 11, 12, 16, 17, 18, 19, 20, 21, 22]
    BR.STOLEN = (8, 18, 23)
    sel = lambda s: BR.choose_phrases_weighted(s, table_weight=1.25)
    try:
        symbols, ring, layout = BR.build_encoding(
            west_first=True, phrase_selector=sel, **kw)
        bands = BR.optimize_feeder(symbols, kw.get("W", 79))
        chunks = [c.value for b in bands for c in b.chunks]
        assert BR.verify(chunks, ring)
        p = BR.build_streaming_seven_once(kw.get("W", 79), ring, layout, bands)
        w, h, s = p.footprint()
        print("%-34s -> %dx%d score %d  rows=%d" % (tag, w, h, s, len(bands)))
        return p, s
    except Exception as e:
        msg = (str(e) or type(e).__name__).splitlines()[0]
        print("%-34s -> FAIL %s" % (tag, msg[:80]))
        return None, None
    finally:
        BR.THRESHOLD, BR.ESC, BR.SMALL_FREE, BR.STOLEN = old


if __name__ == "__main__":
    best = (None, 10 ** 9)
    for tag, kw in [
        ("baseline gb=3 ga=72", dict(group_b_rows=3, group_a_cap=72)),
        ("gb=2 ga=72", dict(group_b_rows=2, group_a_cap=72)),
        ("gb=3 ga=60", dict(group_b_rows=3, group_a_cap=60)),
        ("gb=3 ga=80", dict(group_b_rows=3, group_a_cap=80)),
        ("gb=4 ga=72", dict(group_b_rows=4, group_a_cap=72)),
        ("gb=2 ga=60", dict(group_b_rows=2, group_a_cap=60)),
        ("gb=2 ga=90", dict(group_b_rows=2, group_a_cap=90)),
    ]:
        p, s = attempt(tag, **kw)
        if s is not None and s < best[1]:
            best = (p, s)
            open("/tmp/hist2_best.man", "w").write(p.render())
    print("BEST", best[1])
