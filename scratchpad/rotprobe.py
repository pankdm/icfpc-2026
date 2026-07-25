"""Probe: load n values onto the compact belt, then do K bare rotations (r;s), halt.
Measures ticks/rotation on the oracle. K passed as literal via BP countdown."""
import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

def build(K):
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x, y)] = ch; p.put(x, y, ch)
    # rooms & pipes (same compact belt geometry as build.py)
    p.room(10, 0, 42, 92)
    p.input_room(33, -5); p.pipe([(34, -2), (34, -1)])
    p.output_room(54, 5); p.pipe([(52, 6), (53, 6)])
    p.room(2, 40, 7, 5)
    p.pipe([(9, 30), (5, 30), (5, 39)])
    p.pipe([(4, 39), (4, 20), (9, 20)])
    C(3, 41, '>'); C(4, 41, '@'); C(5, 41, 'R'); C(6, 41, 's'); C(7, 41, 'v')
    C(7, 42, '<'); C(3, 42, '^')
    # INIT: read n -> BP=n ; enqueue SENT(-1)
    p.man(12, 2); C(13, 2, '>')
    C(34, 2, 'r'); C(35, 2, 'b'); C(36, 2, '1'); C(37, 2, 'N')
    C(38, 2, 'v'); C(38, 3, '<'); C(15, 3, 's')
    C(12, 3, 'v'); C(12, 6, '>')
    # LOADLOOP READ
    C(34, 6, 'r'); C(35, 6, 'v'); C(35, 7, '<'); C(15, 7, 's')
    C(14, 7, 'v'); C(14, 8, 'v')
    C(14, 9, 'r'); C(14, 10, 's'); C(14, 11, 'X')
    C(13, 11, '^'); C(13, 8, '>')
    C(15, 11, 'v'); C(15, 12, 'm'); C(15, 13, 'd')
    C(14, 13, '<'); C(12, 13, '^')
    # after load belt=[v_{n-1}..v_0,SENT], BP=0. read t (discard).
    C(15, 15, '>'); C(34, 15, 'r')
    # set BP=K (rotation count) via literal, then rotate loop
    C(35, 15, 'v'); C(35, 16, '<'); C(15, 16, 'v'); C(15, 17, '>')
    x = 16
    klit = '`%d`' % K
    for ch in klit:
        C(x, 17, ch); x += 1
    C(x, 17, 'b')  # BP=K
    C(x+1, 17, 'v'); C(x+1, 18, '<'); C(14, 18, 'v')
    # ROTATE loop (counter): entry (14,18)v south; r;s;m;d
    C(14, 19, 'r'); C(14, 20, 's'); C(14, 21, 'm'); C(14, 22, 'd')
    # d heading south: BP>0 -> CW=west -> loop up col13 -> east to (14,18)v
    C(13, 22, '^'); C(13, 18, '>')
    # BP==0: straight south to exit -> output & halt
    C(14, 23, 'W'); C(14, 24, '>'); C(45, 24, 's'); C(46, 24, 'H')
    return p

if __name__ == '__main__':
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    p = build(K)
    p.save(_REPO + '/scratchpad/rotprobe.man')
    print('footprint', p.footprint())
