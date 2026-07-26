import json
d=json.load(open('/Users/visenbaev/icfpc26/scratchpad/newprobs/little-little-little-man.json'))
P=d['publicTestData']
HEX="0123456789abcdef"
DXY={0:(0,-1),1:(1,0),2:(0,1),3:(-1,0)}

def build(grid, W, H):
    wall=[[False]*W for _ in range(H)]
    corners=[(x,y) for y in range(H) for x in range(W) if grid[y][x]=='+']
    xs=[x for x,y in corners]; ys=[y for x,y in corners]
    x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
    for x in range(x0,x1+1):
        wall[y0][x]=True; wall[y1][x]=True
    for y in range(y0,y1+1):
        wall[y][x0]=True; wall[y][x1]=True
    return wall

def render(grid,W,H,wall,mx,my):
    buf=[[0]*16 for _ in range(16)]
    for y in range(min(H,16)):
        for x in range(min(W,16)):
            ch=grid[y][x]
            if wall[y][x]: col=4
            elif ch in '<>^vXH': col=3
            elif ch in '0123456789': col=8
            elif ch=='M': col=12
            elif ch in '+-': col=10
            else: col=0
            buf[y][x]=col
    if 0<=my<16 and 0<=mx<16: buf[my][mx]=9
    return buf

def step(grid,W,H,wall,st,WALL_MODE):
    x,y,head,A,B,halted=st
    if halted: return st
    ch=grid[y][x]
    if ch=='^': head=0
    elif ch=='>': head=1
    elif ch=='v': head=2
    elif ch=='<': head=3
    elif ch in '0123456789': A=int(ch)
    elif ch=='M': B=A
    elif ch=='+': A=A+B
    elif ch=='-': A=A-B
    elif ch=='X':
        if A>0: head=(head+1)%4
        elif A<0: head=(head-1)%4
    elif ch=='H': return [x,y,head,A,B,True]
    dx,dy=DXY[head]; nx,ny=x+dx,y+dy
    if 0<=nx<W and 0<=ny<H and wall[ny][nx]:
        if WALL_MODE=='onto': return [nx,ny,head,A,B,True]
        else: return [x,y,head,A,B,True]
    return [nx,ny,head,A,B,halted]

def run_case(c,DEFAULT_HEAD,WALL_MODE,VERBOSE=False):
    r0=c['rounds'][0]
    W=int(r0['in'][0]);H=int(r0['in'][1])
    vals=[int(v) for v in r0['in'][2:]]
    grid=[[chr(vals[yy*W+xx]) for xx in range(W)] for yy in range(H)]
    wall=build(grid,W,H)
    for yy in range(H):
        for xx in range(W):
            if grid[yy][xx]=='@': mx,my=xx,yy
    st=[mx,my,DEFAULT_HEAD,0,0,False]
    results=[]
    for ri,rnd in enumerate(c['rounds']):
        if ri>0:
            k=int(rnd['in'][0])
            for _ in range(k):
                if st[5]: break
                st=step(grid,W,H,wall,st,WALL_MODE)
        buf=render(grid,W,H,wall,st[0],st[1])
        got=[''.join(HEX[buf[yy][xx]] for xx in range(16)) for yy in range(16)]
        exp=rnd['frames'][0]
        results.append(got==exp)
        if got!=exp and VERBOSE:
            print('  case',c['name'],'round',ri,'MISMATCH st=',st)
            for a,b in zip(got,exp):
                print('   got',a,'exp',b,'' if a==b else '  <--')
            break
    return results

for DEFAULT_HEAD in [1,0,2,3]:
    for WALL_MODE in ['onto','stay']:
        allok=True; total=0; passed=0
        for c in P:
            res=run_case(c,DEFAULT_HEAD,WALL_MODE)
            total+=len(res); passed+=sum(res)
            if not all(res): allok=False
        print(f"DEFAULT_HEAD={DEFAULT_HEAD} WALL={WALL_MODE}: {passed}/{total}  {'ALL OK' if allok else ''}")

print("=== scale ===")
DEFAULT_HEAD=1; WALL_MODE='onto'
maxk=0; maxticks=0; maxgrid=0
for c in P:
    r0=c['rounds'][0]
    W=int(r0['in'][0]);H=int(r0['in'][1])
    vals=[int(v) for v in r0['in'][2:]]
    grid=[[chr(vals[yy*W+xx]) for xx in range(W)] for yy in range(H)]
    wall=build(grid,W,H)
    for yy in range(H):
        for xx in range(W):
            if grid[yy][xx]=='@': mx,my=xx,yy
    st=[mx,my,DEFAULT_HEAD,0,0,False]
    ks=[]; tot=0
    for ri,rnd in enumerate(c['rounds']):
        if ri>0:
            k=int(rnd['in'][0]); ks.append(k)
            for _ in range(k):
                if st[5]: break
                st=step(grid,W,H,wall,st,WALL_MODE); tot+=1
    maxk=max(maxk,max(ks) if ks else 0); maxticks=max(maxticks,tot); maxgrid=max(maxgrid,W*H)
    print(f"{c['name']:20s} W{W}xH{H}={W*H:3d} rounds{len(c['rounds']):3d} ks={ks} totticks={tot}")
print("MAX k=",maxk,"maxticks=",maxticks,"maxgrid=",maxgrid)
