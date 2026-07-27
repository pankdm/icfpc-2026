#!/usr/bin/env python3
import json, subprocess, sys
MAN=sys.argv[1]; CASE=sys.argv[2]; MAX=int(sys.argv[3]); STEP=int(sys.argv[4])
spec=json.load(open("tests/plotter.json"))
case=[t for t in spec["publicTestData"] if t["name"]==CASE][0]
open("/tmp/pf.json","w").write(json.dumps(case["rounds"]))
for n in range(0,MAX+1,STEP):
    r=subprocess.run(["interp/target/release/lm","--inspect=%d"%n,MAN,"--frames-file=/tmp/pf.json","--cap=%d"%(MAX+10)],capture_output=True,text=True)
    try: d=json.loads(r.stdout)
    except Exception: print(n,"ERR",r.stdout[:120],r.stderr[:200]); break
    rs=d.get("runners",d.get("men",[]))
    ps=" ".join("%s"%(x.get("pos") if isinstance(x,dict) else x) for x in rs)
    print(n, ps)
