"""Reusable littleman builders extracted from the sort-numbers solution.

These sit ON TOP of tools/littleman.py (do not edit that file). They capture the
patterns that made a branchy, looping single-man program tractable to hand-assemble:

  * Placer        - a collision-checking wrapper around Program.put (catches two
                    glyphs landing on one cell — the #1 hand-assembly bug).
  * fifo_ring     - a data ring of guaranteed capacity built from two pipes + a
                    relay man (littleman forbids self-loop pipes, so a ring needs
                    a second room that just does `r;s` forever).
  * relay_man     - the 3x2 `r;s` forever loop used as the ring's relay.
  * countdown_loop / while_bp - backpack (BP) countdown loop skeleton.

Plus, documented as comments, the two control-flow IDIOMS that the whole solution
is built from:

  COMPARE-AND-BRANCH (three-way, no extra register):
    ... A=x, B=y ...          # operands in A and B
    '-'                        # A = x - y   (B preserved = y)
    'X'                        # turn: A>0 -> CW, A<0 -> CCW, A==0 -> straight
    Route the three outgoing directions to <, ==, > handlers. To collapse to a
    two-way test put the '==' (straight) exit through a turn glyph that merges it
    into whichever side is arithmetically equivalent (for min/max, '==' joins the
    "keep either" branch for free).

  EQUALITY-VS-CONSTANT while keeping a live value in B:
    If B already holds t and you want to test t==K without losing t:
      '`K`'                    # A = K   (t still in B)
      '-'                      # A = K - t   (B == t preserved)
      'X'                      # straight (A==0) => t==K ; turn => t!=K
    This is how the sentinel/marker is detected without a 4th register.

  LOOP-BACK RULE (learned the hard way): a while-check cell must be ENTERED FROM
  THE SAME DIRECTION on the initial and the loop-back path. Route both into a
  shared feeder cell. Corridors may CROSS each other through SPACE cells (a space
  is a no-op that preserves heading); they may never cross a foreign glyph cell.
  Build straight corridors as [turn-glyph]+spaces+[turn-glyph], never a run of
  '>'/'<' fill, so crossings land on spaces.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import littleman as lm


class Placer:
    """Program wrapper whose put() refuses to overwrite a differing glyph.

    Almost every layout bug in a hand-assembled walking program is two glyphs
    colliding on one cell (an op landing on a corridor, a corridor crossing an
    op). Placer turns that from a silent wrong-answer into a loud exception."""
    def __init__(self, program=None):
        self.p = program or lm.Program()
        self.placed = {}

    def put(self, x, y, ch):
        if (x, y) in self.placed and self.placed[(x, y)] != ch:
            raise ValueError(f"COLLISION at {(x, y)}: {self.placed[(x, y)]!r} vs {ch!r}")
        self.placed[(x, y)] = ch
        self.p.put(x, y, ch)
        return self

    def vrun(self, x, y, s):
        """Place a vertical (southward) run of glyphs — e.g. a `12345` literal
        the man reads while walking south."""
        for i, c in enumerate(s):
            self.put(x, y + i, c)
        return self

    def hrun(self, x, y, s):
        """Place a horizontal (eastward) run of glyphs."""
        for i, c in enumerate(s):
            self.put(x + i, y, c)
        return self

    def corridor_v(self, x, y0, y1, turn_in, turn_out):
        """A vertical space-corridor: only the two endpoints get turn glyphs, the
        interior stays spaces so other corridors may cross it safely."""
        self.put(x, y0, turn_in)
        self.put(x, y1, turn_out)
        return self


def relay_man(pl, x, y):
    """Place a relay man at (x,y) facing east that forever does `recv;send` using
    its room's single incoming and single outgoing pipe. Footprint: 4 wide x 2 tall
    starting one cell east of (x,y). The man's room must have exactly one incoming
    and one outgoing pipe so `r`/`s` are unambiguous."""
    pl.p.man(x, y)
    pl.put(x + 1, y, '>'); pl.put(x + 2, y, 'r'); pl.put(x + 3, y, 'v')
    pl.put(x + 1, y + 1, '^'); pl.put(x + 2, y + 1, 's'); pl.put(x + 3, y + 1, '<')
    return pl


def ring_capacity(pipe1_len, pipe2_len):
    """A ring = pipe1 (proc->relay) + relay register + pipe2 (relay->proc).
    Max values that can circulate = pipe1_len + 1 + pipe2_len. Size the pipes so
    this is >= (max list length + 1 for the sentinel marker)."""
    return pipe1_len + 1 + pipe2_len


# --- the tested solution builder (kept here so the .man is reproducible) ---
def build_sort():
    """Rebuild the submitted sort-numbers program. Returns an lm.Program.
    Selection/bubble sort over a FIFO ring with a sentinel marker; see report."""
    from importlib import util
    here = os.path.dirname(os.path.abspath(__file__))
    # the canonical builder lives next to this file as _build.py
    spec = util.spec_from_file_location("_sortbuild", os.path.join(here, "_build.py"))
    mod = util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.build()[0]


if __name__ == "__main__":
    p = build_sort()
    import json
    print(p.render())
    print("footprint", p.footprint())
    print(json.dumps(p.grade("sort-numbers")))
