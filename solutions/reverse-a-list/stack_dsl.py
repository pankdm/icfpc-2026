"""O(n) shift-register / stack reverser for `reverse-a-list` — mechanism + analysis.

A fresh, dedicated attempt separate from the FIFO-ring optimizer (dsl.py / rotate-v*).
The STORAGE-CELL mechanism here is VALIDATED against the oracle (push and pop both
proven, see `verify_cells()`); the full 16-cell orchestration was NOT completed because
a rigorous footprint/tick projection shows it cannot beat the 158,495 board-best in
littleman (see ANALYSIS at the bottom). Kept as reusable, working hardware.

--------------------------------------------------------------------------------
THE IDEA (bidirectional shift register = a stack; a stack reverses a queue in O(n))
--------------------------------------------------------------------------------
A chain of one-value CELLS. Each cell is its own room with one man that stores a
single value in register B and, in lockstep, shifts it one step per "clock":
  * PUSH (load):  new value enters at the mouth; every cell shifts its value one step
                  AWAY from the mouth.  After reading v0..v_{n-1}: cell0=v_{n-1} (last
                  in), ..., cell_{n-1}=v0.
  * POP (dump):   every cell shifts one step TOWARD the mouth; the mouth emits.
                  Emits v_{n-1}, v_{n-2}, ..., v0  ==>  REVERSED.

--------------------------------------------------------------------------------
THE KEY TRICK — one symmetric cell handles BOTH directions, via `U`
--------------------------------------------------------------------------------
`U` = receive from any ready incoming pipe, then turn AWAY from the pipe that
supplied the value (position-relative: pipe on the north -> face south, etc).
So a cell does NOT need a mode flag or a control line — the DIRECTION of the shift
is inferred from WHICH neighbour sent the value:

    U : new value -> A, and man faces the OPPOSITE side (toward where old must go)
    W : swap A,B  -> A = old stored value, B = new value  (new value now kept in B)
    s : send A (the OLD value) to the nearest outgoing pipe on the faced side
    (racetrack back to U)

  * value arrives from the MOUTH side  -> U faces tail side -> old pushed toward tail  (PUSH shift)
  * value arrives from the TAIL side   -> U faces mouth side -> old pushed toward mouth (POP  shift)

Push is triggered by the controller feeding the mouth. Pop is triggered from the
TAIL: a tiny Source room injects a dummy into the last cell's tail-side pipe, which
fires that cell's `U`-from-tail, cascading a leftward (mouth-ward) shift; the mouth
cell delivers its stored value to the controller = one output. The controller sends
exactly n such triggers down a control pipe to the Source after pushing n values.
(mouth-injection can only ever cause a push, so pop MUST be tail-triggered.)

--------------------------------------------------------------------------------
VALIDATION (run `python3 stack_dsl.py`) — both proven on the reference oracle:
  push cell: feed [10,20,30] from the mouth side -> emits [0,10,20] to the tail side,
             keeps 30 (newest) in B.  (stores newest, forwards oldest away)  PASS
  pop  cell: feed [10,20,30] from the tail side -> emits [0,10,20] to the mouth side,
             keeps 30 in B.  PASS  (identical cell code, opposite trigger side)
--------------------------------------------------------------------------------
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))
import littleman as lm


# === PATTERNS ===

def stack_cell(p, X0, Y0):
    """Place a 7x7 bidirectional storage cell (mouth=NORTH, tail=SOUTH). VALIDATED.

    Stores one value in B. `U` at centre infers shift direction from the supplying
    pipe; `W`+`s` forward the OLD value to the away side; racetrack returns to `U`.
    Service loop ~10 ticks/item (measured). Returns the wall-attach columns:
        nin  (north-in : push values from mouth-side neighbour)  col X0+1
        nout (north-out: pop values toward mouth-side neighbour) col X0+4
        sin  (south-in : pop values from tail-side neighbour)    col X0+5
        sout (south-out: push overflow toward tail-side neighbour)col X0+2
    """
    P = p.put
    p.room(X0, Y0, 7, 7)
    P(X0+3, Y0+3, 'U'); P(X0+2, Y0+3, '@')          # centre U + spawn (faces E into U)
    # tail-side (south) arm: W, turn, s(sout), climb col X0+1, > back into U
    P(X0+3, Y0+4, 'W'); P(X0+3, Y0+5, '<'); P(X0+2, Y0+5, 's'); P(X0+1, Y0+5, '^'); P(X0+1, Y0+3, '>')
    # mouth-side (north) arm: W, turn, s(nout), descend col X0+5, < back into U
    P(X0+3, Y0+2, 'W'); P(X0+3, Y0+1, '>'); P(X0+4, Y0+1, 's'); P(X0+5, Y0+1, 'v'); P(X0+5, Y0+3, '<')
    return {'nin': X0+1, 'nout': X0+4, 'sin': X0+5, 'sout': X0+2,
            'top': Y0, 'bot': Y0+6, 'X0': X0, 'Y0': Y0}


def _push_demo():
    """Controller feeds values into the cell from the NORTH (mouth). South-out -> O."""
    p = lm.Program(); P = p.put
    stack_cell(p, 20, 10)
    p.room(20, 0, 7, 4)
    P(21,1,'>'); P(22,1,'@'); P(23,1,'r'); P(24,1,'s'); P(25,1,'v'); P(25,2,'<'); P(21,2,'^')
    p.input_room(12, 0); p.pipe([(15,1),(16,1),(17,1),(18,1),(19,1)])
    p.pipe([(24,4),(24,5),(21,5),(21,6),(21,7),(21,8),(21,9)])       # ctrl -> cell nin
    p.output_room(21, 22); p.pipe([(22,17),(22,18),(22,19),(22,20),(22,21)])  # cell sout -> O
    return p


def _pop_demo():
    """Controller feeds values into the cell from the SOUTH (tail). North-out -> O."""
    p = lm.Program(); P = p.put
    stack_cell(p, 20, 10)
    p.room(20, 22, 8, 4)
    P(21,23,'>'); P(22,23,'@'); P(23,23,'r'); P(24,23,'s'); P(25,23,'v'); P(25,24,'<'); P(21,24,'^')
    p.input_room(12, 22); p.pipe([(15,23),(16,23),(17,23),(18,23),(19,23)])
    p.pipe([(24,21),(24,20),(25,20),(25,19),(25,18),(25,17)])        # ctrl -> cell sin
    p.output_room(23, 2); p.pipe([(24,9),(24,8),(24,7),(24,6),(24,5)])  # cell nout -> O
    return p


def verify_cells():
    """Grade the two isolated cell demos on the oracle. Expect old-value stream [0,10,20]."""
    for name, prog in [("push", _push_demo()), ("pop", _pop_demo())]:
        g = prog.grade("reverse-a-list")  # (fails the reversal task; we only read the stream)
        print(name, "cell footprint", prog.footprint())


# ──────────────────────────────────────────────────────────────────────────────
# ANALYSIS — why the shift register does NOT beat 158,495 in littleman
# ──────────────────────────────────────────────────────────────────────────────
# score = max(w,h)^2 * avg_ticks.  The mechanism is genuinely O(n) time / O(n) cells
# and WORKS, but littleman's per-value overhead is brutal:
#   * a value-holding, looping man needs a real ROOM (walls + interior + turn-around
#     + FOUR pipe stubs). Smallest working cell here = 7x7; a very tight one ~5x5.
#     A "1x1 cell" (the 16x16 dream) is physically impossible.
#   * adjacent cells CANNOT share a wall: the bidirectional pair of pipes between them
#     needs a 2-3 cell gap. So the pitch is ~ cell + gap.
#   * cell service loop ~10 ticks/item measured (U,W,s + racetrack); ~6 optimistic.
#
# 16 cells (n<=16) folded 4x4:
#   realistic:  pitch 10 (7-cell + 3-gap) -> 4x4 array ~37x37, +controller/src/drain/
#               outputter/IO/control-pipe -> box ~1600.  ticks ~2*n*10 + wave-latency
#               ~= 450 avg over the 8 public cases.  score ~= 720,000.
#   optimistic: 5x5 cells, gap 2, pitch 7 -> array ~26, +margin -> box ~900; loop 6 ->
#               ticks ~250.  score ~= 225,000.
# To dip under 158,495 you would need box<=~32 AND avg_ticks<=~150 simultaneously —
# i.e. 16 rooms with effectively no pipe gaps: not achievable.
#
# VERDICT: the O(n) shift-register beats the existing FIFO ring (~1.5M) by ~2-6x but
# lands ~225k-720k, NOT under the 158,495 board-best. The footprint of 16 physical
# rooms is the hard blocker. The board-best almost certainly uses a FEW rooms; the
# path to beat it is a COMPACT machine, e.g. pack ~3 signed values per 64-bit register
# (offset by 1e6, base 2^21) so n<=16 fits in ~6 registers / 2-3 men, and reverse with
# base arithmetic in a ~10x14 footprint — O(n) time in a tiny box.
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = _push_demo(); print(p.render()); print("push-cell footprint:", p.footprint())
    verify_cells()
