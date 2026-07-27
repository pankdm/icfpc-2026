#!/usr/bin/env python3
"""Write the best checkpoint from search_layout.py into build_lllm.py.

    python3 solutions/little-little-little-man/apply_search.py /tmp/best_*.json

search_layout writes a JSON checkpoint on every improvement, so a long anneal
can be harvested at any time.  This picks the lowest-scoring checkpoint and
rewrites the three searched constants (HOLDER_ORDER, BLOCK_ORDER, HOLDER_FLIP)
in place.  It only edits those three literals, never anything else in the file.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build_lllm.py")


def fmt_list(name, items, per_line):
    body = "".join("    " + ", ".join('"%s"' % x for x in items[i:i + per_line]) + ",\n"
                   for i in range(0, len(items), per_line))
    return "%s = [\n%s]" % (name, body)


def main(paths):
    best = None
    for p in paths:
        try:
            d = json.load(open(p))
        except (ValueError, IOError):
            continue
        d["_from"] = p
        if best is None or d["score"] < best["score"]:
            best = d
    if best is None:
        sys.exit("no usable checkpoint")
    print("applying %s: score %.4gB box %d ticks %.0f"
          % (best["_from"], best["score"] / 1e9, best["box"], best["ticks"]))

    src = open(BUILD).read()
    for name, items, per in (("HOLDER_ORDER", best["holder"], 5),
                             ("BLOCK_ORDER", best["block"], 4),
                             ("HOLDER_FLIP", best["flip"], 5)):
        pat = re.compile(r"^%s = \[[^\]]*\]" % name, re.M | re.S)
        assert pat.search(src), name
        src = pat.sub(lambda _m, n=name, it=items, p=per: fmt_list(n, it, p), src, 1)
    open(BUILD, "w").write(src)
    print("build_lllm.py updated")


if __name__ == "__main__":
    main(sys.argv[1:])
