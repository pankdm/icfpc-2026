import sys
sys.path.insert(0,'/Users/visenbaev/icfpc26/tools')
sys.path.insert(0,'/Users/visenbaev/icfpc26/solutions/brackets')
import littleman as lm
from tightR import blockRT
from tightC import blockCT
from tightM import blockMT
def build(save):
    p=lm.Program()
    blockMT(p,0,0)      # M cols0-11 rows0-20
    blockRT(p,14,0)     # R cols14-21 rows0-10
    blockCT(p,14,13)    # C cols14-20 rows13-25
    p.input_room(24,0)  # I cols24-26 rows0-2
    p.output_room(0,23) # O cols0-2 rows23-25
    p.pipe([(23,1),(22,1)])     # I->R
    p.pipe([(16,11),(16,12)])   # R->C
    p.pipe([(13,18),(12,18)])   # C->M
    p.pipe([(1,21),(1,22)])     # M->O
    print('footprint',p.footprint())
    p.save(save)
build(sys.argv[1] if len(sys.argv)>1 else '/tmp/s5b.man')
