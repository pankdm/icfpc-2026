"""Exact-length self-avoiding pipe router for the matmul fold.

place.py's router minimises length, so it can never reproduce a 244-cell storage
serpentine. This one takes the length as a HARD constraint (ring capacity), and
snakes to absorb the slack. Warnsdorff ordering + connectivity pruning.
"""
import random, sys

DIRS = [(1,0),(-1,0),(0,1),(0,-1)]

def route_exact(free, start, first_dir, end, last_dir, length, seed=0, budget=400000):
    """Path of exactly `length` cells, start->end, all within `free`.

    first_dir fixes the source attachment (backward neighbour of cell 0);
    last_dir fixes the destination attachment (forward neighbour of cell -1).
    """
    free = set(free)
    if start not in free or end not in free:
        return None
    rnd = random.Random(seed)
    # cell 1 is forced by first_dir; the final cell's incoming dir is forced by last_dir
    prev_of_end = (end[0]-last_dir[0], end[1]-last_dir[1])
    path = [start]
    used = {start}
    nodes = [0]

    def manh(a,b): return abs(a[0]-b[0])+abs(a[1]-b[1])

    def connected_ok(cur, remaining):
        """cheap flood: end must still be reachable through unused free cells"""
        seen = {cur}; stack=[cur]; n=0
        while stack:
            c = stack.pop(); n += 1
            if c == end and n <= remaining + 1: return True
            for d in DIRS:
                nb = (c[0]+d[0], c[1]+d[1])
                if nb in free and nb not in used and nb not in seen:
                    seen.add(nb); stack.append(nb)
        return end in seen

    def dfs(cur):
        nodes[0] += 1
        if nodes[0] > budget: raise TimeoutError
        rem = length - len(path)          # cells still to place
        if rem == 0:
            return cur == end
        d = manh(cur, end)
        if d > rem: return False
        if (rem - d) % 2: return False    # grid parity
        if len(path) % 24 == 0 and not connected_ok(cur, rem):
            return False
        cands = []
        for dd in DIRS:
            nb = (cur[0]+dd[0], cur[1]+dd[1])
            if nb not in free or nb in used: continue
            if nb == end and rem != 1: continue
            if rem == 1 and nb != end: continue
            # the cell before `end` is forced by last_dir
            if rem == 2 and nb != prev_of_end: continue
            deg = sum(1 for e in DIRS
                      if (nb[0]+e[0],nb[1]+e[1]) in free and (nb[0]+e[0],nb[1]+e[1]) not in used)
            nd = manh(nb, end)
            # slack-aware: while there is length to burn, walk AWAY from the goal and
            # hug walls (Warnsdorff) so the path snakes; once slack is thin, home in.
            slack = rem - d
            key = (deg, -nd) if slack > 6 else (nd, deg)
            cands.append((key, rnd.random(), nb))
        cands.sort()
        for _,_,nb in cands:
            path.append(nb); used.add(nb)
            if dfs(nb): return True
            path.pop(); used.remove(nb)
        return False

    first = (start[0]+first_dir[0], start[1]+first_dir[1])
    if length == 1:
        return [start] if start == end else None
    if first not in free or first in used: return None
    path.append(first); used.add(first)
    try:
        if dfs(first):
            return list(path)
    except (TimeoutError, RecursionError):
        return None
    return None

def dirs_of(cells, last_dir):
    ds = []
    for i in range(len(cells)-1):
        ds.append((cells[i+1][0]-cells[i][0], cells[i+1][1]-cells[i][1]))
    ds.append(last_dir)
    return ds
