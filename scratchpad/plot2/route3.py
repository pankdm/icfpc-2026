import itertools, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE="/Users/visenbaev/icfpc26"; SP=HERE+"/solutions/plotter"
combos=list(itertools.product([2],[2],[2,3],range(0,16),[0,1,2,3]))
def run(c):
    gap,swap,atoff,zig,swcol=c
    name="q_%d%d%d%d%d.man"%(gap,swap,atoff,zig,swcol)
    r=subprocess.run([sys.executable,"swar_build.py","--gap",str(gap),"--swap-rows",str(swap),
                      "--atoff",str(atoff),"--zig",str(zig),"--swcol",str(swcol),
                      "--out",name,"--quiet"],capture_output=True,text=True,cwd=SP)
    src=SP+"/"+name; dst="/tmp/"+name
    if r.returncode!=0 or not os.path.exists(src): return None
    shutil.move(src,dst)
    g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",dst,"--cap","40000"],
                     capture_output=True,text=True,cwd=HERE)
    try: j=json.loads(g.stdout)
    except Exception: return None
    if j.get("passed")!=6: return (None, [r2.get("reason") for r2 in j["results"]][:1], c)
    return (j["score"], j["footprint"]["box"], round(j["avgTicks"],1), gap,swap,atoff,zig,swcol)
with ThreadPoolExecutor(max_workers=8) as ex:
    out=[r for r in ex.map(run, combos) if r]
ok=[r for r in out if r[0] is not None]; bad=[r for r in out if r[0] is None]
ok.sort()
for r in ok[:6]:
    print("score=%10.0f box=%4d ticks=%7.1f gap=%d swap=%d atoff=%d zig=%2d swcol=%d"%r)
print("passing",len(ok),"of",len(combos))
seen=set()
for b in bad:
    k=str(b[1])
    if k not in seen: seen.add(k); print("FAIL", b[1], b[2])
