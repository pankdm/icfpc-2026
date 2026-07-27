#!/usr/bin/env python3
"""Write a {ports, floor} seed for pf_joint --start from a port map alone.

Components are pinned under their command port (zero-length feeder) and the
band rows start from BAND_BASE; pf_joint's soft-penalty walk then only has to
find a legal ROW ordering for the horizontal runs.

  cd s4 && python3 scratchpad/pf_start.py '{"ri":15,...}' /tmp/seed.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FORK = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(FORK, "tools"))
sys.path.insert(0, HERE)

import pf_derive as D  # noqa: E402
import stateflow  # noqa: E402

ports = {n: stateflow.DEFAULT_PORTS[n][0] for n in stateflow.DEFAULT_PORTS}
ports.update(json.loads(sys.argv[1]))
bands = dict(D.BAND_BASE)
# a free port order needs one band row per service; give them distinct rows
# from the start so the walk begins on a plausible ordering instead of three
# runs stacked on row 1.
bands.update(ctop=10, sc_band=1, rr_band=2, cc_band=3, cr_band=4,
             sp_band=5, rp_band=6, qr_band=7, ri_row=9, scratch_row=8,
             display_row=8)
floor = D.floor_for(ports, bands)
json.dump({"ports": ports, "floor": floor}, open(sys.argv[2], "w"), indent=1)
print(json.dumps({"ports": ports, "floor": floor}))
