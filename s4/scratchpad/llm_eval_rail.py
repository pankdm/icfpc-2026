#!/usr/bin/env python3
"""Evaluate LLM controller box for a given port column assignment, RAIL layout."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
S4 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(S4, 'tools'))
sys.path.insert(0, os.path.join(S4, 'solutions', 'little-little-man'))
import boustro
import railflow
from llm_eval import get_flow, GLYPH, PORTS


def evaluate_rail(cols, op_slack=0, x0=0, y0=0, nrail=10, max_rail=80,
                  flow=None, GLYPH=GLYPH):
    if flow is None:
        flow = get_flow()
    bands = {}
    bands.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if GLYPH[n] == 's']))
    bands.update(boustro.voronoi_bands(
        [(n, c) for n, c in cols.items() if GLYPH[n] == 'r']))
    opmax = max(cols.values()) + op_slack
    labels = list(flow.blocks)
    try:
        cursor, entry, cells, nrail, intent = railflow.solve(
            flow, labels, cols, GLYPH, bands, x0, y0, nrail, opmax,
            (), max_rail)
    except boustro.Conflict as e:
        return {'error': str(e)}
    max_y = max(y for _, y in cursor.cells)
    height = max_y + 1 - y0 + 1
    width = max(opmax, max(cols.values())) + 2 - x0
    return {'width': width, 'height': height, 'ncorr': nrail,
            'cells': len(cursor.cells)}


if __name__ == '__main__':
    import json
    from llm_eval import evaluate
    BASE = {'ri': 55, 'sp': 65, 'rp': 75, 'sc': 95, 'rr': 119, 'sd': 125,
            'sa': 163, 'ss': 225, 'cc': 245, 'cr': 275}
    cols = json.loads(sys.argv[1]) if len(sys.argv) > 1 else BASE
    print('boustro', evaluate(cols))
    print('rail   ', evaluate_rail(cols))
