#!/usr/bin/env python3
"""Exhaustive placement search for tcp's right band.

The left stack (reader | lane pipes | sweeper) fixes the grid height and owns
cols 0..17. Everything else -- the checker, the I room, the O room and the four
pipes -- has to fit in the columns to its right. This enumerates every legal
placement and reports whether ANY exists, for a given width and checker height.

Encoded rules (all verified against the oracle elsewhere):
  * a pipe is >= 2 cells; consecutive cells are orthogonally adjacent
  * the source cell's BACKWARD neighbour must be a wall cell of the source room
    (a room CORNER counts), i.e. the source points away from its room
  * the last cell points into a wall cell of the destination room
  * a pipe may turn at the very next cell after the source
  * pipe cells may not overlap rooms or other pipes
  * seq and drain must reach the checker on OPPOSITE walls (north/south), at
    ANY interior column and independently of each other. `U`'s turn is
    pipe_flow_dir = the END ARROWHEAD direction (lib.rs op_recv_any), i.e. the
    direction the value flows INTO the room -- it does not depend on where `U`
    stands or on the two pipes sharing a column. An earlier version of this
    search wrongly pinned both to U's column.

usage: bandsearch.py [width] [checker_h] [reader_h]
"""
import sys
from collections import deque

READER_W = 18                      # cols 0..17: 16 lane columns + 2 walls


def solve(W, CH, RH, verbose=False):
    H = RH + 2 + 7                 # reader + lane pipes + sweeper
    reader = (0, 0, READER_W, RH)          # x, y, w, h
    sweeper = (0, RH + 2, READER_W, 7)

    def cells(r):
        x, y, w, h = r
        return {(x + i, y + j) for i in range(w) for j in range(h)}

    def walls(r):
        x, y, w, h = r
        s = set()
        for i in range(w):
            s.add((x + i, y)); s.add((x + i, y + h - 1))
        for j in range(h):
            s.add((x, y + j)); s.add((x + w - 1, y + j))
        return s

    blocked0 = cells(reader) | cells(sweeper)
    for c in range(1, 17):                  # the 16 lane pipes
        blocked0 |= {(c, RH), (c, RH + 1)}

    band = [(x, y) for x in range(READER_W, W) for y in range(H)]
    if W - READER_W < 4:
        return None

    def spurious_start(path, allwalls):
        """True if any cell after the source would be seen as a pipe START."""
        for i in range(1, len(path) - 1):
            d = (path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
            back = (path[i][0] - d[0], path[i][1] - d[1])
            if back in allwalls:
                return True
        return False

    def route(src_room, dst_room, blocked, dst_wall_filter=None):
        """BFS every legal pipe from src_room to dst_room. Yields cell lists."""
        sw, dw = walls(src_room), walls(dst_room)
        out = []
        for (bx, by) in sw:                 # a source cell sits beside a wall cell
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                s = (bx + d[0], by + d[1])
                if s in blocked or not (0 <= s[0] < W and 0 <= s[1] < H):
                    continue
                if s in cells(src_room) or s in cells(dst_room):
                    continue
                # The SOURCE cell points away from its room: its first move must
                # be exactly d (the offset from the wall cell it sits beside).
                # Only from the second cell on may the pipe turn.
                nxt = (s[0] + d[0], s[1] + d[1])
                if not (0 <= nxt[0] < W and 0 <= nxt[1] < H):
                    continue
                if nxt in dw:
                    continue                      # 1-cell pipe: illegal
                if nxt in blocked or nxt in cells(src_room):
                    continue
                seen = {s, nxt}
                q = deque([(nxt, [s, nxt])])
                while q:
                    cur, path = q.popleft()
                    for e in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        n = (cur[0] + e[0], cur[1] + e[1])
                        if not (0 <= n[0] < W and 0 <= n[1] < H):
                            continue
                        if n in dw and len(path) >= 2:
                            if dst_wall_filter is None or dst_wall_filter(n):
                                out.append(path + [n])   # n = the attach cell
                            continue
                        if n in seen or n in blocked or n in dw:
                            continue
                        if len(path) > 14:
                            continue
                        seen.add(n)
                        q.append((n, path + [n]))
        return out

    for cy in range(0, H - CH + 1):
        checker = (READER_W, cy, 4, CH)
        cL, cR = READER_W + 1, READER_W + 2      # interior columns
        # U's turn is pipe_flow_dir = the END ARROWHEAD direction (lib.rs
        # op_recv_any/pipe_flow_dir), NOT the pipe's position relative to U.
        # So seq only has to flow SOUTH into the north wall and drain NORTH into
        # the south wall; their columns are independent of each other and of U.
        for ux in (cL,):
            north = {(cL, cy), (cR, cy)}
            south = {(cL, cy + CH - 1), (cR, cy + CH - 1)}
            for iy in range(0, H - 3 + 1):
                for ix in range(READER_W, W - 3 + 1):
                    iroom = (ix, iy, 3, 3)
                    if cells(iroom) & (cells(checker) | blocked0):
                        continue
                    for oy in range(0, H - 3 + 1):
                        for ox in range(READER_W, W - 3 + 1):
                            oroom = (ox, oy, 3, 3)
                            if cells(oroom) & (cells(checker) | cells(iroom) | blocked0):
                                continue
                            base = blocked0 | cells(checker) | cells(iroom) | cells(oroom)
                            # 4 pipes, routed greedily with backtracking
                            allw = set()
                            for rm in (reader, sweeper, checker, iroom, oroom):
                                allw |= walls(rm)
                            plans = [
                                ('input', iroom, reader, None, allw, spurious_start),
                                ('seq', reader, checker, lambda n: n in north, allw, spurious_start),
                                ('drain', sweeper, checker, lambda n: n in south, allw, spurious_start),
                                ('output', checker, oroom, None, allw, spurious_start),
                            ]
                            sol = try_all(plans, base, route, 0, {})
                            if sol is not None:
                                return dict(W=W, H=H, CH=CH, RH=RH, cy=cy, ux=ux,
                                            iroom=iroom, oroom=oroom, pipes=sol)
    return None


def try_all(plans, blocked, route, i, acc):
    if i == len(plans):
        return dict(acc)
    name, a, b, filt, allwalls, spur = plans[i]
    for path in route(a, b, blocked, filt):
        body = path[:-1]                      # last entry is the attach cell
        if any(c in blocked for c in body):
            continue
        if spur(path, allwalls):
            continue
        path = body
        acc[name] = path
        r = try_all(plans, blocked | set(path), route, i + 1, acc)
        if r is not None:
            return r
        del acc[name]
    return None


if __name__ == '__main__':
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 22
    CH = int(sys.argv[2]) if len(sys.argv) > 2 else 13
    RH = int(sys.argv[3]) if len(sys.argv) > 3 else 13
    r = solve(W, CH, RH)
    print(f'W={W} checker_h={CH} reader_h={RH} height={RH+9} box={max(W,RH+9)**2}: '
          + ('SOLVABLE ' + str({k: v for k, v in r.items() if k in ("cy","ux","iroom","oroom")})
             if r else 'NO PLACEMENT'))
