"""Fuzz: random well-formed LLLM programs vs the op-stream VM, checked against a
spec-faithful reference (i64-wrapping). Validates genericity for hidden cases."""
import sys, random
import os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from vm import VM
import importlib
B = importlib.import_module(__import__('os').environ.get('LLLM_MOD','lllm_build'))
PRESERVE = __import__('os').environ.get('LLLM_MOD','lllm_build') != 'lllm_build'

MASK=(1<<64)-1
def s64(v):
    v&=MASK
    return v-(1<<64) if v&(1<<63) else v
HEX="0123456789abcdef"
DXY={0:(0,-1),1:(1,0),2:(0,1),3:(-1,0)}  # N,E,S,W

def gen_program(rng):
    W=rng.randint(4,16); H=rng.randint(4,16)
    g=[[' ']*W for _ in range(H)]
    # border walls
    for x in range(W):
        g[0][x]='-'; g[H-1][x]='-'
    for y in range(H):
        g[y][0]='|'; g[y][W-1]='|'
    for (cx,cy) in [(0,0),(W-1,0),(0,H-1),(W-1,H-1)]:
        g[cy][cx]='+'
    # interior
    ops=list('^>v<0123456789M+-XH')
    interior=[(x,y) for y in range(1,H-1) for x in range(1,W-1)]
    # place @ once
    mx,my=rng.choice(interior)
    for (x,y) in interior:
        if (x,y)==(mx,my): g[y][x]='@'
        else:
            r=rng.random()
            g[y][x]=' ' if r<0.35 else rng.choice(ops)
    return W,H,g

def ref_frames(W,H,g,ks):
    def border(x,y): return x==0 or x==W-1 or y==0 or y==H-1
    def color(x,y,mx,my):
        if x==mx and y==my: return 9
        ch=g[y][x]
        if border(x,y): return 4
        if ch in '<>^vXH': return 3
        if ch in '0123456789': return 8
        if ch=='M': return 12
        if ch in '+-': return 10
        return 0
    for y in range(H):
        for x in range(W):
            if g[y][x]=='@': mx,my=x,y
    head=1; A=0; Bb=0; hlt=False
    def frame(mx,my):
        buf=[[0]*16 for _ in range(16)]
        for y in range(min(H,16)):
            for x in range(min(W,16)):
                buf[y][x]=color(x,y,mx,my)
        return [''.join(HEX[buf[y][x]] for x in range(16)) for y in range(16)]
    frames=[frame(mx,my)]
    for k in ks:
        for _ in range(k):
            if hlt: break
            ch=g[my][mx]
            if ch=='^':head=0
            elif ch=='>':head=1
            elif ch=='v':head=2
            elif ch=='<':head=3
            elif ch in '0123456789':A=int(ch)
            elif ch=='M':Bb=A
            elif ch=='+':A=s64(A+Bb)
            elif ch=='-':A=s64(A-Bb)
            elif ch=='X':
                if A>0: head=(head+1)%4
                elif A<0: head=(head-1)%4
            elif ch=='H': hlt=True; break
            dx,dy=DXY[head]; nx,ny=mx+dx,my+dy
            if border(nx,ny): mx,my=nx,ny; hlt=True
            else: mx,my=nx,ny
        frames.append(frame(mx,my))
    return frames

def run_vm(W,H,g,ks,ops):
    asc=[ord(g[y][x]) for y in range(H) for x in range(W)]
    inputs=[W,H]+asc+list(ks)
    vm=VM(inputs, swap_preserve=PRESERVE)
    vm.run(ops, max_ticks=60_000_000)
    return [[''.join(HEX[f[y*16+x]] for x in range(16)) for y in range(16)] for f in vm.frames]

def main():
    ops=B.build()
    rng=random.Random(int(sys.argv[2]) if len(sys.argv)>2 else 1234)
    N=int(sys.argv[1]) if len(sys.argv)>1 else 200
    bad=0
    for t in range(N):
        W,H,g=gen_program(rng)
        nrounds=rng.randint(1,20)
        ks=[rng.randint(1,64) for _ in range(nrounds)]
        exp=ref_frames(W,H,g,ks)
        got=run_vm(W,H,g,ks,ops)
        if got!=exp:
            bad+=1
            print(f"FUZZ FAIL t={t} W{W}xH{H} ks={ks}")
            for fi in range(max(len(got),len(exp))):
                ge=got[fi] if fi<len(got) else None
                ee=exp[fi] if fi<len(exp) else None
                if ge!=ee:
                    print(" first bad frame",fi)
                    for a,b in zip(ge or [],ee or []):
                        print("  got",a,"exp",b,"" if a==b else "<--")
                    break
            # dump program
            for row in g: print("  |"+''.join(row)+"|")
            if bad>=3: break
    print(f"FUZZ: {N-bad}/{N} programs OK" if bad==0 else f"FUZZ: {bad} FAILURES out of {N}")

if __name__=='__main__':
    main()
