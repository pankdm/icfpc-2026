"""Enumerate 16-cell cycles in small boxes, keep those with two BP-test exits
exactly 8 apart along the cycle, and report waste (cells of the bbox not on the
cycle) and where the exits point.

=== reverse-a-list 11x11: geometry findings (agent 2, 2026-07-26) ===

Continues scratchpad/reverse-11x11-search (branch worktree-agent-ae8705b2953d35e5a).
That agent's conclusion was "50-51 cells of 54, largest free pocket 3, infeasible".
These are the corrections and the new levers.

1. 54 IS A HARD CEILING (analytic, replaces the "assume one main room" hand-wave).
   Main room w x h -> interior (w-2)(h-2). A disjoint 3x3 room needs a 3-wide free
   band, so w<=8 or h<=8; maximising (w-2)(h-2) gives 11x8 or 8x11 -> 54.
   Corner-sharing (legal, one cell) never helps: a full-height 9-wide main room
   would overlap a left-hand 3x3's wall in 3 cells, and every corner-shared
   variant that gains interior leaves no 3-wide band for the *second* I/O room.
   Two main rooms strictly lose: a w x h room costs w*h cells for (w-2)(h-2)
   interior (3x3 -> 1, 4x4 -> 4), so splitting 8x11 (88 cells -> 54) always loses.
   I/O rooms are exactly 3x3 per PROBLEM.md and cannot share structure.
   => Both 6x9 and 9x6 interiors give 54; I/O placement does not change the count.

2. THE MECHANISM'S PARAMETERS ARE FORCED (so "just use a cheaper design" is out).
   With reader lap R ticks, k values forked per lap, ring delay s ticks per BP
   unit, dense output requires s - R = k and total ticks ~ n*(R/k + 1).
   - The reader 6-cycle (3x2: 4 corner turns = 2 turns + `a` + `Y`, 2 straight
     cells = k `m`s) forces R=6, k=2  =>  s=8, total ~4n.
   - Ring length L = 8 * (#m per lap). L=8 (1 `m`) FAILS collision: men enter at
     ticks 6j and 6j+1, two men share a cell iff the entry gap == 0 mod L, and
     6*4 = 24 == 0 mod 8. L=16 works (6d == 0 mod 16 only at d=8, i.e. n>16;
     6d+-1 is odd so never 0 mod 16). L=16 is therefore MINIMAL, 2 `m`, 2 exits
     exactly 8 apart, each exit a cycle *corner* (turn = stay, straight = leave).
   - k=1 (manual-11x11's family) tops out at 7n. Measured: repack11 = 4.25n
     (local avg 95.75, server 118.7), manual-11x11 = 8.5n (local avg 137.5).
     A *perfect* 7n 11x11 still projects to server ~20.8k > repack11's 17,092.8,
     so speeding up manual-11x11 is worthless; only the 4n design can win.
     Target: an 11x11 at repack11's tick count scores 121*118.7 = 14,363, which
     would also beat the board leader (14,865).

3. repack11's REAL circuit is 50 visited cells in a 7x10 bbox (circuit2.py).
   Inventory: park 4, reader 6, fork macro 9, trunk 2, ring 16, ring exits 4
   (2 `s` + 2 `H`), reader-fallout connector 1, terminator 8 (+1 shared merge).
   Its ring is a serpentine in a 6x4 bbox: 16 ring + 4 exit + 4 ENCLOSED DEAD.
   Only 42 of the 50 are non-space; 8 are nop corridor cells inside loops.

4. NEW LEVER A: a 4x4 HAMILTONIAN 16-cycle exists with two valid 8-apart exits
   (2 of the 6 Hamiltonian cycles in 4x4 qualify) -> ring with ZERO waste,
   vs. the 4 dead cells of repack11's 6x4 serpentine. Budget becomes
   54 - 16 - 4 = 34 free for the ~30 remaining cells: slack 4.
   BUT 4x4 and 2x8 rings only admit *opposite-pointing* exit pairs (N/S or E/W),
   which forces the ring to sit centrally (2 free rows above AND below). In a
   6-wide interior that leaves only 2 spare columns, so the carrier must go down
   one column and the trunk back up the other: ~7 cells of transit, which eats
   the entire 4-cell saving. Hand-checked layout came out 2 cells short.

5. NEW LEVER B (the better one): SAME-DIRECTION exit pairs exist. Direction-pair
   census over all 16-cycles with valid exits:
     4x4 {N/S:3, E/W:3}                      2x8 {N/S:1, E/W:1}
     4x5 / 5x4 {..., N/N:8, S/S:8, E/E:8, W/W:8}
     4x6 / 6x4 {..., N/N:25/17, ...}         5x5 {..., N/N:51, ...}
   An (N,N) pair lets the ring sit FLUSH against the bottom wall with both
   `s`/`H` stacks above it -> no transit at all. Best budget found:
   ring bbox 5x4 or 4x5 (waste 4) flush at the bottom => ~30 free cells for the
   ~28-30 remaining, i.e. slack 0-2 with the residual as one connected L, not
   the prior agent's median-3 severed pockets.
   Caveat to check when building: in the 5x4 (N,N) examples the *second* exit's
   `s` lands on a waste cell INSIDE the bbox, and the cell beyond it must also be
   off-cycle (else the man rejoins the ring and re-sends `A`). analyse() does not
   yet enforce that the `H` cell is off-cycle -- add it before trusting a hit.

6. NEW LEVER C: the terminator (odd-n branch) is 8 cells in a 4x2 bbox with NO
   enclosed cell, vs repack11's 3x3 with 1 dead cell:
     row0: `>` nop `^` `x`     row1: `^` `s` `r` `<`
   fallout arrives westward onto `x`; low-bit-1 (even n, BP=-1) turns CW = north
   and leaves for the park; low-bit-0 (odd n) turns CCW = south into the U, reads
   the leftover, sends it, and leaves north from row0 col2. Saves 1 used + 1 dead.
   Timing slack measured: repack11's odd-n cases cost the same as n+1 (n=3 and
   n=4 both 32 ticks), so the odd path has ~5 ticks of routing slack to spend.

NEXT STEP for whoever picks this up: this is now a ~30-cells-in-30-to-34 exact
packing with directional constraints (each cell one op; `a`/`d` turn only at
cycle corners; `Y` births must be free and perpendicular). It is a SAT/CP job,
not a random-placement job -- encode cell->op assignment plus the fixed circuit
edge list from circuit2.py and let a solver run. Do NOT re-run gen2..gen6.


A test cell must be a *corner* of the cycle (the two cycle edges at it are
perpendicular) so that "turn" stays on the ring and "straight" leaves it.
The straight-out cell must be off the cycle (it becomes `s`).
"""
import sys
from itertools import product

