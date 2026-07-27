"""mm2rooms — the six compute rooms of the mm2 matmul engine.

Each function stamps one room at (ox,oy) and returns a Room whose `pipes` dict is
already filled in, plus a `want` map of {cell: (pipe, kind)} that `Room.check()`
verifies -- so a nearest-pipe regression fails the BUILD, not a test case.

Loop order is (i, m, j) with j innermost:  C[i][j] += A[i][m] * B[m][j].
  * A is drained once, in arrival order, each value repeated K times by AREL.
  * B is a ring of M*K values, replayed N times.
  * C is a ring of K accumulators, flushed to the output every M passes.
"""


def mul(g, ox, oy):
    """MUL: 6-op branch-free MAC ring, 10 ticks/MAC.

    ring: * s_PP r_AR | M r_BR s_BF   (entered at '*', so the very first lap
    multiplies 0*0 and emits ONE garbage product -- ACC discards it).
    """
    r = g.room(ox, oy, 8, 4)
    g.text(ox + 1, oy + 1, "@>*srv")
    g.text(ox + 1, oy + 2, " ^srM<")
    r.attach('BF', 'L', oy + 1, 'out')
    r.attach('PP', 'R', oy + 1, 'out')
    r.attach('AR', 'T', ox + 3, 'in')
    r.attach('BR', 'B', ox + 3, 'in')
    r.check({
        (ox + 4, oy + 1): ('PP', 'out'),
        (ox + 3, oy + 2): ('BF', 'out'),
        (ox + 5, oy + 1): ('AR', 'in'),
        (ox + 4, oy + 2): ('BR', 'in'),
    })
    return r


def crel(g, ox, oy):
    """CREL: the C-ring relay (CF in, CR out). One pipe each way, 6 ticks/value."""
    r = g.room(ox, oy, 6, 4)
    g.text(ox + 1, oy + 1, "@>rv")
    g.text(ox + 1, oy + 2, " ^s<")
    r.attach('CF', 'T', ox + 2, 'in')
    r.attach('CR', 'R', oy + 2, 'out')
    return r


def arel(g, ox, oy):
    """AREL: reads N,M,K then emits every A value K times (AP in, AR out)."""
    r = g.room(ox, oy, 10, 9)
    g.text(ox + 1, oy + 1, "@rrrMv")
    g.text(ox + 2, oy + 2, "v...<")
    g.text(ox + 1, oy + 3, ">>rWbWv")
    g.text(ox + 1, oy + 4, ".")
    g.put(ox + 7, oy + 4, '.')
    g.text(ox + 1, oy + 5, ".")
    g.text(ox + 4, oy + 5, "vs<<")
    g.text(ox + 1, oy + 6, ".")
    g.text(ox + 4, oy + 6, ">mav")
    g.text(ox + 1, oy + 7, "^.....<")
    r.attach('AP', 'T', ox + 5, 'in')
    r.attach('AR', 'R', oy + 4, 'out')
    return r


def brel(g, ox, oy):
    """BREL: seeds the B ring from SD (M*K values) then relays BF -> BR forever."""
    r = g.room(ox, oy, 14, 10)
    g.text(ox + 1, oy + 1, "@rrMrv")
    g.text(ox + 3, oy + 2, "vb*<")
    g.text(ox + 3, oy + 3, ".")
    g.text(ox + 3, oy + 4, ">rsv")
    g.text(ox + 2, oy + 5, "vd.m<")
    g.text(ox + 2, oy + 6, ">....v")
    g.text(ox + 7, oy + 7, ">>rv")
    g.text(ox + 8, oy + 8, "^s<")
    r.attach('SD', 'L', oy + 4, 'in')
    r.attach('BF', 'B', ox + 10, 'in')
    r.attach('BR', 'R', oy + 4, 'out')
    r.check({
        (ox + 2, oy + 1): ('SD', 'in'), (ox + 3, oy + 1): ('SD', 'in'),
        (ox + 5, oy + 1): ('SD', 'in'), (ox + 4, oy + 4): ('SD', 'in'),
        (ox + 9, oy + 7): ('BF', 'in'),
    })
    return r


