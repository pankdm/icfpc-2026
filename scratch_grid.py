import sys, importlib.util, math
sys.path.insert(0,'tools'); sys.path.insert(0,'solutions/history-lesson')
spec = importlib.util.spec_from_file_location("bld","solutions/history-lesson/build.py")
bld = importlib.util.module_from_spec(spec); spec.loader.exec_module(bld)
data = open('solutions/history-lesson/icfp-history.txt','rb').read()
# chunks(d) using base 92, maxbytes large
def chunks_for(d):
    return len(bld.pack_chunks(data, 92, 12, d, store=lambda b: b-31))
res=[]
for d in range(6,19):
    nch = chunks_for(d)
    for k in range(2,12):
        w = k*(d+3)+5
        h = math.ceil(nch/k)+6
        res.append((max(w,h), w, h, d, k, nch))
res.sort()
for r in res[:15]:
    print(f"maxdim={r[0]:3d} {r[1]}x{r[2]} d={r[3]} k={r[4]} chunks={r[5]} score={r[0]**2}")
