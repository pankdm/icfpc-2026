import sys
sys.path.insert(0,"solutions/plotter")
import swar_setup as SS
E=SS.Emit
log=[]
of=E.fetch
def fetch(self,name):
    q=[n for n,_ in self.q]
    log.append((name,q.index(name),list(q)))
    return of(self,name)
E.fetch=fetch
e=SS.Emit(3,4,20,19); SS.setup_pre(e)
tot=0
for name,d,q in log:
    tot+=d
    print("%-6s dist=%d  q=%s"%(name,d,q))
print("pre tokens",len(e.toks),"rotations",tot)
