import glob, json, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor as ProcessPoolExecutor
HERE="/Users/visenbaev/icfpc26"
def g(f):
    p=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",f,"--cap","30000"],
                     capture_output=True,text=True,cwd=HERE)
    try: j=json.loads(p.stdout)
    except Exception: return None
    if j.get("passed")!=6: return None
    return (j["score"], j["footprint"]["box"], round(j["avgTicks"],1), os.path.basename(f))
files=sorted(glob.glob("/tmp/g_*.man"))
with ProcessPoolExecutor(max_workers=8) as ex:
    res=[r for r in ex.map(g, files) if r]
res.sort()
for r in res[:12]: print("score=%10.0f box=%4d ticks=%7.1f %s"%r)
print("passing",len(res),"of",len(files))
