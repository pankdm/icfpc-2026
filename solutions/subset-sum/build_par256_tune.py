#!/usr/bin/env python3
"""Tunable wrapper around parallel_grid_build (the live champion generator).

Exposes the geometry constants as literals in ONE file so tools/autotune.py can
perturb them.  Reproduces parallel256-prefix-compact-r13.man byte-exact with the
defaults below.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SS_PREFIX", "1")
os.environ.setdefault("SS_COMPACT_WORKER", "1")
os.environ.setdefault("SS_WORKERS", "256")
os.environ.setdefault("SS_ROWS", "13")
os.environ.setdefault("SS_COLUMNS", "20")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parallel_grid_build as pg  # noqa: E402

# Geometry knobs (defaults reproduce the 604x588 champion).
# SS_GAP_DELTA=-1 gives 585x588 (box -5.2%, 7/7): one column less per worker.
# -2 regresses (566x598: height grows past width); ROW_STRIDE-1 breaks pipes.
GAP_DELTA = int(os.environ.get("SS_GAP_DELTA", "0"))
pg.WORKER_X0 = 10
pg.WORKER_GAP = 30 + pg.COMPACT_WIDTH_DELTA + GAP_DELTA
pg.ROW_STRIDE = 40
pg.BROADCAST_Y = 0
pg.WORKER_Y = 6
pg.COLLECTOR_Y = 36
pg.PRIOR_COLUMN = 15
pg.PRIOR_ATTACHMENT_X = 15
pg.FINAL_PRIOR_COLUMN = 30
pg.FINAL_PRIOR_ATTACHMENT_X = 29

if __name__ == "__main__":
    from compact_man import compact_text, dimensions

    program = pg.build()
    rendered = compact_text(program.render())
    name = (
        "parallel256-tunewrap.man" if GAP_DELTA == 0
        else f"parallel256-prefix-compact-r13-gap{30 + GAP_DELTA}.man"
    )
    destination = HERE / name
    destination.write_text(rendered + "\n", encoding="ascii")
    width, height = dimensions(rendered)
    print("saved", destination, "footprint", (width, height, max(width, height) ** 2))
