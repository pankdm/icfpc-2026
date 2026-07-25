import sys
sys.path.insert(0,'/Users/visenbaev/icfpc26/tools')
sys.path.insert(0,'/Users/visenbaev/icfpc26/solutions/brackets')
import littleman as lm
from tightR import blockRT
from tightC import blockCT
from tightM import blockMT
def build(save):
    p=lm.Program()
    blockRT(p,0,5)      # R cols0-7 rows5-15
    blockCT(p,0,18)     # C cols0-6 rows18-30
    blockMT(p,10,3)     # M cols10-21 rows3-23
    p.input_room(0,0)   # I cols0-2 rows0-2
    p.output_room(24,3) # O cols24-26 rows3-5
    p.pipe([(1,3),(1,4)])              # I -> R
    p.pipe([(2,16),(2,17)])            # R -> C  (R bottom row15 -> C top row18)
    p.pipe([(7,22),(9,22)])            # C -> M  (C right col6 -> M left col10)
    p.pipe([(22,4),(23,4)])            # M -> O
    print('footprint',p.footprint())
    p.save(save)
build(sys.argv[1] if len(sys.argv)>1 else '/tmp/s5.man')
