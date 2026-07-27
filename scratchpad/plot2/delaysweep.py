import json, os, subprocess, sys
HERE="/Users/visenbaev/icfpc26"
sys.path.insert(0, HERE+"/solutions/plotter")
for d in range(0, 30, 2):
    src=open(HERE+"/solutions/plotter/swar_setup.py").read()
    open(HERE+"/solutions/plotter/swar_setup.py","w").write(
        __import__("re").sub(r"^PRE_DELAY = \d+", "PRE_DELAY = %d"%d, src, flags=8))
    out="/tmp/pd%d.man"%d
    r=subprocess.run([sys.executable,"swar_build.py","--out",out,"--quiet"],
                     capture_output=True,text=True,cwd=HERE+"/solutions/plotter")
    if r.returncode!=0:
        print(d,"BUILD FAIL",r.stderr.strip().splitlines()[-1][:90]); continue
    g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",out],
                     capture_output=True,text=True,cwd=HERE)
    try: j=json.loads(g.stdout)
    except Exception: print(d,"grade err"); continue
    print("delay=%2d passed=%d box=%s ticks=%s"%(d,j.get("passed"),j["footprint"]["box"],
          round(j["avgTicks"],1) if j.get("avgTicks") else None))
