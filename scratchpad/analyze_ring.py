import sys, os
sys.path.insert(0, "solutions/plotter")
sys.path.insert(0, "tools")
import dsl
from verify_gate import SETUP1

# Reconstruct the access sequence (list of slot names accessed via tf) for a given
# op list, by re-simulating the _C ring logic. We need the SEQUENCE of tf targets.
# But SETUP1/BODY are already flattened op lists. Instead, instrument _C.

LAYOUT = dsl.LAYOUT

# Instrument: capture (target, kind) sequence by re-running build_setup/build_body
# with a recording _C.
class RecC:
    def __init__(self, ring):
        self.ring = list(ring); self.ops=[]; self.seq=[]
    def e(self,*o): self.ops.extend(o)
    def rot(self): self.e('r','s'); self.ring.append(self.ring.pop(0))
    def tf(self,n):
        c=0
        while self.ring[0]!=n: self.rot(); c+=1
        self.seq.append((n,c))
    def readA(self,n):
        self.tf(n); self.e('r','s'); self.ring.append(self.ring.pop(0))
    def writeA(self,n):
        self.e('M'); self.tf(n); self.e('r','W','s'); self.ring.append(self.ring.pop(0))
    def setB(self,k): self.e('M',('#',k),'W')
    def inc(self): self.e('M',('#',1),'+')
    def sign(self): self.setB(63); self.e('}')
    def binop(self,X,Y,o): self.readA(Y); self.e('M'); self.readA(X); self.e(o)

# We need the raw access order. Re-derive from source by copying build_setup/build_body bodies.
# Instead, extract by running the actual functions but with RecC. Monkeypatch dsl._C.
import types
orig = dsl._C
dsl._C = RecC
# build_setup uses c=_C() with default ring LAYOUT
# But RecC needs ring arg. Patch: make RecC() default.
class RecC2(RecC):
    def __init__(self): super().__init__(LAYOUT)
dsl._C = RecC2

# Re-exec build_setup and build_body to get seq
import importlib
# build_setup returns ops; but we want the recorder. Rebuild:
c = RecC2(); 
# replicate build_setup body isn't accessible cleanly. Instead call dsl.build_setup which creates its own _C.
# We overrode dsl._C so build_setup uses RecC2. But it returns c.ops, not c. We need the seq.
# Patch build_setup to stash the c. Easiest: re-run the function source via calling and capturing via a global.
seqs={}
_realC=RecC2
class Capturing(RecC2):
    def __init__(self):
        super().__init__()
        seqs.setdefault('last',[])
    # override tf to also append to a shared last-created list
dsl._C = RecC2
# Instead, just replicate: patch so each instance registers itself.
instances=[]
class TrackC(RecC2):
    def __init__(self):
        super().__init__(); instances.append(self)
dsl._C = TrackC

s_ops = dsl.build_setup(); setup_c = instances[-1]
b_ops = dsl.build_body(); body_c = instances[-1]

print("SETUP access seq (name,rot):")
print(setup_c.seq)
print("total setup rot:", sum(c for _,c in setup_c.seq), "accesses:", len(setup_c.seq))
print()
print("BODY access seq (name,rot):")
print(body_c.seq)
print("total body rot:", sum(c for _,c in body_c.seq), "accesses:", len(body_c.seq))
print()
print("len(SETUP1)=",len(SETUP1),"len(BODY)=",len(dsl.BODY),"len(INIT)=",len(dsl.INIT))
