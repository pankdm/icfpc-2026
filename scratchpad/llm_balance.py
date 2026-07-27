#!/usr/bin/env python3
"""Measured-height balancing of the LLM two-controller cut.

Starts from the min-edge-cut partition and hill-climbs single-block moves to
minimise max(height_A, height_B) as MEASURED by the boustrophedon layout
engine at the target room width, subject to a cap on cut edges.
"""
import os, sys, json, random, collections
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
SCALE = float(os.environ.get('SCALE', '0.65'))
CODE_X = int(os.environ.get('CODE_X', '45'))


def spec(scale=SCALE):
    out, used = {}, set()
    for n, (off, g) in sorted(BASE.items(), key=lambda kv: kv[1][0]):
        c = max(1, int(round(off * scale)))
        while c in used:
            c += 1
        used.add(c)
        out[n] = (c, g)
    return out


SPEC = spec()


class Sub:
    def __init__(self, blocks):
        self.blocks = blocks


flow = bb.alias_empty_gotos(dedup.build_flow())
ALL = dict(flow.blocks)
LABELS = sorted(ALL)


def succs(toks):
    for t in toks:
        if isinstance(t, tuple):
            return list(t[1:])
    return []


EDGES = sorted({(l, s) for l in LABELS for s in succs(ALL[l]) if s in ALL and s != l})


def build_half(part, side):
    keep = [l for l in LABELS if part[l] == side]
    ks = set(keep)
    xtargets = sorted({v for (u, v) in EDGES if part[u] != part[v] and part[v] == side})
    blocks = {}
    # entry dispatch: read block id from cr, chain of decrement+branch, one row each
    if xtargets:
        chain = []
        for i, t in enumerate(xtargets):
            nxt = f'@DISP{i+1}' if i + 1 < len(xtargets) else t
            blocks[f'@DISP{i}'] = ['cr' if i == 0 else 'M', '1', '-',
                                   ('br', nxt, t, nxt)]
        blocks['@DISP0'][0] = 'cr'
    for l in keep:
        toks = []
        for t in ALL[l]:
            if isinstance(t, tuple):
                new = []
                for x in t[1:]:
                    new.append(x if x in ks else '@XFER')
                toks.append((t[0],) + tuple(new))
            else:
                toks.append(t)
        blocks[l] = toks
    # transfer stub: push id, send over cc, then park waiting on cr dispatch
    blocks['@XFER'] = ['M', 'cc', ('go', '@DISP0' if xtargets else keep[0])]
    if not xtargets:
        blocks['@DISP0'] = ['cr', ('go', keep[0])]
    return blocks


def measure(blocks):
    p = littleman.Program()
    try:
        lay = boustro.lay_cfg_boustrophedon(p, Sub(blocks), SPEC, code_x=CODE_X,
                                            op_slack=0, tight_width=True)
    except Exception as e:
        if os.environ.get('DBG'):
            print('LAYFAIL', e)
        return None, None, None
    return lay['width'], lay['height'], lay['ncorr']


def evaluate(part):
    hs, ws, ncs = [], [], []
    for s in (0, 1):
        w, h, nc = measure(build_half(part, s))
        if h is None:
            return None
        hs.append(h)
        ws.append(w)
        ncs.append(nc)
    cut = sum(1 for u, v in EDGES if part[u] != part[v])
    return max(hs), hs, ws, cut, ncs


def main():
    part = json.load(open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/llm_part_002.json'))
    part = {l: part.get(l, 0) for l in LABELS}
    cap = int(os.environ.get('CUTCAP', '14'))
    best = evaluate(part)
    print('start: maxH', best[0], 'H', best[1], 'W', best[2], 'cut', best[3], 'ncorr', best[4], flush=True)
    rng = random.Random(7)
    improved = True
    rounds = 0
    while improved and rounds < 12:
        rounds += 1
        improved = False
        order = LABELS[:]
        rng.shuffle(order)
        for l in order:
            part[l] ^= 1
            r = evaluate(part)
            if r is not None and r[3] <= cap and (r[0] < best[0] or
                                                  (r[0] == best[0] and r[3] < best[3])):
                best = r
                improved = True
                print(f'  move {l} -> {part[l]}: maxH {r[0]} H {r[1]} cut {r[3]}', flush=True)
            else:
                part[l] ^= 1
    print('FINAL maxH', best[0], 'H', best[1], 'W', best[2], 'cut', best[3], 'ncorr', best[4])
    json.dump(part, open('/tmp/llm_part_bal.json', 'w'))
    # report cross edges + entry targets
    cross = [(u, v) for u, v in EDGES if part[u] != part[v]]
    tin = collections.defaultdict(set)
    for u, v in cross:
        tin[part[v]].add(v)
    print('cross edges:', len(cross))
    for u, v in cross:
        print(f'  {u} -> {v}  ({part[u]}->{part[v]})')
    print('entry targets: A', sorted(tin[0]), '  B', sorted(tin[1]))
    pu = {0: collections.Counter(), 1: collections.Counter()}
    for l in LABELS:
        for t in ALL[l]:
            if not isinstance(t, tuple) and t in BASE:
                pu[part[l]][t] += 1
    for s in (0, 1):
        print('side', s, 'port ops', dict(pu[s].most_common()))
    print('rows A blocks', sum(1 for l in LABELS if part[l] == 0),
          'B blocks', sum(1 for l in LABELS if part[l] == 1))


if __name__ == '__main__':
    main()
