#!/usr/bin/env python3
# tr.py file.man "input" steps [focus_id]  -> per-step: man positions + glyph under each + regs + output changes
import sys, subprocess, json
LM="/Users/visenbaev/icfpc26/interp/target/release/lm"
f=sys.argv[1]; inp=sys.argv[2]; steps=sys.argv[3] if len(sys.argv)>3 else "200"
focus=sys.argv[4] if len(sys.argv)>4 else None
rows=open(f).read().split("\n")
def glyph(x,y):
    if 0<=y<len(rows) and 0<=x<len(rows[y]): return rows[y][x]
    return ' '
out=subprocess.run([LM,f,steps,f"--input={inp}"],capture_output=True,text=True)
prev_out=None
for line in out.stdout.splitlines():
    try: j=json.loads(line)
    except: continue
    parts=[]
    for r in j["runners"]:
        if focus and str(r["id"])!=focus: continue
        x,y=r["pos"]; g=glyph(x,y)
        parts.append(f"#{r['id']}({x},{y})'{g}'a{r['a']}b{r['b']}p{r['backpack']}{'H' if r['halted'] else ''}")
    o=j.get("output")
    tag=""
    if o!=prev_out: tag=f"  OUT={o}"; prev_out=o
    end=j.get("end")
    if end and end!="running": tag+=f"  END={end} {j.get('loaderror','')}"
    print(j["step"]," ".join(parts)+tag)
