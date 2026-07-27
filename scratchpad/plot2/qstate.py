import sys
sys.path.insert(0,"solutions/plotter")
import swar_setup as SS
e=SS.Emit(3,4,20,19); SS.setup_pre(e)
print("after pre fifo:", [n for n,_ in e.q], "A", e.A)
