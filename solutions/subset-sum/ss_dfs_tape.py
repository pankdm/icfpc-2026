#!/usr/bin/env python3
"""ss-dfs Stage 1/2 — VERIFIED walking-head value tape (the DFS foundation).

This builds and validates the core mechanism the branch-and-bound DFS machine
needs: an O(1) indexed value tape that supports *repeated* access (DFS revisits
every depth thousands of times). Prior agents were blocked on "DFS backtrack
needs O(1) access but a FIFO belt pops O(n)". This tape solves that.

WHAT IS VERIFIED ON THE ORACLE (see also scratchpad/ss_proto.py, ss_revisit.py):
  * LOAD: a loader man reads input values and distributes v_i to storage cell i.
  * WALK-READ: a head man walks a corridor; at column c it `r`s the value from
    the storage above column c in O(1) (nearest-incoming pipe = that column's).
    4 values loaded then walk-read back to output in 31 ticks. [ss_proto.man]
  * REVISIT: a head re-reads the SAME cell hundreds of times; the storage man
    auto-refills its pipe (bare `s`-loop, value constant in A), so every revisit
    returns the same value with no crash. [ss_revisit.man]  <-- the key DFS enabler.

STORAGE CELL (5w x 4h), r/w column = X+2:
      +---+
      |@rv|      @ (nop,E) -> r: load v_d once (nearest incoming = loader pipe)
      |>s<|      then bounce >s< on the bottom row forever, `s` -> head pipe
      +---+      (nearest outgoing). A holds v_d permanently -> pipe stays stocked.
  A blocked `s` (pipe full) parks and retries -> auto-refill, no over-send.

HEAD reads at column c with `r` (nearest incoming = storage above c). Storage
columns are GAP apart; the head walks GAP cells per depth step (~few ticks).

================================================================================
FULL DFS ARCHITECTURE (resolved; register-pressure crux solved) — TO BUILD NEXT
================================================================================
Iterative model: solutions/subset-sum/ss_dfs_iter_model.py (7/7, case6=224,015
steps). Budget 15M ticks => <=66 ticks/step; revisit loop is ~8 ticks so the
tape read is cheap; the controller must stay tight.

Three cooperating men (separates ROAMING from STATE — the key to fitting 3 regs):
  1. HEAD (cursor): physical column = DFS depth d. HEADING = MODE (East=descend,
     West=backtrack). Maintains todoTotal (= suffix sum from d) in a register:
     stepping past d it reads v_d and does todoTotal-=v_d (descend) / +=v_d
     (backtrack) — direction only, no decision needed. Per step: read v_d, update
     todoTotal, send (v_d,todoTotal) to KEEPER, receive a command, act (turn/move
     or go to OUTPUT). Leaf = a SENTINEL cell after v_{n-1} (loader writes it);
     reading the sentinel => backtrack.
  2. KEEPER (ALU): holds `remaining` (= target - runningSum) as its ONLY
     persistent register value (that is why 3 registers suffice — see below).
     Per descend msg: if remaining==0 -> SOLUTION; elif remaining>todoTotal ->
     tell head BACKTRACK (can't-reach prune); else read v_d: if v_d<=remaining
     -> INCLUDE (remaining-=v_d, push bit 1) else EXCLUDE (push bit 0); reply
     INCLUDE/EXCLUDE (both => head moves deeper/East). Per backtrack msg: pop
     bit; if 1 (was include) remaining+=v_d, push 0, reply GO-RIGHT (re-descend
     from d+1); if 0 reply GO-LEFT (keep backtracking). d==0 backtrack -> NO-SOLN.
  3. STACK-MAN (decstack coprocessor): holds the include/exclude bit-stack in ITS
     OWN registers where shifts work (push = A=A<<1|bit via `{`/`|`; pop = bit=A&1
     then `}`). KEEPER pushes/pops via a small pipe protocol. This offloads the
     decstack so the KEEPER never has to shift it. A working bit-stack push/pop
     pattern already exists: solutions/brackets/stack2.man (BP-based).

VERIFIED SO FAR (oracle-checked, committed):
  * Stage 1/2 tape: load + O(1) walk-read + revisit (this file; ss_proto/ss_revisit).
  * KEEPER descend decision ALU (3-register crux): scratchpad/ss_keeper.py, 5/5 cases.
  * HEAD<->KEEPER round-trip + addressing: scratchpad/ss_rt, ss_rt2. A roaming head
    CANNOT `r` a fixed remote pipe (per-column value pipes are always nearest) UNLESS
    disambiguated by a TALL room: value pipes on the TOP border, keeper pipe on the
    BOTTOM border, separated by >n rows. Head has ONE outgoing (H2K) so `s` is
    unambiguous; reads pick value(top)/cmd(bottom) by row.
  * KEEPER LOOP: scratchpad/ss_kloop.py, [300,120,180,50]->[180,0,9], ~20 ticks/value.
  * INTEGRATED DESCEND: scratchpad/ss_desc2.py. Head walks column "dips"
    (r v top / s->H2K / down / r cmd bottom / X: cmd<0 continue-East up-channel->next
    dip, cmd>0 solution), keeper loops deciding & driving via K2H. Verified include
    ([120,180,50]->8) AND exclude ([400,300,50]->8, excl 400 then incl 300->rem0).
  * STACK-MAN decstack: scratchpad/ss_stack.py. Bit-stack in one register:
    push=bit+2*stack (A=bit,B=stack -> '+' '+'); pop=stack/2 via '/' (q=newstack,
    rem=popped bit). [1 0 1 -1 -1 -1]->[1,0,1]; [1 -1 0 1 -1 -1]->[1,1,0]. LIFO OK.
  * BIDIRECTIONAL HEAD: scratchpad/ss_bt.py. Two travel rows RE(descend/East) &
    RW(backtrack/West) drop into shared per-column SHAFTs; directional come-ups
    (go-right->RE col+1, go-left->RW col-1); sentinel/leaf column loaded with 0.
    Descend verified through the bidirectional dips ([120,180,50] t300 -> 8). cmd
    encoding: -1 go-right(E), +1 go-left(W), 0 done.
  PIPE GOTCHAS (cost real debugging): (a) two opposite-flow pipes in ADJACENT columns
  break the parser -> separate them by >=1 blank col; (b) a pipe START cell must be
  OUTSIDE the source room wall (not ON it); (c) H2K/K2H must attach at head-bottom
  columns that are NOT dip channels (dip c uses cols c..c+3); (d) a looping man's last
  op must leave a row to TURN before the far wall (loopback W then `>` then up-channel).
STILL TO BUILD (only INTEGRATION remains; leaf+geometry+stack primitives all proven):
  A. 2-MODE KEEPER + stack wiring — THE piece that closes the DFS loop. Replace ss_bt.py's
     descend-only keeper with two loop bodies (DESCEND/BACKTRACK) + transition, wired to the
     STACK-MAN via K2S(out: push bit / -1 pop-cmd) + S2K(in: popped bit). Algorithm verified
     correct for [200,180,120] t300 (1 backtrack -> [180,120]): push 1,0,0 ; sentinel
     (rem=100!=0)->cmd+1 backtrack ; pop 0,0,1 ; at d0 bit=1 -> rem+=200=300, push0, cmd-1
     descend ; push 1,1 ; sentinel rem==0 -> solution. REGISTER FLOW (worked out):
       DESCEND(A=rem): M(B:=rem); r(A=v); W; X rem==0?->SOLUTION; else W; X v==0(sentinel)?
         ->W(A=rem),cmd+1->K2H,jump BACKTRACK ; else '-'; X v<=rem? incl:N(A=rem-v),push1->K2S,
         cmd-1->K2H ; excl:W(A=rem),push0->K2S,cmd-1->K2H ; loop.
       BACKTRACK(A=rem): M(B:=rem); POP FIRST (before recv v): 1,N(A=-1),s->K2S,r(A=bit) [B=rem];
         X bit>0? incl: r(A=v),'+'(A=v+rem),push0->K2S,cmd-1->K2H,jump DESCEND ; excl: r(A=v;
         CONSUME to avoid stale H2K),W(A=rem),cmd+1->K2H,loop.
     KEY subtlety: pop BEFORE recv v (backtrack needs rem+v+bit but pop clobbers A; rem safe in
     B, then include recv's v and '+' in one shot). Consume v in BOTH branches. Keeper has 3
     outgoing (K2H top / K2S left / O right) -> each `s` nearest its pipe; opposite-flow pipes
     >=1 col apart; a pipe start must be OUTSIDE the room wall (gotchas from ss_desc2).
  B. d==0 backtrack (leftmost, nothing to flip) -> emit 0 (no solution).
  C. can't-reach prune (todoTotal on the HEAD, sent to keeper) — keeps case-6 at 224k nodes
     for the 15M budget (without it ~1.7x -> ~380k steps, risky).
  D. LOADER: dynamic n (BP counter) + sentinel + TARGET read from input & routed to keeper
     AROUND the tall head room (target is a `literal` today).
  E. OUTPUT: count (popcount) then selected v_i ASCENDING (decstack pops give descending ->
     reverse via 2nd stack or left-walk collect; cf. ss.man Pass RE).
  Estimated case-6: ~30-50 ticks/node x 224k ~= 7-11M < 15M cap.

WHY 3 REGISTERS SUFFICE (the crux prior agents hit):
  A man has A,B,BP. Every read writes A; BP cannot be shifted-into or read back
  as a value (only `]`>>1, `m`-1, `x`/`d`/`a` turn-tests, `b`:=A). So a shiftable
  decstack cannot live in BP, and remaining/decstack both being recoverable
  values would need A and B, but reading v_d clobbers A. RESOLUTION: offload
  todoTotal to the HEAD, decstack to the STACK-MAN; then the KEEPER's only
  persistent value is `remaining` (A), leaving B/BP free scratch for the v_d read
  + compares (M copies A->B without clobber; `-` then sign-test via `X`).

KEEPER descend micro-op (A=remaining in):
  test A==0 (X: ==0 straight=SOLUTION, >0 continue; remaining>=0 always)
  M (B:=remaining) ; recv todoTotal->A ; `-`(A=todo-rem) ; X(<0 => BACKTRACK) ...
  restore remaining ; M(B:=remaining) ; recv v_d->A ; `-`(A=v_d-rem) ;
  X(<=0 => INCLUDE: newrem=-A via N; >0 => EXCLUDE: newrem=B via W) ; push bit.

OUTPUT stage: on SOLUTION, emit COUNT (=popcount of decstack) then the selected
v_i in INCREASING index order. decstack pops give DECREASING index, so reverse:
pop includes onto a 2nd stack (or head walks left collecting, then emits). On
NO-SOLUTION emit single 0. (See ss.man Pass K/RE for a reference reverse-emit.)

ADDRESSING NOTES (oracle-confirmed): nearest-pipe = Manhattan to attach, reading-
order ties. Keep exactly one incoming + one outgoing per storage room. For the
head, if it must read TWO tapes at one column (e.g. value + suf), feed them from
opposite walls and read at different rows so each is strictly nearest — but the
resolved design avoids a suf-tape (todoTotal maintained on the head) => value
tape only. Men never crash a wall unless output already settled (fatal aborts
the whole program): the LOADER must `H`, not crash.
================================================================================
"""
import os as _os; _REPO = _os.path.abspath(__file__).split('/solutions/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm


def build_tape_readback(values):
    """VERIFIED builder: load `values` into a tape, walk-read them back to O.
    Output == values in order. Proves load + O(1) walking read."""
    n = len(values)
    GAP = 6
    p = lm.Program(); placed = {}
    def C(x, y, ch):
        if (x, y) in placed and placed[(x, y)] != ch:
            raise SystemExit(f"COLLISION {(x,y)}: {placed[(x,y)]!r} vs {ch!r}")
        placed[(x, y)] = ch; p.put(x, y, ch)
    def room(x, y, w, h, g="+-|"):
        p.room(x, y, w, h, g)
        for i in range(w):
            placed[(x+i, y)] = p.get(x+i, y); placed[(x+i, y+h-1)] = p.get(x+i, y+h-1)
        for j in range(h):
            placed[(x, y+j)] = p.get(x, y+j); placed[(x+w-1, y+j)] = p.get(x+w-1, y+j)

    read_cols = [2 + GAP*i for i in range(n)]

    # LOADER (top): read each value, send down to its storage column
    LX1 = read_cols[-1] + 3
    room(0, 0, LX1+1, 3)
    p.man(1, 1)
    for c in read_cols:
        C(c, 1, 'r'); C(c+1, 1, 's')
    C(LX1-1, 1, 'H')                      # loader must halt (never crash a wall)

    # STORAGE cells (middle)
    SY = 6
    for c in read_cols:
        X = c-2
        room(X, SY, 5, 4)
        C(X+1, SY+1, '@'); C(X+2, SY+1, 'r'); C(X+3, SY+1, 'v')
        C(X+1, SY+2, '>'); C(X+2, SY+2, 's'); C(X+3, SY+2, '<')

    # HEAD (bottom): walk-read each and send to O
    HY = 12; HX1 = read_cols[-1] + 4
    room(0, HY, HX1+1, 3)
    p.man(1, HY+1)
    for c in read_cols:
        C(c, HY+1, 'r'); C(c+1, HY+1, 's')

    # pipes: I->loader ; loader->storage ; storage->head ; head->O
    p.input_room(-5, 0); p.pipe([(-2, 1), (-1, 1)])
    for c in read_cols:
        p.pipe([(c, 3), (c, SY-1)])
        p.pipe([(c, SY+4), (c, HY-1)])
    p.output_room(HX1+3, HY); p.pipe([(HX1+1, HY+1), (HX1+2, HY+1)])
    return p


if __name__ == '__main__':
    vals = [11, 22, 33, 44]
    p = build_tape_readback(vals)
    p.save(_REPO + '/solutions/subset-sum/ss_dfs_tape.man')
    print(p.render())
    print('footprint', p.footprint())
