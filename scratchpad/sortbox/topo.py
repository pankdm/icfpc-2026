#!/usr/bin/env python3
"""Dump room + pipe topology of a .man (rooms, pipe src/dst, endpoints, length)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import pipecheck as pc

rows = pc.load_rows(sys.argv[1])
topo = pc.analyze(rows)
if topo.get("type") == "error":
    sys.exit(topo.get("message"))
for i, r in enumerate(topo.get("rooms") or []):
    print(f"room {i}: {tuple(r['min'])}..{tuple(r['max'])} kind={r.get('kind')}")
for i, p in enumerate(topo.get("pipes") or []):
    path = [tuple(c["pos"]) for c in p.get("path") or []]
    print(f"pipe {i}: src=room{p.get('src')} dst=room{p.get('dst')} len={len(path)}")
    print(f"   path={path}")