def spl(g, ox, oy):
    """SPL: reads N,M,K, broadcasts them (S), then routes N*M values to AP and
    M*K values to SD."""
    r = g.room(ox, oy, 16, 10)
    g.text(ox + 1, oy + 1, "@rSMrSW*brS*Mv")
    g.text(ox + 1, oy + 2, "v............<")
    g.text(ox + 1, oy + 3, ">>rsv")
    g.text(ox + 1, oy + 4, "vd.m<")
    g.text(ox + 1, oy + 5, ">Wb......v")
    g.text(ox + 10, oy + 6, ">>rsv")
    g.text(ox + 10, oy + 7, "Hd.m<")
    r.attach('AP', 'L', oy + 3, 'out')
    r.attach('SD', 'R', oy + 6, 'out')
    r.attach('CP', 'B', ox + 8, 'out')
    r.attach('IN', 'T', ox + 1, 'in')
    r.check({
        (ox + 4, oy + 3): ('AP', 'out'),
        (ox + 13, oy + 6): ('SD', 'out'),
    })
    return r


def pcnt(g, ox, oy):
    """PCNT: emits the ACC control stream  K,K then forever [K]*(M-1), -K, K."""
    r = g.room(ox, oy, 13, 10)
    g.text(ox + 1, oy + 1, "@r1Mr-Mrssv")
    g.text(ox + 2, oy + 2, "v........<")
    g.text(ox + 2, oy + 3, ">WbWv")
    g.text(ox + 2, oy + 4, "^.v.<")
    g.text(ox + 2, oy + 5, ".")
    g.text(ox + 4, oy + 5, ">sv")
    g.text(ox + 1, oy + 6, "v..dm<")
    g.text(ox + 1, oy + 7, ">..NsNsv")
    g.text(ox + 2, oy + 8, "^.....<")
    r.attach('CP', 'L', oy + 4, 'in')
    r.attach('CTL', 'B', ox + 6, 'out')
    return r


def acc(g, ox, oy):
    """ACC: MAC ring (10 ticks/MAC), output ring, seed ring and the control merge.

    control:  MERGE = r_CTL ; X    ->  A>0 normal (b, back to MAC)
                                       A<0 last   (N, b, into OUT ring)
    """
    r = g.room(ox, oy, 16, 16)
    P = lambda x, y, s: g.text(ox + x, oy + y, s)
    P(3, 1, "v.........<")
    g.put(ox + 3, oy + 2, '.')          # (3,1)v (4..12,1). (13,1)<
    P(4, 2, ">>rm.sv")              # (4,2)> entry ; OUT ring top cols 5..10
    g.put(ox + 13, oy + 2, '.')
    P(1, 3, "v...ds..0<")           # (1,3)v (2,3). (3,3). (4,3). OUT ring bottom
    g.put(ox + 13, oy + 3, '.')
    P(1, 4, ".>..>rMrv")            # MAC ring top cols 5..9
    g.put(ox + 13, oy + 4, '.')
    P(1, 5, "v...dms+<")            # MAC ring bottom
    g.put(ox + 13, oy + 5, 'r')     # r_PP: discard MUL's garbage product
    P(1, 6, "....")
    g.put(ox + 13, oy + 6, '.')
    P(1, 7, "..>.>0sv")             # SEED ring top cols 5..8
    g.put(ox + 13, oy + 7, '.')
    P(1, 8, "v...d.m<")             # SEED ring bottom
    g.put(ox + 13, oy + 8, '.')
    P(1, 9, "..")
    g.put(ox + 4, oy + 9, '.')
    g.put(ox + 13, oy + 9, '.')
    P(1, 10, "..")
    g.put(ox + 4, oy + 10, 'b')
    g.put(ox + 13, oy + 10, '.')
    P(1, 11, "..")
    g.put(ox + 4, oy + 11, 'N')
    g.put(ox + 13, oy + 11, '.')
    P(1, 12, ">.rX")
    g.put(ox + 13, oy + 12, '.')
    P(1, 13, "@.rb........^")
    P(2, 14, "^.<")
    r.attach('CF', 'L', oy + 2, 'out')
    r.attach('OUT', 'R', oy + 2, 'out')
    r.attach('CR', 'L', oy + 5, 'in')
    r.attach('PP', 'R', oy + 5, 'in')
    r.attach('CTL', 'B', ox + 3, 'in')
    r.check({
        (ox + 6, oy + 2): ('CR', 'in'),
        (ox + 6, oy + 4): ('CR', 'in'),
        (ox + 8, oy + 4): ('PP', 'in'),
        (ox + 13, oy + 5): ('PP', 'in'),
        (ox + 3, oy + 12): ('CTL', 'in'),
        (ox + 3, oy + 13): ('CTL', 'in'),
        (ox + 7, oy + 5): ('CF', 'out'),
        (ox + 6, oy + 3): ('CF', 'out'),
        (ox + 7, oy + 7): ('CF', 'out'),
        (ox + 9, oy + 2): ('OUT', 'out'),
    })
    return r
