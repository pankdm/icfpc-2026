"""p3rooms — glue rooms for the P=2 matmul: two UNMODIFIED dense engines, fed by
a splitter front-end and joined by an ordered merger.

  I -> BC ---A---> ADMX ---> FE1 -> ENGINE1 -> MRG.O1
          `--B---> BDUP -/ `-> FE2 -> ENGINE2 -> MRG.O2
          `--hdr--> FE1, FE2                     MCTLC -> MRG.MC
  ADMX -S-> MCTLA (control for its own demux) and MCTLC (control for MRG)

Each engine is `solutions/matmul/build_dense.py` with the I/O rooms replaced by
ports, i.e. an ordinary single-engine matmul.  Engine i is handed a SMALLER
problem: N1 = ceil(N/2) rows for engine 1, N2 = floor(N/2) + 1 for engine 2
(the +1 is a phantom all-zero row, which makes N2 >= 1 even when N == 1 -- a
dense engine with N = 0 deadlocks on its first `r`).  The phantom row is the
LAST row engine 2 computes, so MRG simply never reads it.

WHY THIS SHAPE: pipes cannot cross, so the netlist must be planar.  A single
shared B ring chained MUL1->MUL2, with SPL feeding BREL/PCNT/MCTL, contains a
K(3,3) minor and is provably unroutable (the PathFinder router confirmed it,
stalling at ~700 permanently contended cells).  This decomposition is planar:
{BC, ADMX, BDUP} x {FE1, FE2} is K(3,2), everything else is face-local.
"""


def bcst(g, ox, oy):
    """BC: reads N,M,K and S-broadcasts them, then routes N*M A values to OA and
    every remaining (B) value to OB.  w=17 h=11."""
    r = g.room(ox, oy, 17, 11)
    g.text(ox + 1, oy + 1, "@>rSMrS*brS")
    g.put(ox + 12, oy + 1, 'v')
    g.put(ox + 2, oy + 2, 'v')
    for x in range(ox + 3, ox + 12):
        g.put(x, oy + 2, '.')
    g.put(ox + 12, oy + 2, '<')
    g.text(ox + 2, oy + 3, ">rs.v")
    g.text(ox + 2, oy + 4, "dm..<")
    g.put(ox + 1, oy + 4, 'v')
    g.put(ox + 1, oy + 5, '.')
    g.put(ox + 1, oy + 6, '.')
    g.put(ox + 1, oy + 7, '>')
    g.text(ox + 2, oy + 7, ">rsv")
    g.text(ox + 2, oy + 8, "^..<")
    r.attach('IN', 'T', ox + 8, 'in')
    r.attach('OA', 'T', ox + 1, 'out')      # -> ADMX (A stream)
    r.attach('OB', 'B', ox + 1, 'out')      # -> BDUP (B stream)
    r.attach('OH1', 'R', oy + 1, 'out')     # -> FE1 header
    r.attach('OH2', 'R', oy + 3, 'out')     # -> FE2 header
    r.check({(ox + 4, oy + 3): ('OA', 'out'), (ox + 4, oy + 7): ('OB', 'out'),
             (ox + 3, oy + 1): ('IN', 'in')})
    return r


def bdup2(g, ox, oy):
    """BDUP: swallow the N,M,K header then S-relay every B value to both FEs."""
    r = g.room(ox, oy, 8, 6)
    g.text(ox + 1, oy + 1, "@>rrrv")
    g.put(ox + 2, oy + 2, 'v')
    for x in range(ox + 3, ox + 6):
        g.put(x, oy + 2, '.')
    g.put(ox + 6, oy + 2, '<')
    g.text(ox + 2, oy + 3, ">rSv")
    g.text(ox + 2, oy + 4, "^..<")
    r.attach('BI', 'T', ox + 3, 'in')
    r.attach('BO1', 'L', oy + 1, 'out')
    r.attach('BO2', 'B', ox + 3, 'out')
    return r


def mctl3(g, ox, oy, pick, term, side_in=None, side_out=None):
    """Emit +V,-V,... exactly N times (V = M for pick='M', K for pick='K').
    With term=True a final 0 token follows (ADMX's switch to the phantom row)."""
    side_in = side_in or ('L', oy + 1)
    side_out = side_out or ('R', oy + 3)
    r = g.room(ox, oy, 11, 7)
    pro = "@>rbrr" if pick == 'K' else "@>rbrMrW"
    g.text(ox + 1, oy + 1, pro)
    ce = ox + len(pro) + 1
    g.put(ce, oy + 1, 'v')
    g.put(ox + 2, oy + 2, 'v')
    for x in range(ox + 3, ce):
        g.put(x, oy + 2, '.')
    g.put(ce, oy + 2, '<')
    g.text(ox + 2, oy + 3, ">sNv")
    g.text(ox + 2, oy + 4, "d.m<")
    if term:
        g.put(ox + 1, oy + 4, 'v')
        g.text(ox + 1, oy + 5, ">0sH")
    else:
        g.put(ox + 1, oy + 4, 'H')
    r.attach('MI', side_in[0], side_in[1], 'in')
    r.attach('MO', side_out[0], side_out[1], 'out')
    r.check({(ox + 3, oy + 1): ('MI', 'in'), (ox + 3, oy + 3): ('MO', 'out')})
    return r


