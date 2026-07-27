import sys
sys.path.insert(0,"solutions/plotter")
import swar_setup as SS
E=SS.Emit
log=[]
of=E.fetch
def fetch(self,name):
    q=[n for n,_ in self.q]
    d=q.index(name)
    log.append((name,d,len(q)))
    return of(self,name)
E.fetch=fetch
e=SS.Emit(3,4,20,19); SS.setup(e)
tot=0
for name,d,ql in log:
    tot+=d
    print("%-6s dist=%d qlen=%d"%(name,d,ql))
print("total rotations",tot,"fetches",len(log))
