import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys, os
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# ---------------- Q1: successive r on a FLAT row pull successive input values ----
# Man echoes values: r(v->A) s(send v) repeated on one flat row. Output order == input order?
def build_q1():
    p = lm.Program()
    p.input_room(0, 0)               # I cols0..2
    p.pipe([(1, 3), (1, 4)])         # I down into compute top at col1
    p.room(0, 5, 14, 3)              # compute room interior row6 cols1..12
    p.man(1, 6)
    p.text(2, 6, "rsrsrsrs")         # 4x (read, send)
    p.output_room(0, 9)              # O below
    p.pipe([(1, 8), (1, 7)])         # WRONG dir? need compute -> O (down). place O below room
    return p

# Simpler/correct Q1: I above, O below, both attach compute room; nearest resolves.
def build_q1b():
    p = lm.Program()
    p.input_room(4, 0)
    p.room(0, 4, 16, 3)              # interior row5 cols1..14
    p.pipe([(5, 3), (5, 4)])         # I(4..6) down col5 into room top
    p.output_room(4, 8)              # O below room
    p.pipe([(6, 7), (6, 8)])         # room bottom col6 down into O top
    p.man(1, 5)
    p.text(2, 5, "rsrsrsrs")
    return p

# ---------------- Q2: X-straight-if-zero gate topology test ----------------------
# Verify the PRIMITIVE: A==0 -> straight (no turn); A>0 -> CW; A<0 -> CCW.
# Man walks east; sets A then hits X. Track path.
def build_q2_prim(aop):
    # aop is a string setting A just before X, e.g. '0','1','1N'
    p = lm.Program()
    p.room(0, 0, 12, 7)              # interior cols1..10 rows1..5
    p.man(1, 3)
    p.text(2, 3, aop + "X")          # set A, then X gate on row3
    # after X: straight=east continues row3; CW(from east)=south; CCW=north
    return p

# Q2 crux: try to read n values on a flat row and STOP after exactly n with a
# linear countdown gated by X-straight-if-zero. Countdown c decremented per lane.
# We test the CLAIM. Input: n then n values. Man: reads n into BP(count). Then per
# lane: r(v->A) s(deposit... just send to O to observe) then load countdown and X.
# We test encoding c=count-remaining. Show what actually happens on the oracle.
def build_q2_comb():
    p = lm.Program()
    p.input_room(6, 0)
    p.room(0, 3, 30, 6)             # big flat comb room interior rows4..7 cols1..28
    p.pipe([(7, 2), (7, 3)])        # I down col7 into room top
    p.output_room(0, 11)
    p.pipe([(8, 8), (8, 11)])       # room bottom col8 down into O
    p.man(1, 4)
    # read n -> B (count). We'll gate on A = (B) decremented... but X needs A.
    # Per-lane flat attempt: r(A=v), s(send v), W(A<->B: A=count), then to keep
    # straight we need A==0. Here we just DEMONSTRATE: put A=count and X; count>0
    # so it TURNS every lane (staircase). That's the finding.
    p.text(2, 4, "rM")              # A=n, B=n (count in B)
    # lane pattern along row4: r s W X  (W brings count into A, X gates)
    p.text(4, 4, "rsWX")            # after reading v0: A=count(n)>0 -> X turns CW=south
    return p

if __name__ == '__main__':
    which = sys.argv[1]
    p = {'q1b': build_q1b, 'q2p0': lambda: build_q2_prim('0'),
         'q2p1': lambda: build_q2_prim('1'), 'q2pN': lambda: build_q2_prim('1N'),
         'q2comb': build_q2_comb}[which]()
    out = _REPO + '/scratchpad/q_%s.man' % which
    p.save(out)
    print(p.render())
    print('SAVED', out)
