import sys; sys.path.insert(0,'/Users/visenbaev/icfpc26/tools'); import littleman as lm
sys.path.insert(0,'/Users/visenbaev/icfpc26/solutions/brackets')
from build import blockR, blockC, blockM

def build(save):
    p=lm.Program()
    # R,C,M stacked vertically (internals byte-identical); I beside R, O beside M
    R=blockR(p,0,0)     # rows0-5, cols0-23
    C=blockC(p,0,8)     # rows8-15, cols0-35
    M=blockM(p,0,18)    # rows18-36, cols0-23
    p.input_room(26,1)  # I cols26-28 rows1-3 (beside R)
    p.output_room(28,30)# O cols26-28 rows30-32 (beside M)
    p.pipe([(25,2),(24,2)])   # I -> R (west into R right border)
    p.pipe([(1,6),(1,7)])     # R bottom -> C top
    p.pipe([(1,16),(1,17)])   # C bottom -> M top
    p.pipe([(26,31),(27,31)]) # M -> O (east into O left border, M border col25)
    p.save(save)
    print('footprint',p.footprint())
build(sys.argv[1] if len(sys.argv)>1 else '/tmp/stack3.man')
