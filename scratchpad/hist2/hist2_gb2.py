#!/usr/bin/env python3
"""One-shot: try group_b_rows=2 (P1 one row shorter) on the 79x80-stream build."""
import os, sys
HL = "/Users/visenbaev/icfpc26/scratchpad/hist2/hl2"
sys.path.insert(0, HL); os.chdir(HL)
import build_ring as BR
gb = int(sys.argv[1]); ga = int(sys.argv[2]); W = int(sys.argv[3])
BR.THRESHOLD, BR.ESC = 23, 29
BR.SMALL_FREE = [2,4,5,6,7,8,11,12,16,17,18,19,20,21,22]
BR.STOLEN = (8,18,23)
sel = lambda s: BR.choose_phrases_weighted(s, table_weight=1.25)
symbols, ring, layout = BR.build_encoding(west_first=True, phrase_selector=sel,
                                          group_b_rows=gb, group_a_cap=ga)
bands = BR.optimize_feeder(symbols, W)
chunks = [c.value for b in bands for c in b.chunks]
assert BR.verify(chunks, ring)
p = BR.build_streaming_seven_once(W, ring, layout, bands)
w,h,s = p.footprint()
print("gb=%d ga=%d W=%d -> %dx%d score %d" % (gb,ga,W,w,h,s), flush=True)
if s < 6400:
    open("/Users/visenbaev/icfpc26/scratchpad/hist2/hist2_%dx%d.man"%(w,h),"w").write(p.render())
    print("WROTE", flush=True)
