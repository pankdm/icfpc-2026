#!/usr/bin/env python3
"""Coordinate descent around a known-good LLM port-column assignment."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'solutions',
                                'little-little-man'))
from llm_search_echo import repair, total
from llm_eval import get_flow

EM4 = {"ri": 112, "sp": 118, "rp": 134, "sc": 176, "rr": 243, "sd": 326,
       "sa": 336, "ss": 346, "cc": 352, "cr": 386, "sp1": 316, "rp1": 323}
SPLIT = {"ri": 52, "sp": 55, "rp": 78, "sc": 157, "rr": 161, "sd": 285,
         "sa": 295, "ss": 305, "cc": 311, "cr": 315, "sp1": 211, "rp1": 218}


def main(slot='mid'):
    flow = get_flow()
    cur = repair(dict(SPLIT if slot == 'split' else EM4), slot)
    best, r = total(cur, flow)
    print('start', best, r['box_h'], r['box_w'], flush=True)
    improved = True
    while improved:
        improved = False
        for p in list(cur):
            for d in (-25, -10, -6, -3, -1, 1, 3, 6, 10, 25):
                cand = repair(dict(cur, **{p: max(52, cur[p] + d)}), slot)
                c2, r2 = total(cand, flow)
                if c2 is not None and c2 < best:
                    best, cur, r = c2, cand, r2
                    improved = True
                    print('->', best, r2['box_h'], r2['box_w'],
                          json.dumps(cur), flush=True)
    print('FINAL', json.dumps({'box': best, 'cols': cur, 'r': r}))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'mid')
