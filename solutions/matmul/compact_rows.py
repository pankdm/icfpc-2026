"""Tier 1 reproducible compaction: from matmul-run.man (the banked RANK-1 floor),
remove the fully-blank ('|'-only) interior rows of the CTRL room. These carry no
glyph and no pipe crosses them, so removing them shrinks room height (box lever:
box = max(w,h)^2, height-bound) AND shortens the CTRL man's vertical glides
(avgTicks lever) with byte-identical executed behaviour. Writes matmul-opt.man.

CTRL room spans .man rows 44..116 (0-based top wall=44, bottom wall=116). Interior
blank rows are the ones with characters == {'|'} (left/right walls, blank between).
Ring-capacity risers (rows 15..29) are ABOVE the room and are NOT touched.
Verified 7/7 on the wasm oracle: box 13689->8464, avgTicks 80511->75065.2.
"""
import os
d = os.path.dirname(__file__)
rows = open(os.path.join(d, "matmul-run.man")).read().split("\n")
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
keep, removed = [], []
for i, r in enumerate(rows):
    if 44 <= i <= 115 and (set(r) - {" "}) == {"|"}:
        removed.append(i); continue
    keep.append(r)
out = "\n".join(x.rstrip() for x in keep) + "\n"
open(os.path.join(d, "matmul-opt.man"), "w").write(out)
print("removed", len(removed), "CTRL-interior blank rows:", removed)
