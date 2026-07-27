"""BFS fifo router: minimal r/s/M/W sequence turning `src` into `dst`."""
from collections import deque

def route(src, dst):
    """src, dst: tuples of names. Returns list of ops or None."""
    start = (tuple(src), None, None)
    goal = tuple(dst)
    seen = {start}
    q = deque([(start, [])])
    while q:
        (f, A, B), ops = q.popleft()
        if f == goal and A is None and B is None:
            return ops
        if len(ops) > 24:
            continue
        stored = set(f)
        # r: pop front into A
        if f and (A is None or A in stored or A == B):
            ns = ((f[1:], f[0], B), ops + ["r"])
            if ns[0] not in seen:
                seen.add(ns[0]); q.append(ns)
        # s: push A to back (A retained)
        if A is not None and A not in stored:
            ns = ((f + (A,), None, B), ops + ["s"])
            if ns[0] not in seen:
                seen.add(ns[0]); q.append(ns)
        # M: B = A
        if A is not None and (B is None or B in stored or B == A):
            ns = ((f, A, A), ops + ["M"])
            if ns[0] not in seen:
                seen.add(ns[0]); q.append(ns)
        # W: swap
        if A != B:
            ns = ((f, B, A), ops + ["W"])
            if ns[0] not in seen:
                seen.add(ns[0]); q.append(ns)
    return None

if __name__ == "__main__":
    import itertools
    src = ("addr0", "adx", "sx", "ady", "vy")
    dst = ("adx", "ady", "addr0", "sx", "vy")
    print(route(src, dst))
