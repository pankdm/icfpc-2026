import json, re, shutil, subprocess, sys, os, time
HERE="/Users/visenbaev/icfpc26"
P=HERE+"/solutions/plotter/swar_setup.py"
CACHE=HERE+"/solutions/plotter/__pycache__"
orig=open(P).read()
try:
    for d in range(0, 13):
        shutil.rmtree(CACHE, ignore_errors=True)
        open(P,"w").write(re.sub(r"^PRE_DELAY = \d+", "PRE_DELAY = %d"%d, orig, flags=8))
        sys.path.insert(0, HERE+"/solutions/plotter")
        out="/tmp/e%d.man"%d
        r=subprocess.run([sys.executable,"swar_build.py","--out",os.path.basename(out),"--quiet"],
                         capture_output=True,text=True,cwd=HERE+"/solutions/plotter")
        src=HERE+"/solutions/plotter/"+os.path.basename(out)
        if r.returncode!=0 or not os.path.exists(src):
            print(d,"build fail", r.stderr.strip().splitlines()[-1][:60] if r.stderr else ""); continue
        shutil.move(src, out)
        txt=open(out).read()
        dots=max((len(m) for m in re.findall(r"\.{2,}", txt.split("\n")[7])), default=0)
        g=subprocess.run([sys.executable,"tools/grade_fast.py","plotter",out,"--cap","40000"],
                         capture_output=True,text=True,cwd=HERE)
        j=json.loads(g.stdout)
        print("delay=%2d dots_row7=%2d passed=%d ticks=%s score=%s"%(d,dots,j["passed"],
              round(j["avgTicks"],1) if j.get("avgTicks") else None,
              round(j["score"]) if j.get("score") else None))
finally:
    shutil.rmtree(CACHE, ignore_errors=True)
    open(P,"w").write(orig)
