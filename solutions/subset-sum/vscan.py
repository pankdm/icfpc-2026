"""Minimal validator: LOAD values reversed onto compact belt, then value-scan with a
HARDCODED mask (BP), sum selected values, output the sum. Reuses build.py belt geometry.

belt after LOAD = [v_{n-1}..v_0, SENT].  value-scan: BP=mask, for each item front->back:
 x low bit -> include (add) / exclude, ] shift BP, until SENT. sum in B.
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

def build(mask_lit):
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]} vs {ch}")
        placed[(x, y)] = ch; p.put(x, y, ch)

    # rooms & pipes (from build.py, proven compact belt)
    p.room(10, 0, 42, 92)
    p.input_room(33, -5); p.pipe([(34, -2), (34, -1)])
    p.output_room(54, 5); p.pipe([(52, 6), (53, 6)])
    p.room(2, 40, 7, 5)
    p.pipe([(9, 30), (5, 30), (5, 39)])       # FEED CTRL left row30 -> RELAY
    p.pipe([(4, 39), (4, 20), (9, 20)])       # RETURN RELAY -> CTRL left row20
    C(3, 41, '>'); C(4, 41, '@'); C(5, 41, 'R'); C(6, 41, 's'); C(7, 41, 'v')
    C(7, 42, '<'); C(3, 42, '^')

    # INIT: read n -> BP=n (load counter); SENT=-1 enqueue
    p.man(12, 2); C(13, 2, '>')
    C(34, 2, 'r')     # A=n
    C(35, 2, 'b')     # BP=n
    C(36, 2, '1')     # A=1
    C(37, 2, 'N')     # A=-1 (SENT)
    C(38, 2, 'v'); C(38, 3, '<')
    C(15, 3, 's')     # enqueue SENT
    C(12, 3, 'v'); C(12, 6, '>')

    # LOADLOOP READ
    C(34, 6, 'r')     # A=value
    C(35, 6, 'v'); C(35, 7, '<')
    C(15, 7, 's')     # enqueue value (to back)
    C(14, 7, 'v'); C(14, 8, 'v')
    # ROTATE (prepend: rotate until SENT back to front) r;s;X
    C(14, 9, 'r'); C(14, 10, 's'); C(14, 11, 'X')   # A>0 loop(W), A<0 exit(E)
    C(13, 11, '^'); C(13, 8, '>')
    C(15, 11, 'v'); C(15, 12, 'm'); C(15, 13, 'd')   # DEC BP; BP>0 loop
    C(14, 13, '<'); C(12, 13, '^')                   # loop-read up col12

    # after load: belt=[v_{n-1}..v_0, SENT], BP=0. Read t (discard for this test).
    C(15, 15, '>'); C(34, 15, 'r')   # A=t (unused for this test)
    C(35, 15, 'v'); C(35, 16, '<')   # turn back: down then west along row16 to (15,16)
    # set BP = mask (hardcoded literal), B=0 (sum accumulator)
    C(15, 16, 'v'); C(15, 17, '>')
    x = 16
    for ch in mask_lit:
        C(x, 17, ch); x += 1
    C(x, 17, 'b')      # BP = mask
    C(x+1, 17, '0')    # A=0
    C(x+2, 17, 'M')    # B=0 (sum)
    C(x+3, 17, 'v'); C(x+3, 18, '<'); C(14, 18, 'v')

    # VLOOP: r item; s (re-enqueue); X sign: A>0 value->CW(W)=VAL ; A<0 SENT->CCW(E)=END
    C(14, 19, 'v')     # re-entry
    C(14, 20, 'r'); C(14, 21, 's'); C(14, 22, 'X')
    # VAL (W at 13,22): x low bit: 1->CW(N)=INCLUDE ; 0->CCW(S)=EXCLUDE
    C(13, 22, 'x')
    # INCLUDE (N col13): A=item still in A? after X A=item(value). We re-enqueued already.
    #   add value to sum(B): +, then M(B=sum'), ](BP>>=1), loop back to VLOOP entry.
    C(13, 21, '+')     # A=value+sum
    C(13, 20, 'M')     # B=sum'
    C(13, 19, ']')     # BP>>=1
    C(13, 18, '>'); C(14, 18, 'v')  # loop back (merge into re-entry col14 row18->19)
    # EXCLUDE (S col13): ](BP>>=1), loop back up col12 to (12,18)-> E -> shared (13,18)>
    C(13, 23, ']'); C(13, 24, '<'); C(12, 24, '^'); C(12, 18, '>')
    # END (E at 15,22): sum in B. Move to A and output.
    C(15, 22, 'W')     # A=sum
    C(16, 22, '>'); C(45, 22, 's'); C(46, 22, 'H')
    return p, placed

if __name__ == '__main__':
    mask = sys.argv[1] if len(sys.argv) > 1 else '`12`'
    p, _ = build(mask)
    p.save(_REPO + '/scratchpad/vscan.man')
    print('footprint', p.footprint())
