"""prooms — the NEW rooms for the P=2 (parallel) matmul engine.

MCTL   reads N,M,K and emits +V,-V,+V,... exactly N times (V = M or K).
       With pad=True it emits one extra 0 token iff N is odd -- the sign of A
       after N negations IS the parity, so no extra register is needed.
ADMX   A-queue demultiplexer: forwards N,M,K to both ARELs (S broadcast), then
       routes blocks of M A-values alternately to AO1/AO2 under MCTL control,
       and on the 0 token emits one phantom block of M zeros to AO2 (so both
       engines always receive the SAME number of blocks -- otherwise the shared
       B ring deadlocks on odd N).
MRG    ordered 2-stream output merge: K values from O1, K from O2, ... N times.

DIST / EAT3 are test-rig only.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'solutions', 'matmul'))
from mm2lib import DIRS, pipe                       # noqa: E402
from mm2route import bfs                            # noqa: E402


# ---------------------------------------------------------------- routing help
def interiors(g, rects):
    """Reserve every room interior so BFS cannot tunnel through a room."""
    res = []
    for (x, y, w, h) in rects:
        for i in range(x + 1, x + w - 1):
            for j in range(y + 1, y + h - 1):
                if g.get(i, j) == ' ':
                    g.put(i, j, '\x01')
                    res.append((i, j))
    return res


def halo(g, cells, keep=()):
    """Reserve the 4-neighbourhood of `cells` so nothing is ever laid ADJACENT to
    them.  Two pipes side by side parse as one pipe; a pipe hugging a foreign room
    wall gets re-terminated on that room.  Both bit during the first rig build."""
    res = []
    keep = set(keep)
    for (x, y) in cells:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, y + dy)
            if c not in keep and g.get(*c) == ' ':
                g.put(c[0], c[1], '\x01')
                res.append(c)
    return res


def room_halo(g, rects, keep):
    cells = []
    for (x, y, w, h) in rects:
        cells += [(x + i, y) for i in range(w)] + [(x + i, y + h - 1) for i in range(w)]
        cells += [(x, y + j) for j in range(h)] + [(x + w - 1, y + j) for j in range(h)]
    return halo(g, cells, keep)


def link(g, src_att, src_dir, dst_att, dst_dir, bound, keep=()):
    for c in (src_att, dst_att):
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dy)
            if g.get(*n) == '\x01':
                del g.c[n]
    s2 = (src_att[0] + DIRS[src_dir][0], src_att[1] + DIRS[src_dir][1])
    g.put(src_att[0], src_att[1], '\x01', force=True)
    p = bfs(g, s2, dst_att, (), bound)
    del g.c[src_att]
    if p is None:
        raise ValueError(f"no route {src_att} -> {dst_att}")
    cells = [src_att] + p
    pipe(g, cells, end_direction=dst_dir)
    return cells


def wire_all(g, rects, nets, bound, tries=400, seed=1):
    """Route every net with BFS + halo, retrying random orders until all fit."""
    import random
    rnd = random.Random(seed)
    atts = {c for n in nets for c in (n[0], n[2])}
    order = sorted(range(len(nets)),
                   key=lambda i: -(abs(nets[i][0][0] - nets[i][2][0]) +
                                   abs(nets[i][0][1] - nets[i][2][1])))
    for t in range(tries):
        snap = dict(g.c)
        resv = interiors(g, rects)
        resv += room_halo(g, rects, atts)
        try:
            for i in order:
                sa, sd, da, dd = nets[i]
                for c in (sa, da):
                    if g.get(*c) == '\x01':
                        del g.c[c]
                cells = link(g, sa, sd, da, dd, bound, keep=atts)
                resv += halo(g, cells, atts)
        except ValueError:
            g.c.clear()
            g.c.update(snap)
            order = list(range(len(nets)))
            rnd.shuffle(order)
            continue
        for c in resv:
            if g.get(*c) == '\x01':
                del g.c[c]
        return t
    raise ValueError("wire_all: no ordering routed all nets")


# ---------------------------------------------------------------------- rooms
def mctl(g, ox, oy, pick, pad):
    """w=11 h=7.  MI in on L@oy+1, MO out on R@oy+3."""
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
    if pad:
        g.put(ox + 1, oy + 4, 'X')
        g.put(ox + 1, oy + 3, 'H')
        g.text(ox + 1, oy + 5, ">0sH")
    else:
        g.put(ox + 1, oy + 4, 'H')
    r.attach('MI', 'L', oy + 1, 'in')
    r.attach('MO', 'R', oy + 3, 'out')
    r.check({(ox + 3, oy + 1): ('MI', 'in'), (ox + 3, oy + 3): ('MO', 'out')})
    return r


def _demux(g, ox, oy, prologue, pad):
    """Shared skeleton of ADMX and MRG.  w=17 h=15.

    entry: r_CTL at (ox+7,oy+12) then X at (ox+7,oy+11) walking NORTH
           A>0 -> east loop  (reads/sends the EAST pipe)
           A<0 -> west loop  (negates first, reads/sends the WEST pipe)
           A=0 -> straight north (pad branch, or H)
    """
    r = g.room(ox, oy, 17, 15)
    # --- return lane: col ox+15 south, then row oy+13 west into the entry
    g.put(ox + 15, oy + 3, 'v')
    for y in range(oy + 4, oy + 13):
        g.put(ox + 15, y, '.')
    g.put(ox + 15, oy + 13, '<')
    for x in range(ox + 8, ox + 15):
        g.put(x, oy + 13, '.')
    g.put(ox + 7, oy + 13, '^')
    g.put(ox + 7, oy + 12, 'r')          # r_CTL
    g.put(ox + 7, oy + 11, 'X')
    if prologue:
        g.text(ox + 1, oy + 1, prologue)
        for x in range(ox + 1 + len(prologue), ox + 15):
            g.put(x, oy + 1, '.')
        g.put(ox + 15, oy + 1, 'v')
        g.put(ox + 15, oy + 2, '.')
    else:
        g.put(ox + 1, oy + 13, '@')
        for x in range(ox + 2, ox + 7):
            g.put(x, oy + 13, '.')

    # ---- east loop (A>0)
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

    # ---- west loop (A<0)
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
    # west exit: over the top, join the return lane
    g.put(ox + 7, oy + 4, '^')
    g.put(ox + 7, oy + 3, '>')
    for x in range(ox + 8, ox + 15):
        g.put(x, oy + 3, '.')

    # ---- pad branch (A==0)
    if pad:
        g.put(ox + 7, oy + 10, 'W')      # A = M (stashed in B), B = 0
        g.put(ox + 7, oy + 9, 'b')
        g.put(ox + 7, oy + 8, '<')
        g.text(ox + 2, oy + 7, ">0smd")
        g.text(ox + 2, oy + 8, "^...<")
        g.put(ox + 7, oy + 7, 'H')
    else:
        g.put(ox + 7, oy + 10, 'H')
    return r


def admx(g, ox, oy, bcast=()):
    """AP in L@oy+1, MA in L@oy+13, AO1 out T@ox+11, AO2 out B@ox+4.

    `bcast` names extra OUT pipes that exist only to receive the N,M,K `S`
    broadcast (MCTLA / MCTLC / PCNT1 / PCNT2).  Making ADMX -- not SPL -- the
    fan-out point is what makes the netlist PLANAR: with SPL feeding BREL, PCNT
    and both MCTLs, {SPL,engine1,engine2} x {ADMX,BREL,MRG} is a K(3,3) minor and
    the pipes provably cannot be routed without a crossing.  Their attachments
    are parked far from all three `s` cells so nearest-pipe still picks AO1/AO2.
    """
    r = _demux(g, ox, oy, "@>rSrSMrS", True)
    r.attach('AP', 'L', oy + 1, 'in')
    r.attach('MA', 'L', oy + 13, 'in')
    r.attach('AO1', 'T', ox + 11, 'out')
    r.attach('AO2', 'B', ox + 4, 'out')
    far = [('B', ox + 15), ('R', oy + 8), ('R', oy + 10), ('R', oy + 12)]
    for nm, (side, off) in zip(bcast, far):
        r.attach(nm, side, off, 'out')
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


def mrg(g, ox, oy):
    """MC in B@ox+7, O1 in T@ox+11, O2 in L@oy+4, OUT out R@oy+9."""
    r = _demux(g, ox, oy, None, False)
    r.attach('MC', 'B', ox + 7, 'in')
    r.attach('O1', 'T', ox + 11, 'in')
    r.attach('O2', 'L', oy + 4, 'in')
    r.attach('OUT', 'R', oy + 9, 'out')
    r.check({
        (ox + 9, oy + 4): ('O1', 'in'),
        (ox + 3, oy + 4): ('O2', 'in'),
        (ox + 7, oy + 12): ('MC', 'in'),
        (ox + 10, oy + 4): ('OUT', 'out'),
        (ox + 4, oy + 4): ('OUT', 'out'),
    })
    return r


# ------------------------------------------------------------- test-rig rooms
def dist(g, ox, oy):
    """DIST (rig): reads N,V,W, S-broadcasts them, then forwards N*V values.
    The forwarding loop sits on the EAST side so its `s` binds DD (east wall)."""
    r = g.room(ox, oy, 15, 9)
    g.text(ox + 1, oy + 1, "@>rSMrS*brS")
    g.put(ox + 12, oy + 1, 'v')
    g.put(ox + 8, oy + 2, 'v')
    for x in range(ox + 9, ox + 12):
        g.put(x, oy + 2, '.')
    g.put(ox + 12, oy + 2, '<')
    g.text(ox + 8, oy + 3, ">rsmd")
    g.text(ox + 8, oy + 4, "^...<")
    g.put(ox + 13, oy + 3, 'H')
    r.attach('IN', 'L', oy + 1, 'in')
    r.attach('DD', 'R', oy + 3, 'out')
    r.attach('DA', 'B', ox + 8, 'out')
    r.attach('DK', 'B', ox + 4, 'out')
    r.check({(ox + 10, oy + 3): ('DD', 'out')})
    return r


def eat3(g, ox, oy):
    """EAT3 (rig): swallow 3 values then relay forever."""
    r = g.room(ox, oy, 11, 7)
    g.text(ox + 1, oy + 1, "@>rrr")
    g.put(ox + 6, oy + 1, 'v')
    g.put(ox + 2, oy + 2, 'v')
    for x in range(ox + 3, ox + 6):
        g.put(x, oy + 2, '.')
    g.put(ox + 6, oy + 2, '<')
    g.text(ox + 2, oy + 3, ">rsv")
    g.text(ox + 2, oy + 4, "^.m<")
    r.attach('EI', 'L', oy + 1, 'in')
    r.attach('EO', 'R', oy + 3, 'out')
    return r


def pcnt2(g, ox, oy):
    """PCNT with every `s` promoted to `S` so ONE control stream feeds BOTH ACCs
    atomically (and keeps them in lock-step).  Two CTL out-pipes."""
    r = g.room(ox, oy, 13, 10)
    g.text(ox + 1, oy + 1, "@r1Mr-MrSSv")
    g.text(ox + 2, oy + 2, "v........<")
    g.text(ox + 2, oy + 3, ">WbWv")
    g.text(ox + 2, oy + 4, "^.v.<")
    g.text(ox + 2, oy + 5, ".")
    g.text(ox + 4, oy + 5, ">Sv")
    g.text(ox + 1, oy + 6, "v..dm<")
    g.text(ox + 1, oy + 7, ">..NSNSv")
    g.text(ox + 2, oy + 8, "^.....<")
    r.attach('CP', 'L', oy + 4, 'in')
    r.attach('CTL1', 'B', ox + 4, 'out')
    r.attach('CTL2', 'B', ox + 8, 'out')
    return r


def bdup(g, ox, oy):
    """BDUP: relays every value it receives to BOTH outgoing pipes (`S`).

    Giving each engine its OWN B ring (instead of chaining B through MUL1 into
    MUL2) is what removes the MUL1--MUL2 edge, and with it the last crossing:
    the netlist becomes K(2,3) between the two engines and {BDUP, ADMX, MRG},
    which is planar.  It also decouples the engines, so an idle engine can no
    longer stall the other one's B ring.
    """
    r = g.room(ox, oy, 7, 4)
    g.text(ox + 1, oy + 1, "@>rSv")
    g.text(ox + 2, oy + 2, "^..<")
    r.attach('BI', 'L', oy + 1, 'in')
    r.attach('BO1', 'T', ox + 3, 'out')
    r.attach('BO2', 'B', ox + 3, 'out')
    return r
