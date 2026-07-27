import sys
sys.path.insert(0,'/Users/visenbaev/icfpc26/scratchpad/brk5')
sys.path.insert(0,'/Users/visenbaev/icfpc26/solutions/brackets')
import brk5_asm as A, p6_build as REF
rows = ["vs< 0aqsN}<", "@vX5MUbm] x", ">U^ 0dqs} <"]
C_CELLS=[]; man=None
for j,r in enumerate(rows):
    for i,ch in enumerate(r):
        if ch==' ': continue
        if ch=='@': man=(i+1,j+1); continue
        C_CELLS.append((i+1,j+1,ch))
print('C cells',len(C_CELLS),'man',man,'span x',min(c[0] for c in C_CELLS),max(c[0] for c in C_CELLS),'y',min(c[1] for c in C_CELLS),max(c[1] for c in C_CELLS))
C=(13,5,C_CELLS,man)
for Mw in (11,10):
    M=(Mw,REF.M9_H,REF.M9_CELLS,REF.M9_MAN)
    try:
        fp=A.assemble(M=M,C=C,cx=3,io=((0,11),(Mw+3,8)),save=f'/tmp/brk5_M{Mw}.man',verbose=False)
        print(f'  M_w={Mw} -> {fp[0]}x{fp[1]} box {fp[2]}')
    except Exception as e: print(f'  M_w={Mw} -> {type(e).__name__}: {str(e)[:70]}')
