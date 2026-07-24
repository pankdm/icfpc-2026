"""Reusable littleman DSL helpers discovered building the 'brackets' solution.

Promotion candidates for tools/littleman.py PATTERNS section:

  route(p, pts): lay a MAN-path (not a pipe) through orthogonal waypoints — places a
    direction arrow at each segment start; straights are left as spaces (nops the man
    walks through). Use to wire a branch/return of one little man to a target cell.
    Arrows are placed at pts[0..n-2]; the final waypoint is the arrival cell (leave it
    as the target instruction, e.g. a '>' merge or an 'r').

KEY LAYOUT LESSONS (oracle-verified):
  * A room's '>' '<' '^' 'v' are ABSOLUTE direction-sets, not relative turns, so any
    man arriving at a '>' cell from ANY direction leaves heading east. This makes MERGE
    points trivial: route several branches into one '>' and they all continue together.
  * With exactly ONE incoming and ONE outgoing pipe on a room, `r`/`s` are unambiguous
    regardless of the man's position (nearest-of-one). So a pipe may attach at ANY
    border cell; you do NOT need to route it to the r/s cell. Prefer single-in/single-
    out rooms to avoid nearest-pipe reasoning entirely.
  * A pipe's START cell's backward neighbour must sit on the SOURCE room border and the
    END cell's forward neighbour on the DEST border; leave >=1 clear cell of gap so the
    arrowhead never lands ON a room border (that corrupts the wall / room detection).
  * Register wall: `r` clobbers A, and every binary op is `A = A op B`, so only ONE
    value survives a read (in B). A single man cannot hold stack + position + classify.
    Split across men connected by FIFO pipes; blocking `r`/`s` auto-synchronise them.
  * A do-while loop reads before checking the counter and DEADLOCKS on empty input
    (n=0). Use a check-first (while) loop: CHECK cell ('d'/'a' on BP, or X on A) at the
    top, body below returning to a dedicated feed '>' just before the CHECK.

The brackets pipeline (see build.py): I -> R -> C -> M -> O, three little men.
  R (reader): reads n, BP=n countdown; per char sends [char, position]; at end sends
     [0, n+1].  Position lives in B (survives the input read).
  C (classifier, stateless): char -> signal = mag*sign  (mag=char>>5 in {1,2,3},
     sign=+1 opener / -1 closer via s3 = (w^2-3w+1), w=char&3); 0 for the end marker.
     Sends [signal, position].  Uses an inner count-multiply while-loop.
  M (stack machine): base-3-ish stack S in B (sentinel=1, push S=3S+mag via +S+S+S,
     digit=mag so NO subtraction). X on signal 3-ways to END / PUSH / POP.
       PUSH: A=mag,+,+,+,M.
       POP : T=S-mag; divmod T/3 -> q,r; then z = q - r*(q+1) via BP=r count-subtract;
             z>0 => match (S=q), else offence (output the position, halt).
       END : if S==1 output 0 (balanced) else output n+1 (unclosed).
     Offence / end handlers are LOCAL 'rsH' / 'r0sH' (each `s` reaches the single out
     pipe), so no long output wiring is needed.
"""
import littleman as lm

def route(p, pts):
    """Lay a man-path: arrow at each segment start; straights left as spaces."""
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i + 1]
        dx = (x1 > x0) - (x1 < x0); dy = (y1 > y0) - (y1 < y0)
        p.put(x0, y0, lm.VEC2ARROW[(dx, dy)])
