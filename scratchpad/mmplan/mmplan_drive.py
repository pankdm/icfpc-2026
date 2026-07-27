#!/usr/bin/env python3
"""Driver: parallel glue-spacing sweep (mmplan_sweep.parallel)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmplan_sweep as S

if __name__ == '__main__':
    GRID = [(sx, sy) for sx in (1.0, 1.8, 2.6) for sy in (1.0, 1.8, 2.6)] + \
           [(3.4, 1.8), (1.8, 3.4), (3.4, 3.4)]
    S.parallel(GRID, iters=int(sys.argv[1]) if len(sys.argv) > 1 else 8,
               workers=int(sys.argv[2]) if len(sys.argv) > 2 else 12)
