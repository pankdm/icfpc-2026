#!/usr/bin/env python3
"""How compressible is icfp-history.txt, and what does the ring encoder achieve?

Prints sizes only -- never the text.
"""
import bz2, collections, gzip, lzma, math, zlib

TXT = "/Users/visenbaev/icfpc26/solutions/history-lesson/icfp-history.txt"
data = open(TXT, "rb").read()
n = len(data)
alpha = sorted(set(data))
print(f"bytes={n}  distinct={len(alpha)}  "
      f"min={min(alpha)} max={max(alpha)}")

def H(order):
    ctx = collections.defaultdict(collections.Counter)
    for i in range(n):
        ctx[data[max(0, i - order):i]][data[i]] += 1
    bits = 0.0
    for c, cnt in ctx.items():
        t = sum(cnt.values())
        for v in cnt.values():
            bits -= v * math.log2(v / t)
    return bits / 8

for o in (0, 1, 2, 3):
    print(f"  order-{o} empirical entropy (no model cost): {H(o):7.0f} B "
          f"ratio {H(o)/n:.3f}")

print(f"  zlib -9      {len(zlib.compress(data, 9)):5d} B  ratio "
      f"{len(zlib.compress(data,9))/n:.3f}")
print(f"  gzip -9      {len(gzip.compress(data, 9)):5d} B")
print(f"  bz2 -9       {len(bz2.compress(data, 9)):5d} B  ratio "
      f"{len(bz2.compress(data,9))/n:.3f}")
print(f"  lzma         {len(lzma.compress(data)):5d} B  ratio "
      f"{len(lzma.compress(data))/n:.3f}")
raw = lzma.compress(data, format=lzma.FORMAT_RAW,
                    filters=[{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}])
print(f"  lzma raw     {len(raw):5d} B  ratio {len(raw)/n:.3f}")

# what the ring stream costs today
print()
print("ring encoder today: 2042 base-92 symbols = "
      f"{2042*math.log2(92)/8:.0f} B  ratio {2042*math.log2(92)/8/n:.3f}")
print("76x76 needs ~1711 symbols (base 92) = "
      f"{1711*math.log2(92)/8:.0f} B  ratio {1711*math.log2(92)/8/n:.3f}")
