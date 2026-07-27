"""Recover rooms + pipe paths from a produced .man so a standalone builder can be written."""
import subprocess, json, sys, os
ROOT='/Users/visenbaev/icfpc26'
man=sys.argv[1]
rows=open(man).read().split('\n')
W=max(len(r) for r in rows); H=len(rows)
def at(x,y):
    if 0<=y<H and 0<=x<len(rows[y]): return rows[y][x]
    return ' '
# rooms: same scan as the engine
claimed=[[False]*W for _ in range(H)]
rooms=[]
for y0 in range(H):
    for x0 in range(W):
        if at(x0,y0)!='+': continue
        x1=x0+1
        while at(x1,y0)=='-': x1+=1
        if x1<=x0+1 or at(x1,y0)!='+': continue
        y1=y0+1
        while at(x0,y1)=='|': y1+=1
        if y1<=y0+1 or at(x0,y1)!='+': continue
        if at(x1,y1)!='+': continue
        ok=all(at(x,y1)=='-' for x in range(x0+1,x1)) and all(at(x1,y)=='|' for y in range(y0+1,y1))
        if not ok: continue
        rooms.append((x0,y0,x1,y1))
print('rooms', rooms)
p=subprocess.run([os.path.join(ROOT,'interp/target/release/lm'),'--inspect=0',man],capture_output=True,text=True)
d=json.loads(p.stdout)
print('pipes', [(x.get('src'),x.get('dst')) for x in d['pipes']])
