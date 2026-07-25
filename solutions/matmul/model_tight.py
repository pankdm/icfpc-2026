"""Validate the COUNTER-DRIVEN tight-MAC matmul algorithm before littleman build.

Difference from model.py (token-driven):
  - SB carries NO marks — just b's, cycled (read+reenq). One full SB cycle per output row.
  - Inner K-loop driven by BP counter (BP=K), not by reading MARK tokens from SB.
    => removes the per-MAC classify (the op-count floor of the opt5 design).
  - a-fetch + row boundary driven by tokens in SA (read once per BLOCK = amortized over K):
      SA = [ a(row0)*M , ROWMARK, a(row1)*M, ROWMARK, ..., a(rowN-1)*M, ROWMARK, SA_SENT ]
    a(row i) = A[i*M + t] for t=0..M-1.  ROWMARK after each row -> output that row.
  - a held in a tiny holder ring H across the K-sweep (round-trips each MAC — unavoidable,
    the 3-value/2-register crux).  SC = [c_0..c_{K-1}, SC_SENT] stationary accumulators.

Register model per MAC (A=main, B=off, BP=counter):
  r H->A=a; s H reenq; M B=a; r SB->A=b; s SB reenq; * A=a*b (B=a kept);
  M B=a*b; r SC->A=c; + A=c+a*b; s SC store; m BP--; d loop-if-BP>0.
"""
from collections import deque

OFFSET   = 1_000_000
SA_SENT  = 30000
ROWMARK  = 150      # in SA: end of a row's a's -> output row
SC_SENT  = -1

def matmul_tight(N,M,K,A,B):
    # ---- seed rings ----
    SA = deque()
    for i in range(N):
        for t in range(M):
            SA.append(A[i*M+t])
        SA.append(ROWMARK)
    SA.append(SA_SENT)
    SB = deque(B[:])                       # M*K b's, cycled, no marks
    SC = deque([OFFSET]*K + [SC_SENT])     # K accumulators + sentinel
    H  = deque()                           # a-holder (starts empty)
    out = []

    while True:
        x = SA.popleft()                   # once per block (or row-boundary) — amortized
        if x == SA_SENT:
            return out
        if x == ROWMARK:
            # ----- OUTPUT ROW: SC == [c_0..c_{K-1}, SC_SENT] (aligned after last block) -----
            while True:
                c = SC.popleft()
                if c == SC_SENT:
                    SC.append(SC_SENT); break
                out.append(c - OFFSET)
                SC.append(OFFSET)          # reset accumulator
            continue
        # ----- BLOCK: x is a real 'a'. run K MACs -----
        a = x
        # load a into holder (drain any stale, then push)
        if H: H.popleft()
        H.append(a)
        BP = K
        while True:
            av = H.popleft(); H.append(av)     # r H ; s H reenq
            assert av == a
            b = SB.popleft(); SB.append(b)      # r SB ; s SB reenq
            prod = a*b                           # * (B kept =a)
            c = SC.popleft()                     # r SC
            c = c + prod                         # +
            SC.append(c)                         # s SC store
            BP -= 1                              # m
            if BP == 0: break                    # d (loop while BP>0)
        # after K MACs SC front == SC_SENT (aligned); realign identity: pop SENT, reenq
        s = SC.popleft(); assert s == SC_SENT, ("block-align", s)
        SC.append(SC_SENT)

def naive(N,M,K,A,B):
    C=[]
    for i in range(N):
        for j in range(K):
            s=0
            for t in range(M):
                s+=A[i*M+t]*B[t*K+j]
            C.append(s)
    return C

if __name__=="__main__":
    import random
    random.seed(1)
    tests=[(2,2,2,[1,2,3,4],[5,6,7,8]),
           (2,3,2,[1,0,-1,2,3,1],[4,5,6,7,8,9])]
    for _ in range(200):
        N=random.randint(1,16);M=random.randint(1,16);K=random.randint(1,16)
        A=[random.randint(-99,99) for _ in range(N*M)]
        B=[random.randint(-99,99) for _ in range(M*K)]
        tests.append((N,M,K,A,B))
    ok=True
    for N,M,K,A,B in tests:
        try:
            got=matmul_tight(N,M,K,A,B)
        except AssertionError as e:
            ok=False; print("ASSERT",N,M,K,e); break
        exp=naive(N,M,K,A,B)
        if got!=exp:
            ok=False; print("FAIL",N,M,K); print("got",got[:8]); print("exp",exp[:8]); break
    print("ALL OK" if ok else "FAILED", "tested", len(tests))
