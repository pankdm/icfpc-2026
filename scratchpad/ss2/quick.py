"""Grade a subset-sum .man case-by-case with the Rust engine, cheapest first,
printing each verdict as it lands so a break shows up in seconds not minutes."""
import json, subprocess, sys, time, os
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LM=os.path.join(ROOT,'interp/target/release/lm')
man=sys.argv[1]; only=sys.argv[2] if len(sys.argv)>2 else None
d=json.load(open(os.path.join(ROOT,'tests/subset-sum.json')))
cases=d['publicTestData']
tot=0.0; n=0
for c in cases:
    if only and only not in c['name']: continue
    inp=" / ".join(" ".join(r['in']) for r in c['rounds'])
    exp=" / ".join(" ".join(r.get('out') or []) for r in c['rounds'])
    t=time.time()
    p=subprocess.run([LM,'--grade',man,'--input='+inp,'--expected='+exp,'--cap=15000000'],
                     capture_output=True,text=True)
    try: r=json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: r={'status':'ERR','raw':p.stdout[:120]}
    print("%-32s %-8s tick=%-9s %.0fs"%(c['name'],r.get('status'),r.get('settleTick'),time.time()-t),flush=True)
    if r.get('status')=='pass': tot+=r['settleTick']; n+=1
    else: print("  FAIL", r); 
print("passed %d  avgTicks %.1f"%(n, tot/max(n,1)))
