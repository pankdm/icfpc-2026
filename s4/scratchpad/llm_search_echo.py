#!/usr/bin/env python3
"""Anneal port columns for the RAIL controller with a REPLICATED scratch echo.

Two hardware slots are offered for the extra echo room, because the band under
the controller is already packed:

  mid    between the scalar RAM's reply column and the display's DATA column
  right  past the cell RAM, where nothing can collide (width is free: the box
         is height-bound at 877 vs 344)
"""
import sys, os, random, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'solutions',
                                'little-little-man'))
import echo_split
from llm_eval import get_flow
from llm_eval_rail import evaluate_rail

OPMIN = 52
BASE = {'ri': 52, 'sp': 55, 'rp': 78, 'sc': 157, 'rr': 206, 'sd': 207,
        'sa': 217, 'ss': 227, 'cc': 268, 'cr': 292}
NRAIL = 48


def repair(c, slot):
    c = dict(c)
    c['ri'] = max(OPMIN, c['ri'])
    c['sp'] = max(c['sp'], c['ri'] + 3)
    c['rp'] = max(c['rp'], c['sp'] + 6)
    c['sc'] = max(c['sc'], c['sp'] + 11, c['rp'] + 6)
    c['rr'] = max(c['rr'], c['sc'] + 24)
    if slot == 'mid':
        c['sp1'] = max(c['sp1'], c['rr'] + 3)
        c['rp1'] = max(c['rp1'], c['sp1'] + 6)
        c['sd'] = max(c['sd'], c['rp1'] + 3)
    else:
        c['sd'] = max(c['sd'], c['rr'] + 1)
    c['sa'] = max(c['sa'], c['sd'] + 10, c['sc'] + 31)
    c['ss'] = max(c['ss'], c['sa'] + 10)
    c['cc'] = max(c['cc'], c['ss'] + 6, c['sc'] + 81)
    c['cr'] = max(c['cr'], c['cc'] + 24)
    if slot == 'right':
        c['sp1'] = max(c['sp1'], c['cr'] + 3)
        c['rp1'] = max(c['rp1'], c['sp1'] + 6)
    return c


def total(c, flow):
    k = 2 if 'sp1' in c else 1
    new, glyphs, _est = echo_split.rewrite_flow(flow, c, k, opmin=NRAIL + 2)
    r = evaluate_rail(c, nrail=NRAIL, flow=new, GLYPH=glyphs)
    if 'error' in r:
        return None, r
    height = r['height'] + 45
    width = max(c['cr'] + 2, c['cc'] + 76, max(c.values()) + 8)
    return max(width, height) ** 2, dict(r, box_w=width, box_h=height)


def main(seed, iters, slot):
    rng = random.Random(seed)
    flow = get_flow()
    keys = list(BASE) + ['sp1', 'rp1']
    start = dict(BASE)
    start['sp1'] = 300 if slot == 'right' else 210
    start['rp1'] = start['sp1'] + 8
    cur = repair(start if seed == 0 else
                 {p: start[p] + rng.randint(-30, 60) for p in keys}, slot)
    c, r = total(cur, flow)
    while c is None:
        cur = repair({p: start[p] + rng.randint(-30, 60) for p in keys}, slot)
        c, r = total(cur, flow)
    best = (c, dict(cur), r)
    for it in range(iters):
        T = 0.05 * (1 - it / iters) + 1e-4
        cand = dict(cur)
        for _ in range(rng.choice([1, 1, 2, 3])):
            p = rng.choice(keys)
            cand[p] = max(OPMIN, cand[p] +
                          rng.choice([-60, -25, -10, -4, -1, 1, 4, 10, 25, 60]))
        cand = repair(cand, slot)
        c2, r2 = total(cand, flow)
        if c2 is None:
            continue
        if c2 <= c or rng.random() < math.exp(-(c2 - c) / max(1.0, c * T)):
            cur, c = cand, c2
            if c2 < best[0]:
                best = (c2, dict(cand), r2)
    print(json.dumps({'seed': seed, 'slot': slot, 'box': best[0],
                      'cols': best[1], 'r': best[2]}))


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
