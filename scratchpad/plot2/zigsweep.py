import itertools, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE="/Users/visenbaev/icfpc26"; SP=HERE+"/solutions/plotter"
combos=[(z,d,sc) for z in range(0,8) for d in range(10,22) for sc in (1,2)]
def run(c):
    z,d,sc=c
    name="z_%d_%d_%d.man"%(z,d,sc)
    r=subprocess.run([sys.executable,"swar_build.py","--zig",str(z),"--dzig",str(d),
                      "--swcol",str(sc),"--out",name,"--quiet"],capture_output=True,text=True,cwd=SP)
    src=SP+"/"+name; dst="/tmp/"+name
    if r.returncode!=0 or not os.path.exists(src): return None
    shutil.move(src,dst)
    g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",dst,"--cap","40000"],
                     capture_output=True,text=True,cwd=HERE)
    try: j=json.loads(g.stdout)
    except Exception: return None
    if j.get("passed")!=6: return None
    return (j["score"], j["footprint"]["box"], round(j["avgTicks"],1), z,d,sc)
with ThreadPoolExecutor(max_workers=8) as ex:
    res=[r for r in ex.map(run, combos) if r]
res.sort()
for r in res[:10]: print("score=%10.0f box=%4d ticks=%7.1f zig=%d dzig=%2d swcol=%d"%r)
print("passing",len(res),"of",len(combos))
