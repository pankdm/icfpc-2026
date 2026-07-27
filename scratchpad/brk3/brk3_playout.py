#!/usr/bin/env python3
"""Constructively lay brackets' P room into a 3-wide interior (route A: 5x11).

Random fill cannot find a 20-cell walk in 27 cells; this WALKS each arm instead
and places only what the walk demands, backtracking on the choice at every step
(place the arm's next op / place a turn / leave blank).  Arms are laid one after
another on the SAME grid, so a cell an earlier arm fixed constrains the later
ones -- which is exactly the sharing the room needs.

P's spec, read off the live 6x8 room:
    spine        ^ turns the man N, then r, then X
    X heading N  A>0 -> E, A=0 -> N (straight), A<0 -> W
    arms         A>0 [1,+,M]   A=0 [s,0,M,+,M]   A<0 [1,+,s,0,M,+,M]
Each arm must return to `r` having executed exactly its sequence.

  python3 brk3_playout.py [interior_w] [interior_h] [max_cells]
"""
import sys

IW = int(sys.argv[1]) if len(sys.argv) > 1 else 3
IH = int(sys.argv[2]) if len(sys.argv) > 2 else 9
BUDGET = int(sys.argv[3]) if len(sys.argv) > 3 else 27

ARMS = [(-1, list("1+s0M+M")), (0, list("s0M+M")), (1, list("1+M"))]
TURN = {">": (1, 0), "<": (-1, 0), "v": (0, 1), "^": (0, -1)}
N, S, E, Wd = (0, -1), (0, 1), (1, 0), (-1, 0)
LIMIT = 60


def inside(x, y):
    return 1 <= x <= IW and 1 <= y <= IH


def solve(grid, rc, xc):
    """Lay every arm; return a finished grid or None."""
    def arm(i, x, y, d, need, steps):
        if steps > LIMIT:
            return None
        nx, ny = x + d[0], y + d[1]
        if not inside(nx, ny):
            return None
        cur = grid.get((nx, ny))
        if (nx, ny) == rc:
            return dict(grid) if not need else None
        if (nx, ny) == xc:
            return None                       # never re-enter the branch
        options = []
        if cur is not None:
            options = [cur]
        else:
            if len(grid) >= BUDGET:
                options = [" "]
            else:
                if need:
                    options.append(need[0])
                options.extend(list(TURN))
                options.append(" ")
        for g in options:
            if cur is None:
                grid[(nx, ny)] = g
            if g == " ":
                r = arm(i, nx, ny, d, need, steps + 1)
            elif g in TURN:
                nd = TURN[g]
                r = None if nd == (-d[0], -d[1]) else arm(
                    i, nx, ny, nd, need, steps + 1)
            elif need and g == need[0]:
                r = arm(i, nx, ny, d, need[1:], steps + 1)
            else:
                r = None
            if r is not None:
                return r
            if cur is None:
                del grid[(nx, ny)]
        return None

    def lay(i):
        if i == len(ARMS):
            return dict(grid)
        sign, need = ARMS[i]
        d = {(-1): Wd, 0: N, 1: E}[sign]
        snap = dict(grid)
        got = arm(i, xc[0], xc[1], d, need, 0)
        if got is None:
            grid.clear()
            grid.update(snap)
            return None
        # `arm` left its placements in `grid`; recurse with them fixed.
        r = lay(i + 1)
        if r is None:
            grid.clear()
            grid.update(snap)
        return r

    return lay(0)


def render(grid, man):
    out = []
    for y in range(0, IH + 2):
        row = ""
        for x in range(0, IW + 2):
            if x in (0, IW + 1) and y in (0, IH + 1):
                row += "+"
            elif y in (0, IH + 1):
                row += "-"
            elif x in (0, IW + 1):
                row += "|"
            else:
                row += ("@" if (x, y) == man else grid.get((x, y), " "))
        out.append(row)
    return out


def main():
    for ry in range(IH, 2, -1):
        for rx in range(1, IW + 1):
            xc = (rx, ry - 1)
            if not inside(*xc):
                continue
            grid = {(rx, ry): "r", xc: "X"}
            if inside(rx, ry + 1):
                grid[(rx, ry + 1)] = "^"
                man = None
            else:
                continue
            got = solve(grid, (rx, ry), xc)
            if got:
                # the man starts west of the entry turn, gliding east into it
                mx = rx - 1
                if mx < 1:
                    continue
                if got.get((mx, ry + 1), " ") not in (" ", None):
                    continue
                cells = sum(1 for v in got.values() if v != " ") + 1
                print(f"FOUND  interior {IW}x{IH}  {cells} cells  "
                      f"r at ({rx},{ry})")
                for line in render(got, (mx, ry + 1)):
                    print("  " + line)
                return
    print(f"no layout for interior {IW}x{IH} within {BUDGET} cells")


if __name__ == "__main__":
    main()
