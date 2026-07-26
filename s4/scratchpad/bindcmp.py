import sys, os
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','tools'))
import pipecheck
def snap(f):
    rows=open(f).read().split('\n')
    w=max(len(r) for r in rows); rows=[r.ljust(w) for r in rows]
    t=pipecheck.analyze(rows)
    assert t.get('type')=='analysis', t
    inc,out=pipecheck.attachments(t); rooms=t['rooms']
    order={};role=[]
    for r in rooms:
        (x0,y0),(x1,y1)=tuple(r['min']),tuple(r['max']); k=(x1-x0+1,y1-y0+1)
        order[k]=order.get(k,0)+1; role.append(f"{k[0]}x{k[1]}#{order[k]}")
    def room_of(x,y):
        for i,r in enumerate(rooms):
            (x0,y0),(x1,y1)=tuple(r['min']),tuple(r['max'])
            if x0<x<x1 and y0<y<y1: return i
    res={}
    for y,row in enumerate(rows):
        for x,ch in enumerate(row):
            if ch not in 'rs': continue
            ri=room_of(x,y)
            if ri is None or ri==0: continue
            pi=pipecheck.bind((x,y),(out if ch=='s' else inc).get(ri,[]))
            (rx,ry)=tuple(rooms[ri]['min']); pp=t['pipes'][pi]
            other=pp.get('dst') if ch=='s' else pp.get('src')
            res[(role[ri],x-rx,y-ry,ch)]='ctrl' if other==0 else ('display' if other==-1 else role[other])
    dangling=[i for i,p in enumerate(t['pipes']) if p.get('src') in (None,-1) or p.get('dst') in (None,)]
    return res,[len(p['path']) for p in t['pipes']],dangling
a,la,da=snap(sys.argv[1]); b,lb,db=snap(sys.argv[2])
bad=[(k,a.get(k),b.get(k)) for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]
print("service binding diffs:",len(bad))
for r in bad: print("  ",r)
print("ref pipe lens ",sorted(la)); print("new pipe lens ",sorted(lb))
print("ref dangling",da,"new dangling",db)
