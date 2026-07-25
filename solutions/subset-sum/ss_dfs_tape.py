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
  * KEEPER descend decision ALU (the 3-register crux): scratchpad/ss_keeper.py
    passes all 5 cases (solution / can't-reach prune / include / exclude / v==rem
    boundary) using only A,B (remaining persists in B across the v_d read; branch
    via `X` sign-turn). This retires the register-pressure unknown prior agents hit.
STILL TO BUILD (integration of known patterns, no unsolved crux):
  backtrack keeper (mirror of descend + decstack pop), stack-man wiring, head
  cursor + head<->keeper pipe protocol, dynamic counter-loader (+ sentinel &
  target routing), output reverse-emit (count then selected v_i ascending).

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
import sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/tools')
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
    p.save('/Users/visenbaev/icfpc26/solutions/subset-sum/ss_dfs_tape.man')
    print(p.render())
    print('footprint', p.footprint())
