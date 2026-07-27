#!/usr/bin/env python3
"""Measure boustro controller HEIGHT vs port-span WIDTH for the LLM CFG,
full graph and each half of the min-cut partition."""
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'solutions', 'little-little-man'))
import boustro, littleman
import build_banked_boustro as bb, build_banked_dedup as dedup

BASE = {
    "ri": (10, "r"), "rp": (30, "r"), "rr": (74, "r"), "cr": (230, "r"),
    "sp": (20, "s"), "sc": (50, "s"), "sd": (80, "s"), "sa": (118, "s"),
    "ss": (180, "s"), "cc": (200, "s"),
}


def scaled_spec(scale, keep=None):
    keep = keep or set(BASE)
    items = [(n, v) for n, v in BASE.items() if n in keep]
    # renormalise offsets of the kept ports onto a 1..span grid preserving order
    out = {}
    for n, (off, g) in items:
        out[n] = (max(1, int(round(off * scale))), g)
    # de-duplicate columns
    used = set()
    for n in sorted(out, key=lambda k: out[k][0]):
        c, g = out[n]
        while c in used:
            c += 1
        used.add(c)
        out[n] = (c, g)
    return out


class Sub:
    def __init__(self, blocks):
        self.blocks = blocks


def measure(blocks, spec, code_x=45, op_slack=0):
    p = littleman.Program()
    try:
        lay = boustro.lay_cfg_boustrophedon(p, Sub(blocks), spec,
                                            code_x=code_x, op_slack=op_slack,
                                            tight_width=True)
    except Exception as e:
        return None, None, str(e)
    return lay['width'], lay['height'], None


def main():
    flow = bb.alias_empty_gotos(dedup.build_flow())
    part = json.load(open('/tmp/llm_part.json'))
    allb = dict(flow.blocks)
    # halves: cross-edge targets get rewritten to a local stub so the layout
    # engine sees a closed graph of the right shape.
    halves = {}
    for side in (0, 1):
        keep = [l for l in allb if part.get(l, 0) == side]
        keepset = set(keep)
        blocks = {}
        stub = 'XFER'
        for l in keep:
            toks = []
            for t in allb[l]:
                if isinstance(t, tuple):
                    tt = (t[0],) + tuple(x if x in keepset else stub for x in t[1:])
                    toks.append(tt)
                else:
                    toks.append(t)
            blocks[l] = toks
        # stub = send block id over cc, then wait on cr, then a dispatch chain
        blocks[stub] = ['sc', 'cc'] + ['cr', 'M', '1', '-', ('br', keep[0], keep[0], keep[0])]
        halves[side] = blocks
    print(f'{"case":8s} {"scale":>6s} {"width":>6s} {"height":>7s}  note')
    for name, blocks in [('full', allb), ('A', halves[0]), ('B', halves[1])]:
        for scale in (1.0, 0.9, 0.8, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4):
            spec = scaled_spec(scale)
            w, h, err = measure(blocks, spec)
            print(f'{name:8s} {scale:6.2f} {str(w):>6s} {str(h):>7s}  {err or ""}')


if __name__ == '__main__':
    main()