DIRS = {(1, 0): 'E', (-1, 0): 'W', (0, 1): 'S', (0, -1): 'N'}
CW = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
CCW = {v: k for k, v in CW.items()}


def cycles(W, H, L=16):
    """all simple cycles of length L in the WxH grid, canonical (start = smallest
    cell, second neighbour < last neighbour)."""
    cells = [(x, y) for y in range(H) for x in range(W)]
    idx = {c: i for i, c in enumerate(cells)}
    nbr = {c: [(c[0]+d[0], c[1]+d[1]) for d in DIRS
               if 0 <= c[0]+d[0] < W and 0 <= c[1]+d[1] < H] for c in cells}
    out = []
    for start in cells:
        path = [start]
        used = {start}

        def rec():
            cur = path[-1]
            if len(path) == L:
                if start in nbr[cur] and idx[path[1]] < idx[path[-1]]:
                    out.append(tuple(path))
                return
            for nx in nbr[cur]:
                if nx in used or idx[nx] < idx[start]:
                    continue
                # prune: remaining length must allow return
                if abs(nx[0]-start[0]) + abs(nx[1]-start[1]) > L - len(path):
                    continue
                path.append(nx); used.add(nx)
                rec()
                path.pop(); used.remove(nx)
        rec()
    return out


def analyse(cyc, W, H):
    L = len(cyc)
    on = set(cyc)
    res = []
    # direction of travel entering cell i (from i-1 to i) and leaving (i to i+1)
    ind = [(cyc[i][0]-cyc[i-1][0], cyc[i][1]-cyc[i-1][1]) for i in range(L)]
    outd = [(cyc[(i+1) % L][0]-cyc[i][0], cyc[(i+1) % L][1]-cyc[i][1]) for i in range(L)]
    corners = []
    for i in range(L):
        if ind[i] != outd[i]:  # a turn
            s = (cyc[i][0]+ind[i][0], cyc[i][1]+ind[i][1])  # straight-out cell
            if s not in on:
                op = 'd' if outd[i] == CW[ind[i]] else 'a'
                corners.append((i, cyc[i], s, op, ind[i]))
    for A, B in product(corners, corners):
        if (B[0]-A[0]) % L == L//2 and A[0] < B[0]:
            res.append((A, B))
    return res


def main():
    boxes = [(4, 4), (2, 8), (8, 2), (3, 6), (6, 3), (3, 7), (4, 5), (5, 4),
             (4, 6), (6, 4), (5, 5)]
    for W, H in boxes:
        if W*H > 26:
            continue
        cs = cycles(W, H)
        good = 0
        best = None
        for c in cs:
            pairs = analyse(c, W, H)
            if pairs:
                good += 1
                waste = W*H - 16
                if best is None:
                    best = (c, pairs, waste)
        print("box %dx%d: %d 16-cycles, %d with a valid 8-apart exit pair, bbox waste %d"
              % (W, H, len(cs), good, W*H-16))
        if best and W*H <= 16:
            c, pairs, waste = best
            print("   example cycle:", c)
            for A, B in pairs[:3]:
                print("   exits: idx%d %s op%s -> s at %s   |  idx%d %s op%s -> s at %s"
                      % (A[0], A[1], A[3], A[2], B[0], B[1], B[3], B[2]))

main()
