#!/usr/bin/env python3
"""Phase-1 table: current box vs min-rows / min-width / min-box optimum, per problem.

Reports the implied BOX for each objective, plus a SENSITIVITY row: the calibration
offsets (row_off/col_off) are measured on the as-built grid and assumed to carry over to
a re-placed one. row_off in particular can be NEGATIVE (blocks sharing rows, which the
model cannot express), so any win that survives only at the measured offset is fragile.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import smtrows

TARGETS = [
    ("Snake",      "solutions/snake/live-4d96c89f.man"),
    ("LLLM",       "solutions/little-little-little-man/live-8e907387.man"),
    ("Pathfinder", "solutions/pathfinder/mem16-flow-one-ring-square-eager.man"),
    ("LLM",        "solutions/little-little-man/live-2b320f4f.man"),
]

rows_out = []
for name, path in TARGETS:
    flow = smtrows.load_flow(path)
    ch = smtrows.grid_chrome(path, flow)
    wmax = ch["interior_w"]
    cache = {}
    wfloor = smtrows.width_floor(flow)
    ab = ch["as_built_rows"]
    ro, co = ch["row_off"], ch["col_off"]
    cw, chh = ch["chrome_w"], ch["chrome_h"]
    cur_side = max(ch["grid_w"], ch["grid_h"])

    rig_w, rig_h = ch["rigid_w"], ch["rigid_h"]

    def side(w, r, ro=ro):
        """OPTIMISTIC: chrome slides when the room shrinks (needs a placer + routing)."""
        return max(r + ro + 2 + chh, w + co + 2 + cw)

    def side_rigid(w, r, ro=ro):
        """GUARANTEED: nothing outside the room moves at all."""
        return max(r + ro + 2 + chh, w + co + 2 + cw, rig_w, rig_h)

    # min ROWS = the legacy objective: widest allowed, fewest rows
    r_rows = smtrows.rows_at_width(flow, wmax, cache)
    s_rows = side(wmax, r_rows)

    # (a) min WIDTH subject to rows <= as-built
    w_a = smtrows.min_width_at_rows(flow, ab, wfloor, wmax, cache)
    if w_a is None:
        s_a, r_a = None, None
    else:
        r_a = smtrows.rows_at_width(flow, w_a, cache)
        s_a = side(w_a, r_a)

    # (b) joint min max(w,h)
    best = smtrows.min_box(flow, cw, chh, wfloor, wmax, row_off=ro + 2, col_off=co + 2,
                           cache=cache)
    s_b, w_b, r_b = best if best else (None, None, None)

    # sensitivity: what if the row-sharing bonus does NOT carry over (row_off -> 0 floor)?
    ro_pess = max(ro, 0)
    s_b_pess = side(w_b, r_b, ro=ro_pess) if best else None

    # GUARANTEED best: sweep widths under the rigid floor (no chrome movement allowed)
    g_best = None
    for w in range(wfloor, wmax + 1):
        r = smtrows.rows_at_width(flow, w, cache)
        if r is None:
            continue
        s = side_rigid(w, r)
        if g_best is None or s <= g_best[0]:
            g_best = (s, w, r)

    rows_out.append(dict(name=name, cur=cur_side, box=ch["box"], wfloor=wfloor, wmax=wmax,
                         ab=ab, ro=ro, co=co, cw=cw, chh=chh, rig_w=rig_w, rig_h=rig_h,
                         r_rows=r_rows, s_rows=s_rows,
                         w_a=w_a, r_a=r_a, s_a=s_a,
                         w_b=w_b, r_b=r_b, s_b=s_b, s_b_pess=s_b_pess,
                         g=g_best))

def fmt(s):
    return f"{s}^2={s*s:,}" if s else "n/a"

print()
print(f"{'problem':<11} {'current':>16} {'min-ROWS':>16} {'min-WIDTH (a)':>16} {'joint (b) opt.':>16} {'joint GUARANTEED':>18}")
print("-" * 104)
for d in rows_out:
    print(f"{d['name']:<11} {fmt(d['cur']):>16} {fmt(d['s_rows']):>16} {fmt(d['s_a']):>16} "
          f"{fmt(d['s_b']):>16} {fmt(d['g'][0]):>18}")
print()
print("min-ROWS = the objective smtrows had until today. Note where it is WORSE than current.")
print("joint GUARANTEED = nothing outside the room is allowed to move (rigid floor).")
print("joint opt.       = the chrome slides with the room (needs place.py + length-preserving routing).")
print()
for d in rows_out:
    print(f"{d['name']}: interior {d['wmax']}w, width floor {d['wfloor']}, as-built block-rows {d['ab']}, "
          f"chrome w{d['cw']}/h{d['chh']}, calib row_off {d['ro']:+d} col_off {d['co']:+d}")
    print(f"   min-rows : w={d['wmax']} rows={d['r_rows']} -> side {d['s_rows']}")
    print(f"   (a) width: w={d['w_a']} rows={d['r_a']} -> side {d['s_a']}")
    print(f"   (b) joint: w={d['w_b']} rows={d['r_b']} -> side {d['s_b']}   "
          f"[pessimistic calib (row_off->{max(d['ro'],0)}): side {d['s_b_pess']}]")
    print(f"   rigid floor from NON-ROOM content: {d['rig_w']}w x {d['rig_h']}h  "
          f"-> guaranteed best side {d['g'][0]} at w={d['g'][1]} rows={d['g'][2]}")
    if d["g"][0] < d["cur"]:
        print(f"   GUARANTEED WIN: box {d['box']:,} -> {d['g'][0]**2:,}  "
              f"({(1-d['g'][0]**2/d['box'])*100:.1f}% score)")
    elif d["s_b"] and d["s_b"] < d["cur"]:
        print(f"   CONDITIONAL only: box {d['box']:,} -> {d['s_b']**2:,} "
              f"({(1-d['s_b']**2/d['box'])*100:.1f}%) BUT needs the chrome to slide; "
              f"rigid gives {d['g'][0]**2:,} = no change.")
    else:
        print(f"   NEGATIVE: box does not fall under either reading.")
    print()
