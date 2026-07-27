#!/usr/bin/env python3
"""Anneal port columns for the rail controller with k replicated scratch echoes.

Slot string, one char per EXTRA echo:
  m  chained between the scalar RAM's reply column and the display's DATA pipe
  r  past the cell RAM (nothing can collide there; width is free)
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
NRAIL = 48
BASE = {'ri': 52, 'sp': 55, 'rp': 78, 'sc': 157, 'rr': 206, 'sd': 207,
        'sa': 217, 'ss': 227, 'cc': 268, 'cr': 292}


def repair(c, slots):
    c = dict(c)
    c['ri'] = max(OPMIN, c['ri'])
    c['sp'] = max(c['sp'], c['ri'] + 3)
    c['rp'] = max(c['rp'], c['sp'] + 6)
    c['sc'] = max(c['sc'], c['sp'] + 11, c['rp'] + 6)
    c['rr'] = max(c['rr'], c['sc'] + 24)
    prev = c['rr']
    for i, s in enumerate(slots, start=1):
        if s != 'm':
            continue
        c[f'sp{i}'] = max(c[f'sp{i}'], prev + 3)
        c[f'rp{i}'] = max(c[f'rp{i}'], c[f'sp{i}'] + 6)
        prev = c[f'rp{i}']
    c['sd'] = max(c['sd'], prev + 3)
    c['sa'] = max(c['sa'], c['sd'] + 10, c['sc'] + 31)
    c['ss'] = max(c['ss'], c['sa'] + 10)
    c['cc'] = max(c['cc'], c['ss'] + 6, c['sc'] + 81)
    c['cr'] = max(c['cr'], c['cc'] + 24)
    prev = c['cr']
    for i, s in enumerate(slots, start=1):
        if s != 'r':
            continue
        c[f'sp{i}'] = max(c[f'sp{i}'], prev + 3)
        c[f'rp{i}'] = max(c[f'rp{i}'], c[f'sp{i}'] + 6)
        prev = c[f'rp{i}']
    return c


def total(c, flow, k):
    new, glyphs, _est = echo_split.rewrite_flow(flow, c, k, opmin=NRAIL + 2)
    r = evaluate_rail(c, nrail=NRAIL, flow=new, GLYPH=glyphs)
    if 'error' in r:
        return None, r
    height = r['height'] + 45
    width = max(c['cr'] + 2, c['cc'] + 76, max(c.values()) + 8)
    return max(width, height) ** 2, dict(r, box_w=width, box_h=height)


def main(seed, iters, slots):
    rng = random.Random(seed)
    flow = get_flow()
    k = len(slots) + 1
    start = dict(BASE)
    base_mid, base_right = 215, 300
    for i, s in enumerate(slots, start=1):
        if s == 'm':
            start[f'sp{i}'], start[f'rp{i}'] = base_mid, base_mid + 8
            base_mid += 20
        else:
            start[f'sp{i}'], start[f'rp{i}'] = base_right, base_right + 8
            base_right += 20
    keys = list(start)
    cur = repair(start if seed == 0 else
                 {p: start[p] + rng.randint(-30, 60) for p in keys}, slots)
    c, r = total(cur, flow, k)
    while c is None:
        cur = repair({p: start[p] + rng.randint(-30, 60) for p in keys}, slots)
        c, r = total(cur, flow, k)
    best = (c, dict(cur), r)
    for it in range(iters):
        T = 0.05 * (1 - it / iters) + 1e-4
        cand = dict(cur)
        for _ in range(rng.choice([1, 1, 2, 3])):
            p = rng.choice(keys)
            cand[p] = max(OPMIN, cand[p] +
                          rng.choice([-60, -25, -10, -4, -1, 1, 4, 10, 25, 60]))
        cand = repair(cand, slots)
        c2, r2 = total(cand, flow, k)
        if c2 is None:
            continue
        if c2 <= c or rng.random() < math.exp(-(c2 - c) / max(1.0, c * T)):
            cur, c = cand, c2
            if c2 < best[0]:
                best = (c2, dict(cand), r2)
    print(json.dumps({'seed': seed, 'slots': slots, 'box': best[0],
                      'cols': best[1], 'r': best[2]}))


if __name__ == '__main__':
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
