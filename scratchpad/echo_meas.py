import sys,subprocess,tempfile
sys.path.insert(0,'tools'); import littleman as lm

def build_echo(W):
    p=lm.Program(); P=p.put
    p.room(0,5,W,4)                       # interior rows6,7 cols1..W-2
    P(1,6,'>');P(2,6,'@');P(3,6,'R');P(4,6,'s')
    rc=W-2
    P(rc,6,'v');P(rc,7,'<');P(1,7,'^')
    p.input_room(2,0); p.pipe([(3,3),(3,4)])   # feed into col3 (R) top
    p.output_room(W+2,5); p.pipe([(W,6),(W+1,6)])
    return p

def measure(W,N=16):
    p=build_echo(W); src=p.render()
    with tempfile.NamedTemporaryFile('w',suffix='.man',delete=False) as f:
        f.write(src); tmp=f.name
    inp=str(N)+" "+" ".join(str(i) for i in range(1,N+1))
    exp=inp
    out=subprocess.run(['./interp/target/release/lm','--grade',tmp,f'--input={inp}',f'--expected={exp}'],capture_output=True,text=True)
    return src,out.stdout.strip().splitlines()[-1]

for W in [7,8,10,14]:
    src,r=measure(W)
    print(f"W={W}: {r}")
    if W==7: print(src)
