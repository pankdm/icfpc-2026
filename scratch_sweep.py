import sys, os
sys.path.insert(0,'tools')
sys.path.insert(0,'solutions/history-lesson')
import importlib.util
spec = importlib.util.spec_from_file_location("bld","solutions/history-lesson/build.py")
bld = importlib.util.module_from_spec(spec); spec.loader.exec_module(bld)
data = open('solutions/history-lesson/icfp-history.txt','rb').read()
best=[]
for d in range(9,19):
    for k in range(3,9):
        try:
            p,nch,nr = bld.build(data, base=92, maxbytes=10, digit_width=d, offset=31, groups_per_row=k)
            w,h,sc = p.footprint()
            best.append((max(w,h), w,h,sc,d,k,nch,nr))
        except Exception as e:
            pass
best.sort()
for b in best[:20]:
    print(f"maxdim={b[0]:3d}  {b[1]}x{b[2]} score={b[3]:5d}  d={b[4]} k={b[5]} chunks={b[6]} rows={b[7]}")