def admx3(g, ox, oy):
    """A-queue demultiplexer.  w=17 h=15.

    prologue: r,S,r,S,M,r,S   -- consumes N,M,K and re-broadcasts them to every
    outgoing pipe (FE1, FE2, MCTLA, MCTLC); B is left holding M.
    entry:    r_MA ; X    A>0 -> east loop: BP=A, forward A values to AO1
                          A<0 -> west loop: negate, forward to AO2
                          A=0 -> pad  loop: B=M -> BP=M, emit M zeros to AO2
    """
    r = g.room(ox, oy, 17, 15)
    g.put(ox + 15, oy + 3, 'v')
    for y in range(oy + 4, oy + 13):
        g.put(ox + 15, y, '.')
    g.put(ox + 15, oy + 13, '<')
    for x in range(ox + 8, ox + 15):
        g.put(x, oy + 13, '.')
    g.put(ox + 7, oy + 13, '^')
    g.put(ox + 7, oy + 12, 'r')
    g.put(ox + 7, oy + 11, 'X')
    g.text(ox + 1, oy + 1, "@>rSrSMrS")
    for x in range(ox + 10, ox + 15):
        g.put(x, oy + 1, '.')
    g.put(ox + 15, oy + 1, 'v')
    g.put(ox + 15, oy + 2, '.')
    # east loop (A>0)
    g.put(ox + 8, oy + 11, '^')
    g.put(ox + 8, oy + 10, 'b')
    for y in range(oy + 6, oy + 10):
        g.put(ox + 8, y, '.')
    g.text(ox + 8, oy + 4, ">rsmd")
    g.text(ox + 8, oy + 5, "^...<")
    g.put(ox + 13, oy + 4, 'v')
    for y in range(oy + 5, oy + 13):
        g.put(ox + 13, y, '.')
    g.put(ox + 13, oy + 13, '<', force=True)
    # west loop (A<0)
    g.put(ox + 6, oy + 11, 'N')
    for x in range(ox + 2, ox + 6):
        g.put(x, oy + 11, '.')
    g.put(ox + 1, oy + 11, '^')
    g.put(ox + 1, oy + 10, 'b')
    for y in range(oy + 5, oy + 10):
        g.put(ox + 1, y, '.')
    g.put(ox + 1, oy + 4, '>')
    g.text(ox + 2, oy + 4, ">rsmd")
    g.text(ox + 2, oy + 5, "^...<")
    g.put(ox + 7, oy + 4, '^')
    g.put(ox + 7, oy + 3, '>')
    for x in range(ox + 8, ox + 15):
        g.put(x, oy + 3, '.')
    # pad loop (A==0): M zeros to AO2
    g.put(ox + 7, oy + 10, 'W')
    g.put(ox + 7, oy + 9, 'b')
    g.put(ox + 7, oy + 8, '<')
    g.text(ox + 2, oy + 7, ">0smd")
    g.text(ox + 2, oy + 8, "^...<")
    g.put(ox + 7, oy + 7, 'H')
    r.attach('AP', 'L', oy + 1, 'in')
    r.attach('MA', 'R', oy + 10, 'in')
    r.attach('AO1', 'T', ox + 11, 'out')
    r.attach('AO2', 'B', ox + 4, 'out')
    r.attach('MCA', 'R', oy + 8, 'out')
    r.attach('MCC', 'R', oy + 13, 'out')
    r.check({
        (ox + 3, oy + 1): ('AP', 'in'), (ox + 5, oy + 1): ('AP', 'in'),
        (ox + 8, oy + 1): ('AP', 'in'),
        (ox + 9, oy + 4): ('AP', 'in'), (ox + 3, oy + 4): ('AP', 'in'),
        (ox + 7, oy + 12): ('MA', 'in'),
        (ox + 10, oy + 4): ('AO1', 'out'),
        (ox + 4, oy + 4): ('AO2', 'out'),
        (ox + 4, oy + 7): ('AO2', 'out'),
    })
    return r


FE_OPS = {
    #        N1 = (N+1)>>1                          count = M*N1
    '1': "rM1+M1W}sMrs*brs",
    #        N2 = (N>>1)+1                          count = M*N2
    '2': "rM1W}M1+sMrs*brs",
}


def fe(g, ox, oy, which, fo=None):
    """FE: emits the per-engine header (Ni, M, K), then relays exactly M*Ni A
    values from ADMX, then relays B forever from BDUP.  w=22 h=21."""
    r = g.room(ox, oy, 22, 21)
    ops = FE_OPS[which]
    g.text(ox + 1, oy + 1, "@>" + ops)
    g.put(ox + 19, oy + 1, 'v')
    g.put(ox + 2, oy + 2, 'v')
    for x in range(ox + 3, ox + 19):
        g.put(x, oy + 2, '.')
    g.put(ox + 19, oy + 2, '<')
    for y in range(oy + 3, oy + 8):
        g.put(ox + 2, y, '.')
    g.text(ox + 2, oy + 8, ">rrrv")
    g.text(ox + 2, oy + 9, "v...<")
    g.text(ox + 2, oy + 10, ">rs.v")
    g.text(ox + 2, oy + 11, "dm..<")
    g.put(ox + 1, oy + 11, 'v')
    for y in range(oy + 12, oy + 16):
        g.put(ox + 1, y, '.')
    g.put(ox + 1, oy + 16, '>')
    g.text(ox + 2, oy + 16, ">rsv")
    g.text(ox + 2, oy + 17, "^..<")
    r.attach('HI', 'L', oy + 1, 'in')
    r.attach('DA', 'L', oy + 9, 'in')
    r.attach('DB', 'L', oy + 17, 'in')
    r.attach('FO', *(fo or ('L', oy + 5)), 'out')
    r.check({
        (ox + 3, oy + 1): ('HI', 'in'), (ox + 13, oy + 1): ('HI', 'in'),
        (ox + 17, oy + 1): ('HI', 'in'),
        (ox + 3, oy + 8): ('DA', 'in'), (ox + 5, oy + 8): ('DA', 'in'),
        (ox + 3, oy + 10): ('DA', 'in'),
        (ox + 3, oy + 16): ('DB', 'in'),
    })
    return r
