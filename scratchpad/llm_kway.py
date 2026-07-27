#!/usr/bin/env python3
"""k-way CFG split of the LLM controller: measured room width x height,
projected program box.  k=1 reproduces the single-controller baseline."""
import os, sys, json, random, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
sys.path.insert(0, os.path.join(HERE, '..', 'solutions', 'little-little-man'))
import boustro, littleman
import build_banked_boustro as bb, build_banked_dedup as dedup

BASE = {"ri": (10, "r"), "rp": (30, "r"), "rr": (74, "r"), "cr": (230, "r"),
        "sp": (20, "s"), "sc": (50, "s"), "sd": (80, "s"), "sa": (118, "s"),
        "ss": (180, "s"), "cc": (200, "s")}


def spec(scale):
    out, used = {}, set()
    for n, (off, g) in sorted(BASE.items(), key=lambda kv: kv[1][0]):
        c = max(1, int(round(off * scale)))
        while c in used:
            c += 1
        used.add(c)
        out[n] = (c, g)
    return out


class Sub:
    def __init__(self, b):
        self.blocks = b


flow = bb.alias_empty_gotos(dedup.build_flow())
ALL = dict(flow.blocks)
LABELS = sorted(ALL)
ROWS = json.load(open('/tmp/llm_flow.json'))


def succs(t):
    for x in t:
        if isinstance(x, tuple):
            return list(x[1:])
    return []


EDGES = sorted({(l, s) for l in LABELS for s in succs(ALL[l]) if s in ALL and s != l})


def build_part(part, side):
    keep = [l for l in LABELS if part[l] == side]
    if not keep:
        return None
    ks = set(keep)
    xt = sorted({v for (u, v) in EDGES if part[u] != part[v] and part[v] == side})
    blocks = {}
    for i, t in enumerate(xt):
        nxt = f'@D{i+1}' if i + 1 < len(xt) else t
        blocks[f'@D{i}'] = ['cr' if i == 0 else 'M', '1', '-', ('br', nxt, t, nxt)]
    for l in keep:
        toks = []
        for t in ALL[l]:
            if isinstance(t, tuple):
                toks.append((t[0],) + tuple(x if x in ks else '@X' for x in t[1:]))
            else:
                toks.append(t)
        blocks[l] = toks
    blocks['@X'] = ['M', 'cc', ('go', '@D0' if xt else keep[0])]
    if not xt:
        blocks['@D0'] = ['cr', ('go', keep[0])]
    return blocks


def measure(blocks, scale):
    best = None
    for cx in (24, 32, 40, 50, 62, 74):
        p = littleman.Program()
        try:
            l = boustro.lay_cfg_boustrophedon(p, Sub(blocks), spec(scale),
                                              code_x=cx, op_slack=0, tight_width=True)
        except Exception:
            continue
        if best is None or l['width'] < best[0]:
            best = (l['width'], l['height'], l['ncorr'])
    return best


def kway(k, seed=0):
    """balance by model rows, minimise cut, via annealed local search"""
    W = {l: ROWS[l]['rows'] for l in LABELS}
    tot = sum(W.values())
    rng = random.Random(seed)
    part = {l: rng.randrange(k) for l in LABELS}

    def cut(p):
        return sum(1 for u, v in EDGES if p[u] != p[v])

    def imb(p):
        s = collections.Counter()
        for l in LABELS:
            s[p[l]] += W[l]
        return max(s[i] for i in range(k)) - tot / k

    def obj(p):
        return cut(p) + 3.0 * max(0.0, imb(p) - 0.01 * tot)
    cur = obj(part)
    T = 6.0
    for it in range(120000):
        T = 6.0 * (1 - it / 120000) + 0.02
        l = rng.choice(LABELS)
        old = part[l]
        new = rng.randrange(k)
        if new == old:
            continue
        part[l] = new
        o = obj(part)
        if o <= cur or rng.random() < pow(2.718, -(o - cur) / T):
            cur = o
        else:
            part[l] = old
    # greedy polish
    imp = True
    while imp:
        imp = False
        for l in LABELS:
            old = part[l]
            for new in range(k):
                if new == old:
                    continue
                part[l] = new
                o = obj(part)
                if o < cur - 1e-9:
                    cur, old, imp = o, new, True
                else:
                    part[l] = old
    return part, cut(part)


BAND = 49          # champion RAM/IO band rows (live-2b320f4f: y744..792)
BANDW = 356        # champion RAM/IO band width
CHAMP = 742        # champion controller rows
BOUSTRO1 = 994     # boustro rows for the same flow at scale 1.0
CHAMPBOX = 628849

print(f'{"k":>2s} {"scale":>5s} {"cut":>4s} {"roomW":>6s} {"rowsSum":>7s} {"maxH":>5s} '
      f'{"chH":>5s} {"W":>5s} {"H":>5s} {"box":>8s} {"gain":>5s}')
for k in (1, 2, 3, 4):
    best_part, c = (None, 0)
    if k > 1:
        cands = [kway(k, s) for s in range(4)]
        best_part, c = min(cands, key=lambda pc: pc[1])
    for scale in (0.30, 0.35, 0.40, 0.50, 0.65, 0.80, 1.00):
        if k == 1:
            m = measure(dict(ALL), scale)
            if not m:
                continue
            ws, hs = [m[0]], [m[1]]
        else:
            ws, hs, ok = [], [], True
            for s in range(k):
                b = build_part(best_part, s)
                m = measure(b, scale) if b else None
                if not m:
                    ok = False
                    break
                ws.append(m[0])
                hs.append(m[1])
            if not ok:
                continue
        maxH = max(hs)
        rowsum = sum(hs)
        # champion-tech projection: same relative row density as live-2b320f4f
        chH = round(maxH * CHAMP / BOUSTRO1)
        W = max(sum(ws) + (k - 1), BANDW)
        H = chH + 2 + BAND
        box = max(W, H) ** 2
        print(f'{k:2d} {scale:5.2f} {c:4d} {ws[0]:6d} {rowsum:7d} {maxH:5d} '
              f'{chH:5d} {W:5d} {H:5d} {box:8d} {CHAMPBOX/box:5.2f}')
