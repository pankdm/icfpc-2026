import json, os, subprocess, sys
HERE="/Users/visenbaev/icfpc26"
sys.path.insert(0, HERE+"/solutions/plotter")
import swar_build as B, swar_setup as SS
pre,px,py,tb,tf=SS.segments()
BW=max(len(px),len(py))+2
print("npre",len(pre),"ntail",len(tb),"BW",BW,"fin",len(tf))
res=[]
for L in range(5,10):
    IH=B.ih_of(L)
    for k in range(3,L-1,2):
        trows=L-k-1
        if trows<1: continue
        for W in range(BW+8,70):
            pre_cap=(W-3)+(k-1)*(W-BW-3)+(W-BW-2)
            tail_cap=trows*(W-3)
            if pre_cap<len(pre) or tail_cap<len(tb): continue
            out="/tmp/g_%d_%d_%d.man"%(L,k,W)
            r=subprocess.run([sys.executable,"swar_build.py","--geom","%d,%d,%d,%d"%(L,k,W,IH),
                              "--out",out,"--quiet"],capture_output=True,text=True,cwd=HERE+"/solutions/plotter")
            if r.returncode!=0: continue
            g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",out],
                             capture_output=True,text=True,cwd=HERE)
            try: j=json.loads(g.stdout)
            except Exception: continue
            if j.get("passed")!=6: continue
            res.append((j["score"],j["footprint"]["box"],round(j["avgTicks"],1),L,k,W))
res.sort()
for r in res[:10]: print("score=%10.0f box=%4d ticks=%7.1f L=%d k=%d W=%d"%r)
print("passing",len(res))
