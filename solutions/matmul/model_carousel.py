#!/usr/bin/env python3
"""Validate the CAROUSEL matmul machine before touching a grid.

Design under test (see docs/matmul-carousel-design.md):

  storage    A-QUEUE   N*M values, drains once, never re-enqueued
             B-RING    M*K values, row-major = exactly input order, cycles N times
             C-RING    K accumulators, cycles once per k-step
             a-holder  the single live a = A[i][k], re-enqueued by each worker
  compute    P identical worker men share ONE room, spaced evenly around a 14-cell
             op loop.  Each lap performs one MAC => one MAC per 14/P ticks.
             P men cost ~ZERO area (one room), so score scales as 1/P.
  ordering   every ring is FIFO and every worker runs the SAME lap, so the workers
             dequeue b_j/c_j and re-enqueue c_j in the same relative order.

NOTE on input order: N,M,K then ALL of A then ALL of B.  B must be resident before
the first MAC and A arrives first, so A MUST be buffered.  There is no way to stream
it.  Both A and B therefore cost ~N*M and ~M*K cells.

This model checks the ALGORITHM, the RING CHOREOGRAPHY and the STALL/COLLISION
budget, not grid geometry.
"""
from collections import deque
import json
import os
import sys

REPO = os.path.abspath(__file__).split("/solutions/")[0]

LAP_OPS = 10        # r b, s b, M, r a, s a, *, M, r c, +, s c
LAP_CELLS = 14      # 10 op cells + 4 corner cells of the loop
MAXN = MAXM = MAXK = 16


def rings_for_worst_case():
    """Pipe cells the grid must physically provide (sized for 16x16x16)."""
    a_queue = MAXN * MAXM + 1
    b_ring = MAXM * MAXK + 1
    c_ring = MAXK + 1
    holder = 2
    return {"a_queue": a_queue, "b_ring": b_ring, "c_ring": c_ring,
            "holder": holder,
            "total": a_queue + b_ring + c_ring + holder}


def matmul_carousel(N, M, K, A, B, P=3):
    a_queue = deque(A)
    b_ring = deque(B)
    c_ring = deque([0] * K)
    out = []
    macs = 0

    for i in range(N):
        for k in range(M):
            a = a_queue.popleft()          # consumed once, never returned
            for j in range(K):
                b = b_ring.popleft()
                c = c_ring.popleft()
                c_ring.append(c + a * b)
                b_ring.append(b)           # needed again M*K macs later
                macs += 1
        for _ in range(K):                 # row done: emit and reset
            out.append(c_ring.popleft())
        for _ in range(K):
            c_ring.append(0)

    ticks_per_mac = LAP_CELLS / P
    seed = 3 + N * M + M * K               # every input value read once
    drain = N * K                          # every output value sent once
    compute = macs * ticks_per_mac

    # --- RING TRANSIT STALLS -------------------------------------------------
    # A pipe cell passes a value on at 1 cell/tick, so a re-enqueued value needs
    # ~L ticks to come back round, where L is the PHYSICAL ring length -- fixed by
    # geometry and sized for the 16x16x16 worst case.  A small case holds few
    # values, so it drains its ring long before the first one returns and the
    # worker blocks.  This is the price of pipe-as-storage and it hits small cases
    # hardest.
    r = rings_for_worst_case()
    # b-ring: whole of B is consumed once per output row (M*K macs), then reused
    b_cycle_ticks = M * K * ticks_per_mac
    b_stall = max(0.0, r["b_ring"] - b_cycle_ticks) * N
    # c-ring: K accumulators reused every k-step (K macs)
    c_cycle_ticks = K * ticks_per_mac
    c_stall = max(0.0, r["c_ring"] - c_cycle_ticks) * N * M
    stall = b_stall + c_stall

    return out, {
        "macs": macs,
        "ticks": round(compute + seed + drain + stall),
        "compute": round(compute), "seed": seed, "drain": drain,
        "stall": round(stall), "b_stall": round(b_stall), "c_stall": round(c_stall),
        # stall tolerance: men are LAP_CELLS/P apart; a mover entering a blocked
        # man's cell kills BOTH, so consecutive stall ticks must stay under this.
        "spacing": LAP_CELLS / P,
    }


def run_public(P):
    spec = json.load(open(os.path.join(REPO, "tests", "matmul.json")))
    tot, n, ok = 0, 0, True
    per = []
    for c in spec["publicTestData"]:
        for rnd in c["rounds"]:
            v = [int(x) for x in rnd["in"]]
            N, M, K = v[0], v[1], v[2]
            A = v[3:3 + N * M]
            B = v[3 + N * M:3 + N * M + M * K]
            got, st = matmul_carousel(N, M, K, A, B, P)
            ok &= got == [int(x) for x in rnd["out"]]
            per.append((c["name"], N, M, K, st))
            tot += st["ticks"]
            n += 1
    return ok, tot / n, per


def main():
    r = rings_for_worst_case()
    print("worst-case ring cells (16x16x16):", json.dumps(r))
    print()
    ok, avg, per = run_public(3)
    print(f"{'case':<24} {'N,M,K':>10} {'macs':>6} {'compute':>8} {'seed':>5} {'ticks':>8}")
    for name, N, M, K, st in per:
        print(f"{name:<24} {N},{M},{K:>4} {st['macs']:>6} {st['compute']:>8} "
              f"{st['seed']:>5} {st['ticks']:>8}")
    print(f"\ncorrectness on public cases: {'ALL PASS' if ok else 'FAILED'}")
    print()

    # --- what P buys, against the real board -----------------------------
    CUR_BOX, CUR_AVG, CUR_SCORE = 3721, 49864, 230073151
    print(f"{'P':>3} {'spacing':>8} {'avg ticks':>10} {'box 1296':>12} {'box 2025':>12}  vs live")
    for P in (1, 2, 3, 5, 7):
        ok, avg, _ = run_public(P)
        s1, s2 = 1296 * avg, 2025 * avg
        print(f"{P:>3} {LAP_CELLS/P:>8.1f} {avg:>10,.0f} {s1:>12,.0f} {s2:>12,.0f}"
              f"  {CUR_SCORE/s2:>5.1f}x - {CUR_SCORE/s1:>5.1f}x")
    print()
    print(f"live today: box {CUR_BOX:,} x avg {CUR_AVG:,} = {CUR_SCORE:,}")
    print("board best: 8,320,307  (fixstars)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
