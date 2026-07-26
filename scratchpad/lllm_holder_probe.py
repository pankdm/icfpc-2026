#!/usr/bin/env python3
"""Measure the real cost of a scalar-holder access (LLLM machine design).

Builds CTRL room + HOLD room joined by a 2-cell pipe pair.  CTRL loops
`s` ... `r` around a cycle of tunable length; HOLD is a 6-cell echo ring
(`>` `r` `s` `v` / `<` ... `^`).  Slope of settleTick vs iteration count =
ticks per holder round trip.

MEASURED (rust interp, 2026-07-26):

    loop cells   8  10  12  14  16  18
    ticks/iter   9  11  13  15  17  19

i.e. **round trip = controller path length + 1**.  Pipe latency is COMPLETELY
HIDDEN for any controller cycle >= 8 cells; a scalar access costs only the
cells the controller walks, not the pipe.  Design consequence: the cost of the
LLLM step loop is the *walked path length* of the controller, so optimise
geometry (short hot loop, stations close together), not pipe count.

Also note bug class 3(a): the first version put the holder's `@` inside the
echo ring; '@' is a no-op so the man walked straight through it into the wall
(fatal at tick 22).  Man starts go on straight cells, turns need real glyphs.
"""
import os, sys, subprocess
sys.path.insert(0,'/Users/dmitrykorolev/projects/icfpc-2026-main/tools')
import littleman as lm
LM='/Users/dmitrykorolev/projects/icfpc-2026-main/interp/target/release/lm'
SC=os.path.join(os.path.dirname(os.path.abspath(__file__)),"lllm_holder_probe.man")

def build(n, gap):
    """controller loop: >(10-g,2) ... s(11,2) v(12,2) r(12,3) <(12,4) m d ... ^ back.
       gap = extra padding cells on the return row -> loop length 8+2*gap"""
    p = lm.Program()
    W=14+gap
    p.room(0,0,W,6)
    hx=W+2
    p.room(hx,0,8,6)
    p.pipe([(W,2),(W+1,2)])
    p.pipe([(hx-1,3),(hx-2,3)])
    p.output_room(1,8)
    p.pipe([(2,6),(2,7)])
    p.man(1,1)
    p.text(2,1,"`%d`b"%n); lx=2+len("`%d`b"%n)
    p.put(lx,1,"v"); p.put(lx,2,">")
    sx=W-3            # 's' cell, adjacent-ish to pipe
    p.put(sx,2,"s"); p.put(sx+1,2,"v")
    p.put(sx+1,3,"r"); p.put(sx+1,4,"<")
    p.put(sx,4,"m"); p.put(sx-1-gap,4,"d")
    for i in range(gap): p.put(sx-1-i,4," ")
    p.put(sx-1-gap,3," ") if False else None
    p.put(sx-1-gap,2,">")
    p.put(2,4,"s"); p.put(1,4,"H")
    p.put(hx+1,2,">"); p.put(hx+2,2,"r"); p.put(hx+3,2,"s"); p.put(hx+4,2,"v")
    p.put(hx+4,3,"<"); p.put(hx+1,3,"^"); p.man(hx+2,3)
    return p

def run(p, exp):
    p.save(SC)
    r=subprocess.run([LM,'--grade',SC,'--input=','--expected=%s'%exp,'--cap=2000000'],capture_output=True,text=True)
    return r.stdout.strip().splitlines()[-1]

for gap in range(0,6):
    a=run(build(100,gap),'100'); b=run(build(200,gap),'200')
    import json
    try:
        ta=json.loads(a)['settleTick']; tb=json.loads(b)['settleTick']
        print('gap',gap,'looplen',8+2*gap,'ticks/iter',(tb-ta)/100, a[:60])
    except Exception: print('gap',gap,a,b)
