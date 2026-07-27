import sys
sys.path.insert(0,"solutions/plotter")
import swar_setup as SS
E=SS.Emit
rots={"n":0}
orig=E.rot
def rot(self):
    rots["n"]+=1
    return orig(self)
E.rot=rot
e=SS.Emit(3,4,20,19); SS.setup(e)
print("tokens",len(e.toks),"rotations",rots["n"],"rot cost ops",2*rots["n"])
rots["n"]=0
e=SS.Emit(4,3,19,20); SS.setup(e)
print("y-major tokens",len(e.toks),"rotations",rots["n"])
