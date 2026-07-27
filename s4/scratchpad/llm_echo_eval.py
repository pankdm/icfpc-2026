#!/usr/bin/env python3
"""Height of the rail controller with k replicated scratch echoes."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_echo
from llm_eval_rail import evaluate_rail

R4 = {'ri': 52, 'sp': 55, 'rp': 78, 'sc': 157, 'rr': 206, 'sd': 207,
      'sa': 217, 'ss': 227, 'cc': 268, 'cr': 292}


def build_cols(base, extra):
    """extra: list of (sp_col, rp_col) for copies 1..k-1."""
    cols = dict(base)
    for i, (s, r) in enumerate(extra, start=1):
        cols[f'sp{i}'] = s
        cols[f'rp{i}'] = r
    return cols


def measure(base, extra, nrail=48):
    cols = build_cols(base, extra)
    k = len(extra) + 1
    flow, glyphs, est = llm_echo.rewrite_flow(cols, k)
    r = evaluate_rail(cols, nrail=nrail, flow=flow, GLYPH=glyphs)
    r['est_rows'] = est
    return r, cols


if __name__ == '__main__':
    trials = {
        'k1': [],
        'k2@212': [(212, 216)],
        'k2@300': [(300, 310)],
        'k2@160': [(160, 164)],
        'k3': [(212, 216), (300, 310)],
        'k4': [(120, 124), (212, 216), (300, 310)],
        'k5': [(120, 124), (176, 180), (212, 216), (300, 310)],
    }
    for name, extra in trials.items():
        r, cols = measure(R4, extra)
        w = r.get('width')
        h = r.get('height')
        print(name, r.get('error', ''), 'h', h, 'est', r.get('est_rows'),
              'w', w, 'nrail', r.get('ncorr'))
