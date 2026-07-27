import json, re, subprocess, sys
HERE="/Users/visenbaev/icfpc26"
P=HERE+"/solutions/plotter/swar_setup.py"
orig=open(P).read()
try:
    for d in range(3, 15):
        open(P,"w").write(re.sub(r"^PRE_DELAY = \d+", "PRE_DELAY = %d"%d, orig, flags=8))
        out="/tmp/dd%d.man"%d
        r=subprocess.run([sys.executable,"swar_build.py","--out",out,"--quiet"],
                         capture_output=True,text=True,cwd=HERE+"/solutions/plotter")
        if r.returncode!=0:
            print(d,"build fail"); continue
        g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",out,"--cap","40000"],
                         capture_output=True,text=True,cwd=HERE)
        j=json.loads(g.stdout)
        print("delay=%2d passed=%d box=%d ticks=%s score=%s"%(d,j["passed"],j["footprint"]["box"],
              round(j["avgTicks"],1) if j.get("avgTicks") else None,
              round(j["score"]) if j.get("score") else None))
finally:
    open(P,"w").write(orig)
