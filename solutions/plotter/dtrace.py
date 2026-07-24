#!/usr/bin/env python3
# dtrace.py file.man "input" steps [focus_id] [--pix]
# Display-aware tracer built on the fast Rust `lm`. Shows man state, display
# cursor/frame count, lit (non-zero) pixels of the NEXT buffer, output, end.
import sys, subprocess, json
LM = "/Users/visenbaev/icfpc26/interp/target/release/lm"
f = sys.argv[1]; inp = sys.argv[2]; steps = sys.argv[3] if len(sys.argv) > 3 else "2000"
focus = None; showpix = False
for a in sys.argv[4:]:
    if a == "--pix": showpix = True
    else: focus = a
rows = open(f).read().split("\n")
def glyph(x, y):
    if 0 <= y < len(rows) and 0 <= x < len(rows[y]): return rows[y][x]
    return ' '
out = subprocess.run([LM, f, steps, f"--input={inp}"], capture_output=True, text=True)
prev_out = None; prev_frames = None; prev_lit = None
for line in out.stdout.splitlines():
    try: j = json.loads(line)
    except: continue
    parts = []
    for r in j["runners"]:
        if focus and str(r["id"]) != focus: continue
        x, y = r["pos"]; g = glyph(x, y)
        parts.append(f"#{r['id']}({x},{y})'{g}'a{r['a']}b{r['b']}p{r['backpack']}{'H' if r['halted'] else ''}")
    tag = ""
    disp = (j.get("displays") or [{}])[0]
    cur = disp.get("cursor"); frames = disp.get("frames")
    if frames != prev_frames:
        tag += f"  FRAMES={frames}"; prev_frames = frames
    o = j.get("output")
    if o != prev_out: tag += f"  OUT={o}"; prev_out = o
    fj = j.get("frameJudge")
    if fj is not None: tag += f"  FJUDGE={fj}"
    end = j.get("end")
    if end and end != "running": tag += f"  END={end} {j.get('fatal') or j.get('loaderror') or ''}"
    line_out = f"{j['step']:>5} " + " ".join(parts)
    if cur is not None: line_out += f" cur={cur}"
    if showpix:
        buf = disp.get("back") or []
        lit = [(i, v) for i, v in enumerate(buf) if v]
        if lit != prev_lit:
            tag += "  LIT=" + ",".join(f"{i}:{v}" for i, v in lit[:40]) + ("..." if len(lit) > 40 else "")
            prev_lit = lit
    print(line_out + tag)
