import sys, os, subprocess, json
sys.path.insert(0,'/Users/dmitrykorolev/projects/icfpc-2026-main')
sys.path.insert(0,'/Users/dmitrykorolev/projects/icfpc-2026-main/scratchpad/llmfork')
import build_rig as B
LM='/Users/dmitrykorolev/projects/icfpc-2026-main/interp/target/release/lm'
def run(p, n):
    path=f'/tmp/rig_{n}.man'; p.save(path)
    o=subprocess.run([LM,'--grade',path,f'--input={n}',f'--expected={7*n}'],capture_output=True,text=True)
    return json.loads(o.stdout)
print(f"{'pipeLen':>7} {'RTT~':>5} | {'serial':>8} {'fork':>8} {'dep':>8} | {'ser/txn':>8} {'fork/txn':>8} {'dep/txn':>8} {'speedup':>8} {'dep vs ser':>10}")
for L in (10, 20, 42, 84, 168):
    B.PIPE_LEN = L
    B.RAMX = B.MXE + 1 + L
    row=[]
    for fn in (B.build_serial, B.build_fork, B.build_dep):
        p=fn(); a=run(p,50); b=run(p,200)
        assert a['status']=='pass' and b['status']=='pass', (fn.__name__, L, a, b)
        row.append((b['settleTick'], (b['settleTick']-a['settleTick'])/150.0))
    print(f"{L:>7} {2*L:>5} | {row[0][0]:>8} {row[1][0]:>8} {row[2][0]:>8} | "
          f"{row[0][1]:>8.1f} {row[1][1]:>8.1f} {row[2][1]:>8.1f} "
          f"{row[0][1]/row[1][1]:>7.2f}x {row[0][1]/row[2][1]:>9.2f}x")
