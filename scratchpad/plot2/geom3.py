import json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE="/Users/visenbaev/icfpc26"; SP=HERE+"/solutions/plotter"
sys.path.insert(0, SP)
import swar_build as B, swar_setup as SS
pre,px,py,tb,tf=SS.segments()
BW=max(len(px),len(py))+2
print("npre",len(pre),"ntail",len(tb),"BW",BW,"fin",len(tf))
combos=[]
for L in range(5,9):
    IH=B.ih_of(L)
    for k in range(3,L-1,2):
        trows=L-k-1
        if trows<1: continue
        for W in range(BW+8,56):
            if (W-3)+(k-1)*(W-BW-3)+(W-BW-2) < len(pre) or trows*(W-3) < len(tb): continue
            combos.append((L,k,W,IH))
def run(c):
    L,k,W,IH=c
    name="h_%d_%d_%d.man"%(L,k,W)
    r=subprocess.run([sys.executable,"swar_build.py","--geom","%d,%d,%d,%d"%c,"--out",name,"--quiet"],
                     capture_output=True,text=True,cwd=SP)
    src=SP+"/"+name; dst="/tmp/"+name
    if r.returncode!=0 or not os.path.exists(src): return None
    shutil.move(src,dst)
    g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",dst,"--cap","40000"],
                     capture_output=True,text=True,cwd=HERE)
    try: j=json.loads(g.stdout)
    except Exception: return None
    if j.get("passed")!=6: return None
    return (j["score"], j["footprint"]["box"], round(j["avgTicks"],1), L,k,W)
with ThreadPoolExecutor(max_workers=8) as ex:
    res=[r for r in ex.map(run, combos) if r]
res.sort()
for r in res[:8]: print("score=%10.0f box=%4d ticks=%7.1f L=%d k=%d W=%d"%r)
print("passing",len(res),"of",len(combos))
