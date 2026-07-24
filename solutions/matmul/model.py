"""Validate the ring-machine matmul algorithm before translating to littleman.

Rings (FIFO deques). Registers A,B,BP. Ops mirror littleman semantics we will use.
Design: stationary-C streaming.
  SA: [a_0..a_{NM-1}, SA_SENT]           (consumed once, not re-enqueued)
  SB: [ per t-block: b_{t*K..t*K+K-1}, MARK ] * M  but last MARK -> ENDMARK
      i.e. b's with a MARK after every K, ENDMARK after the last block.
  SC: [c_0..c_{K-1}, SC_SENT]            (K accumulators + sentinel), c stored +OFFSET
  AH: [a]                                (period-1 a holder)
Tokens: SA_SENT big magnitude; MARK=1000; ENDMARK=2000; SC_SENT=-1.
Accumulator storage: c_stored = c_real + OFFSET (OFFSET keeps positive so SC_SENT<0 distinguishes).
"""
from collections import deque

OFFSET = 1_000_000
SA_SENT = 1_000_000_000   # |.|>500 marks end of A
MARK = 1000
ENDMARK = 2000
SC_SENT = -1

def matmul_model(N,M,K,A,B):
    # ---- seed rings ----
    SA = deque(A + [SA_SENT])
    SB = deque()
    idx = 0
    for t in range(M):
        for j in range(K):
            SB.append(B[t*K+j])
        SB.append(MARK if t < M-1 else ENDMARK)
    SC = deque([OFFSET]*K + [SC_SENT])
    AH = deque([0])  # dummy seed
    out = []

    def fetch_a():
        # replace AH content with next SA value; return False if SA_SENT (done)
        v = SA.popleft()
        if abs(v) > 500:  # SA_SENT
            return False
        AH.popleft()      # discard old
        AH.append(v)      # new current a
        return True

    # ---- row 0 start ----
    if not fetch_a():
        return out
    while True:
        x = SB.popleft(); SB.append(x)   # read + re-enqueue
        if x == ENDMARK:
            # OUTPUT PHASE: SC front is SC_SENT
            s = SC.popleft()             # leading sentinel
            assert s == SC_SENT
            SC.append(SC_SENT)           # re-enqueue -> [c_0..c_{K-1}, SENT]
            while True:
                c = SC.popleft()
                if c == SC_SENT:
                    SC.append(SC_SENT)   # -> [OFFSETs.., SENT]
                    break
                out.append(c - OFFSET)   # emit
                SC.append(OFFSET)        # reset accumulator
            # next row
            if not fetch_a():
                return out
            continue
        elif x == MARK:
            # t-boundary: fetch next a, realign SC (skip leading sentinel)
            if not fetch_a():
                return out   # shouldn't happen mid-row
            s = SC.popleft(); assert s == SC_SENT, s
            SC.append(SC_SENT)
            continue
        else:
            b = x
            a = AH.popleft(); AH.append(a)   # read a, re-enqueue (period-1)
            c = SC.popleft()
            c = c + a*b
            SC.append(c)
            continue

def naive(N,M,K,A,B):
    C=[]
    for i in range(N):
        for j in range(K):
            s=0
            for t in range(M):
                s+=A[i*M+t]*B[t*K+j]
            C.append(s)
    return C

import json,random
random.seed(1)
tests=[(2,2,2,[1,2,3,4],[5,6,7,8]),
       (2,3,2,[1,0,-1,2,3,1],[4,5,6,7,8,9]),
       ]
for _ in range(200):
    N=random.randint(2,16);M=random.randint(2,16);K=random.randint(2,16)
    A=[random.randint(-99,99) for _ in range(N*M)]
    B=[random.randint(-99,99) for _ in range(M*K)]
    tests.append((N,M,K,A,B))
ok=True
for N,M,K,A,B in tests:
    got=matmul_model(N,M,K,A,B); exp=naive(N,M,K,A,B)
    if got!=exp:
        ok=False; print("FAIL",N,M,K); print("got",got[:8]); print("exp",exp[:8]); break
print("ALL OK" if ok else "FAILED", "tested", len(tests))
