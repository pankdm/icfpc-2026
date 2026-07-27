#!/usr/bin/env python3
"""Generate a complete LLLM interpreter as a littleman .man program.

    python3 solutions/little-little-little-man/build_lllm.py [--out FILE]

Semantics live in lllm_flow.py and are gated by lllm_sim.py (10/10 public cases
in Python).  This file is *only* geometry, and it is built around one invariant
that makes both the pipe bindings and the control flow provable at build time:

  PORTS ARE COLUMNS.  Every device (holder, ring, input, display) attaches to
  the controller's TOP wall only.  The distance from an instruction at (x, y)
  to an attachment at (c, top-1) is (y-top+1) + |x-c|, so among attachments
  that all share row top-1 the NEAREST is simply the one with the closest
  column -- an `r`/`s` placed exactly on a device's column can never rebind.
  verify_bindings() (--verify) re-derives every binding the way the oracle
  does, through tools/pipecheck.py, and is what makes moving a pipe safe.

  CONTROL FLOW GOES EAST OR SOUTH.  A block is a row of ops entered from the
  west; `b d` turns a taken branch SOUTH, a fall-through keeps heading EAST.
  Each exit drops onto its own private row, runs WEST to a per-target highway
  column, and rides it to the target's entry row.  Highways cross exit rows on
  BLANK cells (a blank preserves heading), so no two routes ever share a turn
  glyph -- the classic generated-grid misroute cannot happen here.  A target may
  ALSO be fallen into from the block above (descend_east), in which case the
  lane glides its men east onto the very cell the falling man lands on.

WHAT COSTS WHAT.  The controller man never stalls -- profiling shows the
controller room executing one cell per tick -- so ticks are exactly the cells he
walks, and cost_model.py computes them to a constant +227.  Measured on the
current build: 64% is walking between PORT COLUMNS inside a block, 24% the
highway's west run and glide, 10% the highway's vertical ride.  Everything is
column spread and row count, which is why the three free permutations
(HOLDER_ORDER, BLOCK_ORDER, HOLDER_FLIP) are annealed by search_layout.py
against box x ticks rather than guessed.

Knobs are module constants / default args so tools/autotune.py can sweep them;
all DATA (colour table, character classes, the classifier hash) is computed
from dicts in lllm_tables.py, never written as a bare integer.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import layout as lay
import littleman as lm
import lllm_flow as F
import lllm_sim as SIM

# ---- tunable integer knobs -------------------------------------------------
HOLDER_PITCH = 3        # columns between neighbouring holder rooms
BAND_TIERS = 2          # rows of holder rooms stacked above the controller
TIER_GAP = 0            # blank rows between two tiers of holder rooms
HOLDER_W = 4            # holder room outer width
HOLDER_H = 6            # holder room outer height
PIPE_GAP = 3            # rows between the device band and the controller
PORT_GAP = 1            # columns between the non-holder port columns
IN_CLEAR = 3            # extra clearance east of the 3-wide input room
HWY_GAP = 0             # columns between neighbouring highway lanes
LEAD_IN = 0             # blank columns between the entry column and the ops
RING_LIFT = 7           # how far above the band the ring relay sits
DISP_GAP = 6            # routing columns between the band and the display
TAIL_PAD = 0            # spare rows under the last block
CODE_SLACK = 6          # spare code columns east of the last port column
                        # (6 is the least that costs no wrap; width is not the
                        #  binding dimension, so the rest was dead grid)

# Which holder gets which controller column.  A port op must sit on its own
# column, so whenever the next one is behind the cursor the ribbon wraps -- that
# costs walked cells AND a whole controller ROW, and height is what the box
# squares.  Searched by search_layout.py; apply_search.py writes the result here.
#
# DO NOT SEARCH THIS ON ROW COUNT.  An earlier attempt annealed rows alone
# (scratchpad/lllm_order_search.py) and reached 369 rows against 375, but graded
# 27% WORSE on ticks -- order sets both the wrap count and the walk length and
# the two trade off.  The objective has to be box x ticks, which is what
# cost_model.py exists to make cheap.
HOLDER_ORDER = [
    "KK", "PCOL", "SH", "AD", "HD",
    "RETM", "CD", "BL", "VLR", "OPR",
    "AL", "WW", "PA", "HHT", "PH",
    "NOTMF", "PATF", "NOTME", "PATE", "ADS",
]

# Block layout order, searched by search_layout.py against cost_model.py.
# Empty == use lllm_flow's own emission order.
BLOCK_ORDER = [
    "BOOT", "MASKS", "CELL_LOOP", "NONDIGIT",
    "CELL_CODED", "NOT_AT", "NOT_PLUS", "ROW_END",
    "PAD_ROWS", "LATER_PLUS", "PLUS_CHK_X", "ROOM_CHECK2",
    "FALLBACK", "P_STEP_B", "PATCH_BOT", "P_STEP_M",
    "P_ROT_B", "P_SPIN_B", "P_RW_B", "FIRST_PLUS",
    "REP_BODY", "REP_LOOP", "MASKS1B", "MASKS2",
    "PAD_BODY", "PAD_LOOP", "ROOM_CHECK", "PATCH_MID",
    "P_ROT_M", "P_SPIN_M", "P_RW_M", "PATCH_MID_NEXT",
    "PATCH_MID_INIT", "RENDER_INIT", "PATCH_INIT", "RENDER_DONE",
    "P_STEP_T", "P_ROT_T", "P_SPIN_T", "P_RW_T",
    "R_EMIT", "R_CHK", "R_LOOP", "FETCH_ROW",
    "ROT_BODY", "ROT_LOOP", "RING_READ", "FETCH_SAME",
    "FETCH_DONE", "STEP_TAIL", "ADV_N", "STEP",
    "ADV_S", "STEP_ALIVE", "DOTICK", "OP_DIGIT",
    "D_LOW", "ADVANCE", "ADV_W", "ADV_E",
    "OP_W", "ROUND_END", "NEXT_ROUND", "OP_S",
    "D_LOW2", "OP_E", "OP_N", "OP_X",
    "X_CW", "D_MID", "OP_SUB", "OP_ADD",
    "OP_M", "OP_H", "X_CCW",
]

# Holders whose DROP pipe takes the right-hand interior column, so that `hr`
# comes after `hw` in reading order.  Searched by search_layout.py.
HOLDER_FLIP = [
    "ADS", "AL", "CD", "HD", "KK",
    "OPR", "PATE", "PATF", "RETM", "VLR",
    "WW",
]

ARROW_S, ARROW_W, ARROW_E, ARROW_N = "v", "<", ">", "^"

# Port columns run west to east in this order.  It is load-bearing: every pipe
# that has to leave the band routes EAST, so a port may never have to cross the
# vertical of a port to its right.
#
# MEASURED DEAD END 2026-07-26.  All 5040 permutations were scored on the exact
# model: the best (rr before rs, so the hot `rr rs` of ROT_BODY stops wrapping)
# is worth 42.78B -> 41.27B.  Every one of them FAILS TO BUILD.  The horizontal
# runs of the pipes pin the order completely:
#   rs's west run to the relay crosses every column west of it  -> rs before rr
#   rr's east run from the relay crosses ds's vertical          -> rr before ds
#   dd's east run at disp_y-1 crosses ds's and da's verticals    -> ds<da<dd
# i.e. in < rs < rr < ds < da < dd is forced and only the unused `ot` may move.
# Do not re-search this without first re-routing the ring and display pipes.
PORT_ORDER = ("in", "ot", "rs", "rr", "ds", "da", "dd")


# ===========================================================================
# 1.  CFG shape
# ===========================================================================
def split_blocks(flow, order=None):
    """[(label, tokens)] in LAYOUT order; tokens keep their inline branches.

    Layout order is free -- every edge is explicit, so any permutation runs the
    same program -- and it is worth a lot: a `go` to the block laid out directly
    below is a 2-cell descend and costs ONE row, while every other edge pays a
    west run to a highway lane, the ride, the glide back east, and two rows.
    `order` is searched by search_layout.py; the entry block must stay first.
    """
    order = order or BLOCK_ORDER or flow.order
    assert sorted(order) == sorted(flow.order), "BLOCK_ORDER is stale"
    assert order[0] == flow.order[0], "the entry block must be laid out first"
    out = []
    for label in order:
        toks = flow.blocks[label]
        assert isinstance(toks[-1], tuple) and toks[-1][0] == "go", label
        out.append((label, toks))
    return out


def entry_labels(blocks):
    """Labels reached by an edge that is not a plain fall-through."""
    index = {b[0]: i for i, b in enumerate(blocks)}
    need = set()
    for i, (label, toks) in enumerate(blocks):
        for tok in toks:
            if not isinstance(tok, tuple):
                continue
            if tok[0] in ("br", "brbp"):
                need.add(tok[1])
            elif tok[0] == "go" and index[tok[1]] != i + 1:
                need.add(tok[1])
    return need


# ===========================================================================
# 2.  column plan
# ===========================================================================
class Columns(object):
    def __init__(self, blocks, holder_order, pitch=HOLDER_PITCH,
                 port_gap=PORT_GAP, hwy_gap=HWY_GAP, lead_in=LEAD_IN,
                 lanes=None, heat=None, code_slack=CODE_SLACK,
                 tiers=BAND_TIERS, port_order=PORT_ORDER, flip=()):
        self.hwy_targets = sorted(entry_labels(blocks))
        # A highway column is only busy between its highest join row and its
        # target row, and men cross an idle one on a BLANK cell, so targets with
        # disjoint row spans share a lane.  `lanes` maps target -> lane index.
        if lanes is None:
            lanes = {t: i for i, t in enumerate(self.hwy_targets)}
        self.lanes = lanes
        nlanes = max(lanes.values()) + 1 if lanes else 0
        # Every highway traversal costs (x_exit - lane) + (entry_col - lane), so
        # a lane column is worth 2 cells per traversal of every edge that uses
        # it: the HOTTEST lane belongs on the column closest to entry_col.  The
        # colouring only cares which targets share a lane, so re-indexing lanes
        # by heat is free -- and it was previously left in arbitrary order.
        order = sorted(range(nlanes),
                       key=lambda i: sum(heat.get(t, 0) for t, li in lanes.items()
                                         if li == i)) if heat else range(nlanes)
        x = 1
        lane_col = {}
        for i in order:
            lane_col[i] = x
            x += 1 + hwy_gap
        self.hwy = {t: lane_col[lanes[t]] for t in self.hwy_targets}
        self.entry_col = x + 1
        x = self.entry_col + lead_in
        self.port = {}
        for name in port_order:
            self.port[name] = x
            # The input ROOM is 3 cells wide and straddles its own port column,
            # so a neighbouring port's vertical would run alongside its right
            # wall and steal its binding.  Every other port is a bare pipe and
            # may be packed shoulder to shoulder.
            x += max(port_gap, IN_CLEAR) if name == "in" else port_gap
        # TIERED BAND.  A holder room is 4 wide (2 walls + a 2-cell ring) and
        # rooms on one row may not share a wall column, so a single row of
        # holders costs 5 columns each.  Stacking them in `tiers` rows drops
        # that to 3: neighbouring rooms are on DIFFERENT rows, so they may
        # overlap in the wall column, and an upper tier's two pipes descend
        # through exactly the 2-column gap its own tier leaves free below.
        #   tier 0:  X..X+3         pipes X+1, X+2      (X+6..X+9 next)
        #   tier 1:      X+3..X+6   pipes X+4, X+5
        # 3 is the floor for private rooms: 2 pipe columns plus the shared wall
        # column, and it does not improve with more tiers (4 tiers is 12 columns
        # for 4 holders, still 3 each).
        #
        # MEASURED DEAD END 2026-07-26: pitch 2 -- the arithmetic floor, since a
        # holder needs two pipe columns -- IS reachable on paper by putting all
        # 20 holders in ONE shared room as 2-column ring units.  It builds, and
        # verify_bindings passes (each s/r sits directly over its own pipe at
        # dx = 0, every other pipe at least one column further), width drops
        # 131 -> 111.  The ORACLE REFUSES IT: "room (29,18)..(70,23) has
        # multiple '@'s".  One man per room is a load-time rule, so a shared
        # bank would need the other 19 men forked in with `Y` at startup.
        self.holder_room_x = {}
        self.holder_tier = {}
        self.hr = {}
        self.hw = {}
        # WHICH of the two interior columns carries the DROP pipe is free: a
        # holder room has exactly one incoming and one outgoing pipe, so the
        # room's own r/s cannot mis-bind either way.  It matters a lot to the
        # controller though.  `get(h)` is `hr` then `hw`; with hr always on the
        # left, every get() on a WESTWARD ribbon row asks for a column behind
        # the cursor and costs a whole wrap row.  So the side is a per-holder
        # bit that search_layout.py picks.
        flip = flip or ()
        self.flip = set(flip)
        for i, name in enumerate(holder_order):
            self.holder_tier[name] = i % tiers
            self.holder_room_x[name] = x
            lo, hi = x + 1, x + 2
            self.hr[name], self.hw[name] = (hi, lo) if name in self.flip else (lo, hi)
            x += pitch
        x += HOLDER_W - pitch
        self.code_hi = x + code_slack
        self.width = self.code_hi + 3

    def of(self, tok):
        if isinstance(tok, tuple):
            if tok[0] == "hr":
                return self.hr[tok[1]]
            if tok[0] == "hw":
                return self.hw[tok[1]]
            if tok[0] in self.port:
                return self.port[tok[0]]
        return None


GLYPH = {"hr": "r", "hw": "s", "in": "r", "rr": "r", "ot": "s",
         "rs": "s", "da": "s", "dd": "s", "ds": "s"}


def tok_cells(tok, direction):
    """The glyph run a token occupies, IN WALK ORDER.

    A literal is read in the direction the man walks, so on a westward row the
    grid must hold it mirrored -- but the placer already writes these cells in
    walk order (it steps the cursor by the heading), so the digits must NOT be
    reversed here.  Reversing them too produced `61` where `16` was meant and
    was invisible on eastward rows, which is exactly how it survived until a
    16-wide raster row hit it.
    """
    if isinstance(tok, tuple):
        if tok[0] == "lit":
            return "`" + str(tok[1]) + "`"
        return GLYPH[tok[0]]
    return tok


# ===========================================================================
# 3.  place the code
# ===========================================================================
class CodePlacer(object):
    """Lays every block as a boustrophedon ribbon of op rows.

    A branch is INLINE: `b d` on an eastward row turns the taken arm south onto
    a private exit row and leaves the fall-through walking east on the same row,
    so a chain of branches costs one row each instead of a round trip each.
    Exit rows are handed out in the order the branches appear, i.e. in
    increasing column order, which is exactly what makes the drops legal: a
    later branch's southward drop crosses only the lanes of branches that turn
    off further west, and it crosses them on blank cells.
    """

    def __init__(self, grid, cols, top_row, edge_heat=None):
        self.g = grid
        self.c = cols
        self.y = top_row
        self.eheat = edge_heat or {}
        self.entry_row = {}
        self.joins = []
        self.lits = set()          # (row, x_open, x_close) of every REAL literal
        self.walk = {}             # label -> cells the man steps through
        self.edges = []            # (src, dst, lane_col, from_col, from_row)
        # --- exact walk model (see cost_model.py) ---------------------------
        # cum[label][i]  cells stepped from the block's first op cell up to and
        #                including token i (wraps included).
        # exit[(label,i)] cells stepped LEAVING the block at token i, up to and
        #                including the entry glyph of the successor block.
        self.cum = {}
        self.exit = {}
        self._rides_by_key = {}
        # label -> the column a highway must glide the man EAST to.  entry_col
        # for a block entered normally; the descend's own turn glyph for a block
        # that is BOTH fallen into from above and entered from a lane.
        self.entry_x = {}

    def place(self, blocks):
        c = self.c
        targets = set(c.hwy_targets)
        labels = [b[0] for b in blocks]
        # heat arriving at each label from somewhere OTHER than a given edge --
        # those are the men who have to glide east to wherever the fall lands
        in_heat = {}
        for lab, toks in blocks:
            for i, tok in enumerate(toks):
                if isinstance(tok, tuple) and tok[0] in ("br", "brbp", "go"):
                    in_heat[tok[1]] = in_heat.get(tok[1], 0) + self.eheat.get((lab, i), 0)
        st = {"x": c.entry_col + 1, "y": self.y, "d": 1, "pend": 0, "walk": 0}
        fresh = True                     # next block must be entered at entry_col

        def put(ch):
            self.g.put(st["x"], st["y"], ch)
            st["x"] += st["d"]
            st["walk"] += 1

        def descend(reverse):
            """Turn south, fall past every pending exit row, then face `reverse`."""
            self.g.put(st["x"], st["y"], ARROW_S)
            st["y"] += 1 + st["pend"]
            # 'v', then `pend` blank exit rows, then the turn glyph: 2 + pend
            st["walk"] += 2 + st["pend"]
            st["pend"] = 0
            self.g.put(st["x"], st["y"], ARROW_W if reverse < 0 else ARROW_E)
            st["d"] = reverse
            st["x"] += reverse

        def wrap():
            descend(-st["d"])

        def descend_east():
            """Fall into the next row FACING EAST, whatever we were doing.

            This is what lets a block be fallen into even though it is also a
            highway target.  A man arriving on the lane glides EAST along the
            target's row over blank cells, steps on the descend's own '>' and
            carries straight on -- byte for byte the state the falling man is
            in.  Landing WESTWARD could never work: the block's own ops lie west
            of the turn glyph, so the arriving man would run them backwards.

            Heading east already, one descend would face west, so it takes two
            -- which still costs the two rows a highway edge costs (its exit row
            plus the target's entry row) while replacing ~100 walked cells with
            four.
            """
            descend(-st["d"])
            if st["d"] < 0:
                descend(1)

        def need(n):
            if st["d"] > 0 and st["x"] + n - 1 > c.code_hi:
                wrap()
            elif st["d"] < 0 and st["x"] - (n - 1) < c.entry_col + 1:
                wrap()

        # A taken branch must turn SOUTH.  `d` (clockwise) does that while the
        # man walks EAST; walking WEST the same job is done by `a`
        # (counter-clockwise) -- PROBLEM.md lines 86-87.  Using the heading's
        # own glyph removes the forced turn-around that `face_east` used to pay
        # on every branch that landed on a westward row: worth ~40 rows, and
        # rows are what the box is squared on.
        BRANCH_TURN = {1: "d", -1: "a"}

        for bi, (label, toks) in enumerate(blocks):
            nxt = labels[bi + 1] if bi + 1 < len(labels) else None
            if fresh:
                st["x"], st["d"] = c.entry_col + 1, 1
                self.g.put(c.entry_col, st["y"], "@" if bi == 0 else ARROW_E)
                self.entry_x[label] = c.entry_col
            elif label in targets:
                # fell in from the block above AND reachable from a lane;
                # descend_east() guarantees the heading, so the lane can deliver
                # men onto this very cell
                assert st["d"] == 1, ("fell westward into target %s" % label)
                self.entry_x[label] = st["x"] - 1
            self.entry_row[label] = st["y"]
            fresh = False
            st["walk"] = 0
            cum = self.cum.setdefault(label, [])
            del cum[:]

            for ti, tok in enumerate(toks):
                kind = tok[0] if isinstance(tok, tuple) else None
                if kind in ("br", "brbp"):
                    need(4)
                    if kind == "br":
                        put("b")
                    put(BRANCH_TURN[st["d"]])
                    st["pend"] += 1
                    # the turn glyph is the cell just walked over, i.e. one step
                    # BEHIND the cursor in the current heading
                    self._lane(st["x"] - st["d"], st["y"] + st["pend"], tok[1],
                               label)
                    # taken arm: fall `pend` rows to the exit row, run west to
                    # the lane, ride it, glide east to the target's entry glyph.
                    self.exit[(label, ti)] = self._ride(
                        (label, ti), st["x"] - st["d"], st["y"] + st["pend"],
                        tok[1]) + st["pend"]
                elif kind == "go":
                    self.walk[label] = st["walk"]
                    cum.append(st["walk"])
                    tgt = tok[1]
                    # Falling into a block that is ALSO a highway target moves
                    # its entry cell east to wherever this ribbon happens to
                    # end, and every OTHER man arriving on the lane then has to
                    # glide out to it.  So it is only worth it when this edge
                    # carries more traffic than the rest put together; weigh the
                    # two in cells x traversals before committing.
                    fall = tgt == nxt
                    if fall and nxt in targets:
                        mine = self.eheat.get((label, ti), 0)
                        others = max(0, in_heat.get(tgt, 0) - mine)
                        dest = c.hwy[tgt]
                        gain = mine * (st["x"] + c.entry_col - 2 * dest - 4)
                        loss = others * (st["x"] - 1 - c.entry_col)
                        fall = gain > loss
                    if fall:
                        w0 = st["walk"]
                        if nxt in targets:
                            descend_east()       # lanes still deliver here
                        else:
                            descend(-st["d"])    # keep walking, no round trip
                        self.exit[(label, ti)] = st["walk"] - w0
                    else:
                        self.g.put(st["x"], st["y"], ARROW_S)
                        row = st["y"] + st["pend"] + 1
                        self.exit[(label, ti)] = (
                            2 + st["pend"]
                            + self._ride((label, ti), st["x"], row, tgt))
                        self._lane(st["x"], row, tgt, label)
                        st["y"] = row + 1
                        st["pend"] = 0
                        fresh = True
                    continue
                elif kind is not None and c.of(tok) is not None:
                    want = c.of(tok)
                    if (st["d"] > 0 and want < st["x"]) or \
                       (st["d"] < 0 and want > st["x"]):
                        wrap()
                    st["walk"] += abs(want - st["x"])
                    st["x"] = want
                    put(GLYPH[kind])
                else:
                    need(len(tok_cells(tok, st["d"])))
                    text = tok_cells(tok, st["d"])
                    x0 = st["x"]
                    for ch in text:
                        put(ch)
                    if text[0] == "`":
                        x1 = st["x"] - st["d"]
                        self.lits.add((st["y"], min(x0, x1), max(x0, x1)))
                cum.append(st["walk"])
        self.y = st["y"] + 1
        return self.y

    def _ride(self, key, x, row, target):
        """Cells from the exit row's '<' to the target block's entry glyph.

        The vertical leg is unknown for a FORWARD edge (the target row has not
        been placed yet), so the ride is recorded and resolved by finish().
        """
        dest = self.c.hwy[target]
        self._rides_by_key[key] = (x, row, target)
        return x - dest          # the eastward glide is added by finish()

    def finish(self):
        """Add each highway ride's vertical leg, now that every row is known."""
        for key, (x, row, target) in self._rides_by_key.items():
            dest = self.c.hwy[target]
            self.exit[key] += (abs(self.entry_row[target] - row)
                               + (self.entry_x[target] - dest))
        self._rides_by_key = {}
        return self

    def _lane(self, x, y, target, src=None):
        """Turn this exit row west and record its join onto the target's lane."""
        dest = self.c.hwy[target]
        self.g.put(x, y, ARROW_W)
        self.joins.append((dest, y, target))
        self.edges.append((src, target, dest, x, y))


def break_stray_literals(g, intended=(), verbose=False):
    """Kill every ACCIDENTAL literal the grid grew by coincidence.

    A backtick closes a literal for the backtick before it *in the direction the
    man walks*, so any two backticks with nothing but digits and spaces between
    them form one -- including a pair made of the closing tick of one intended
    literal and the opening tick of the next, and including pairs that line up
    VERTICALLY down a column the man drops through.  Crossing one silently
    overwrites A.  Intended literals are solid digit runs with no blanks, so
    dropping a '.' (an explicit no-op) into a blank cell of an offending span
    breaks the accident and can never break a real literal.
    """
    fixed = 0
    for axis in (0, 1):
        minx, miny, maxx, maxy = g.p.bounds()
        outer = range(minx, maxx + 1) if axis == 0 else range(miny, maxy + 1)
        inner = range(miny, maxy + 1) if axis == 0 else range(minx, maxx + 1)
        for a in outer:
            ticks = []
            for b in inner:
                x, y = (a, b) if axis == 0 else (b, a)
                if g.get(x, y) == "`":
                    ticks.append(b)
            for lo, hi in zip(ticks, ticks[1:]):
                if axis == 1 and (a, lo, hi) in intended:
                    continue
                span = [(a, b) if axis == 0 else (b, a) for b in range(lo + 1, hi)]
                cells = [g.get(x, y) for x, y in span]
                if not any(c.isdigit() for c in cells):
                    continue
                if not all(c.isdigit() or c == " " for c in cells):
                    continue
                blanks = [pt for pt, c in zip(span, cells) if c == " "]
                if not blanks:
                    raise RuntimeError("stray literal with no blank to break: "
                                       "axis=%d line=%d span=%d..%d" % (axis, a, lo, hi))
                x, y = blanks[len(blanks) // 2]
                g.put(x, y, ".")
                fixed += 1
    if verbose:
        print("broke %d stray literal spans" % fixed)
    return fixed


def estimate_ticks(placer, cols, counts):
    """Walked-cell tick model: cost is the path the controller man walks.

    Pipe latency is hidden (measured: a holder round trip = controller path
    length + 1), so ticks are just cells walked -- op path, plus for every
    control edge the westward exit lane, the ride down the highway and the
    glide back east into the target.
    """
    indeg = {}
    for src, dst, _c, _x, _y, _f in placer.edges:
        indeg[dst] = indeg.get(dst, 0) + 1
    total = 0.0
    for label, walk in placer.walk.items():
        total += counts.get(label, 0) * walk
    for src, dst, lane, x, y in placer.edges:
        trow = placer.entry_row.get(dst, y)
        cost = (x - lane) + abs(trow - y) + (cols.entry_col - lane)
        total += counts.get(dst, 0) * cost / max(1, indeg.get(dst, 1))
    return total


def colour_lanes(spans):
    """Interval-graph colouring: {target: span} -> {target: lane index}."""
    lanes = {}
    ends = []                       # ends[i] = last row lane i is busy
    for target, (lo, hi) in sorted(spans.items(), key=lambda kv: kv[1][0]):
        for i, end in enumerate(ends):
            if end < lo:
                lanes[target] = i
                ends[i] = hi
                break
        else:
            lanes[target] = len(ends)
            ends.append(hi)
    return lanes


def plan_lanes(blocks, holder_order, rounds=6, **kw):
    """Iterate placement <-> lane colouring until the assignment stops moving."""
    lanes = None
    for _ in range(rounds):
        cols = Columns(blocks, holder_order, lanes=lanes, **kw)
        g = lay.Layout(lm.Program())
        placer = CodePlacer(g, cols, 1, edge_heat=SIM.edge_heat())
        placer.place(blocks)
        spans = {}
        for _dest, row, target in placer.joins:
            lo, hi = spans.get(target, (row, row))
            spans[target] = (min(lo, row), max(hi, row))
        for target, row in placer.entry_row.items():
            if target in spans:
                lo, hi = spans[target]
                spans[target] = (min(lo, row), max(hi, row))
        new = colour_lanes(spans)
        if new == lanes:
            break
        lanes = new
    # verify: two targets on one lane must not overlap
    by_lane = {}
    for t, i in lanes.items():
        by_lane.setdefault(i, []).append(spans[t])
    for i, iv in by_lane.items():
        iv.sort()
        for a, b in zip(iv, iv[1:]):
            assert a[1] < b[0], ("overlapping highway lane", i, a, b)
    return lanes


def checked_room(g, x, y, w, h, glyphs="+-|"):
    cor, hor, ver = glyphs
    for cx, cy in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
        g.put(cx, cy, cor)
    for i in range(1, w - 1):
        g.put(x + i, y, hor)
        g.put(x + i, y + h - 1, hor)
    for j in range(1, h - 1):
        g.put(x, y + j, ver)
        g.put(x + w - 1, y + j, ver)
    rect = lm.Rect(x, y, x + w - 1, y + h - 1, x + 1, y + 1, x + w - 2, y + h - 2)
    g.p.rooms.append(rect)
    return rect


# ===========================================================================
# 4.  whole program
# ===========================================================================
def build(holder_order=None, pitch=HOLDER_PITCH, ring_lift=RING_LIFT,
          port_gap=PORT_GAP, lead_in=LEAD_IN, code_slack=CODE_SLACK,
          tiers=BAND_TIERS, port_order=PORT_ORDER, block_order=None,
          flip=None):
    flow = F.build_flow()
    blocks = split_blocks(flow, block_order)
    holder_order = holder_order or [h for h in HOLDER_ORDER if h in F.HOLDERS]
    assert sorted(holder_order) == sorted(F.HOLDERS), "HOLDER_ORDER is stale"
    kw = dict(pitch=pitch, port_gap=port_gap, lead_in=lead_in,
              code_slack=code_slack, tiers=tiers, port_order=port_order,
              flip=HOLDER_FLIP if flip is None else flip, heat=SIM.block_heat())
    cols = Columns(blocks, holder_order,
                   lanes=plan_lanes(blocks, holder_order, **kw), **kw)

    p = lm.Program()
    g = lay.Layout(p)

    # controller room: top wall row 0, interior from row 1
    ctrl_top = 0
    placer = CodePlacer(g, cols, ctrl_top + 1, edge_heat=SIM.edge_heat())
    placer.place(blocks)
    code_bottom = placer.y + TAIL_PAD

    # highway turn glyphs: 'v' above the target row, '^' below it
    for dest, row, target in placer.joins:
        trow = placer.entry_row[target]
        g.put(dest, row, ARROW_S if trow > row else ARROW_N)
        g.put(dest, trow, ARROW_E)

    ctrl_bot = code_bottom
    # draw the controller walls THROUGH the collision-checked Layout: the raw
    # Program.room is a bare dict store and would silently overwrite code.
    ctrl = checked_room(g, 0, ctrl_top, cols.width, ctrl_bot - ctrl_top + 1)

    # ---- device band above the controller ------------------------------
    # Tier 0 sits nearest the controller; tier t is HOLDER_H + TIER_GAP rows
    # higher.  band_bot/band_top are the OUTER extent, which is what the input
    # room, the ring relay and the display are positioned against.
    def tier_bot(t):
        return ctrl_top - PIPE_GAP - 1 - t * (HOLDER_H + TIER_GAP)

    band_bot = tier_bot(0)                      # bottom wall row of tier 0
    band_top = tier_bot(tiers - 1) - (HOLDER_H - 1)
    pipes = {"in": [], "out": []}

    def drop_pipe(col, room_bottom_row):
        """device -> controller (a value falls into the controller)."""
        path = [(col, room_bottom_row + 1)]
        while path[-1][1] < ctrl_top - 1:
            path.append((col, path[-1][1] + 1))
        lay.place_pipe(g, path, (0, 1))
        pipes["in"].append((col, ctrl_top - 1))

    def lift_pipe(col, room_bottom_row):
        """controller -> device."""
        path = [(col, ctrl_top - 1)]
        while path[-1][1] > room_bottom_row + 1:
            path.append((col, path[-1][1] - 1))
        lay.place_pipe(g, path, (0, -1))
        pipes["out"].append((col, ctrl_top - 1))

    for name in holder_order:
        rx = cols.holder_room_x[name]
        rbot = tier_bot(cols.holder_tier[name])
        rtop = rbot - (HOLDER_H - 1)
        p.room(rx, rtop, HOLDER_W, HOLDER_H)
        ix, iy = rx + 1, rtop + 1                    # interior 2 x (H-2)
        # 6-cell ring: s first, then r, with '@' parked outside it
        # 6-cell ring  s -> '<' -> 'v' -> r -> '>' -> '^' -> s.  Every turn is a
        # real glyph and '@' sits OUTSIDE the cycle, on a ramp that joins it at
        # the '^': an '@' inside a ring is a no-op and walks the man into a wall.
        g.put(ix, iy + 3, "@")
        g.put(ix + 1, iy + 3, ARROW_N)               # entry ramp
        g.put(ix + 1, iy + 2, ARROW_N)
        g.put(ix + 1, iy + 1, "s")
        g.put(ix + 1, iy, ARROW_W)
        g.put(ix, iy, ARROW_S)
        g.put(ix, iy + 1, "r")
        g.put(ix, iy + 2, ARROW_E)
        drop_pipe(cols.hr[name], rbot)
        lift_pipe(cols.hw[name], rbot)

    # ---- debug output room (only wired when lllm_flow.DEBUG_EMIT is set) --
    if F.DEBUG_EMIT:
        ot_col = cols.port["ot"]
        ot_bot = band_top - 5
        p.output_room(ot_col - 1, ot_bot - 2)
        lift_pipe(ot_col, ot_bot)

    # ---- input room: above the band, clear of every other pipe ---------
    in_col = cols.port["in"]
    in_bot = band_top - 2
    p.input_room(in_col - 1, in_bot - 2)
    drop_pipe(in_col, in_bot)

    # ---- ring relay: long pipes so all 32 words fit in flight ------------
    relay_bot = band_top - ring_lift
    relay_x = 1
    p.room(relay_x, relay_bot - (HOLDER_H - 1), HOLDER_W, HOLDER_H)
    rix, riy = relay_x + 1, relay_bot - (HOLDER_H - 1) + 1
    g.put(rix, riy + 3, "@")
    g.put(rix + 1, riy + 3, ARROW_N)
    g.put(rix + 1, riy + 2, ARROW_N)
    g.put(rix + 1, riy + 1, "r")                 # the relay takes first, then sends
    g.put(rix + 1, riy, ARROW_W)
    g.put(rix, riy, ARROW_S)
    g.put(rix, riy + 1, "s")
    g.put(rix, riy + 2, ARROW_E)

    def run(path, x=None, y=None):
        cx, cy = path[-1]
        if x is not None:
            step = 1 if x > cx else -1
            for xx in range(cx + step, x + step, step):
                path.append((xx, cy))
        if y is not None:
            cx, cy = path[-1]
            step = 1 if y > cy else -1
            for yy in range(cy + step, y + step, step):
                path.append((cx, yy))
        return path

    # controller -> relay, entering the relay's bottom wall
    c2r = cols.port["rs"]
    path = run(run([(c2r, ctrl_top - 1)], y=relay_bot + 2), x=rix)
    path = run(path, y=relay_bot + 1)
    lay.place_pipe(g, path, (0, -1))
    pipes["out"].append((c2r, ctrl_top - 1))
    ring_out_len = len(path)

    # relay -> controller, leaving the relay's right wall
    r2c = cols.port["rr"]
    path = run(run([(relay_x + HOLDER_W, relay_bot - 2)], x=r2c), y=ctrl_top - 1)
    lay.place_pipe(g, path, (0, 1))
    pipes["in"].append((r2c, ctrl_top - 1))
    # the ring must physically hold all 32 program words while the controller
    # is off doing something else, or `rs` deadlocks against a full pipe
    ring_cap = ring_out_len + len(path) + 1
    assert ring_cap >= F.RING_SLOTS + 1, ("ring too small", ring_cap)

    # ---- display --------------------------------------------------------
    disp_x = cols.code_hi + DISP_GAP
    disp_y = band_bot - 17
    p.display(disp_x, disp_y, 18, 18)

    # The display consumes ADDR, DATA and SWAP in that order within one tick, so
    # a value must never overtake the one it belongs behind: keep
    # len(ADDR) <= len(DATA) <= len(SWAP).  The column order ds < da < dd and the
    # turn rows below are the unique arrangement that gets both that AND a
    # crossing-free routing -- ADDR turns above DATA so DATA's descent to the
    # left wall never meets ADDR's eastward run.
    lens = {}

    # SWAP -> bottom wall, all the way round the east side of the display
    path = run(run([(cols.port["ds"], ctrl_top - 1)], y=disp_y - 6), x=disp_x + 20)
    path = run(run(path, y=ctrl_top - 2), x=disp_x + 2)
    path = run(path, y=ctrl_top - 3)
    lay.place_pipe(g, path, (0, -1))
    pipes["out"].append((cols.port["ds"], ctrl_top - 1))
    lens["ds"] = len(path)

    # ADDR -> top wall
    path = run(run([(cols.port["da"], ctrl_top - 1)], y=disp_y - 2), x=disp_x + 4)
    path = run(path, y=disp_y - 1)
    lay.place_pipe(g, path, (0, 1))
    pipes["out"].append((cols.port["da"], ctrl_top - 1))
    lens["da"] = len(path)

    # DATA -> left wall, entering low so the pipe stays longer than ADDR's
    path = run(run([(cols.port["dd"], ctrl_top - 1)], y=disp_y - 1), x=disp_x - 2)
    path = run(run(path, y=disp_y + 15), x=disp_x - 1)
    lay.place_pipe(g, path, (1, 0))
    pipes["out"].append((cols.port["dd"], ctrl_top - 1))
    lens["dd"] = len(path)

    assert lens["da"] <= lens["dd"] <= lens["ds"], lens

    break_stray_literals(g, placer.lits)
    return p, g, cols, blocks, pipes, ctrl


def render(p):
    return p.render()


# ===========================================================================
# 4b.  binding verifier -- the assert_bindings() this file's docstring promises
# ===========================================================================
def verify_bindings(path, cols, verbose=True):
    """Check every controller port op resolves to the device on ITS OWN column.

    The whole layout rests on "ports are columns": an `r` or `s` standing on a
    device's column is nearer that device's pipe than any other.  So far that
    was only an argument.  This checks it through tools/pipecheck.py, i.e.
    through the same loader the grader uses.  A rebound port does not crash --
    it quietly computes the wrong thing, and the public cases may well not
    notice -- so nothing that moves a pipe should ship without running this.

    Returns the number of bad ops (0 == good).
    """
    import pipecheck

    found, topo = pipecheck.bindings(path)
    rooms = topo.get("rooms") or []
    pipes = topo.get("pipes") or []
    # rendering shifts the grid (the device band lives at negative y), so the
    # controller is identified by being far and away the biggest room, not by
    # its build-time coordinates.
    def area(r):
        return ((r["max"][0] - r["min"][0] + 1) * (r["max"][1] - r["min"][1] + 1))

    ctrl = max(range(len(rooms)), key=lambda i: area(rooms[i]))
    dx = rooms[ctrl]["min"][0]           # controller's left wall == build column 0

    device = {}                     # (controller column, glyph) -> device name
    for name, col in cols.hr.items():
        device[(col + dx, "r")] = "holder %s in" % name
    for name, col in cols.hw.items():
        device[(col + dx, "s")] = "holder %s out" % name
    for name, col in cols.port.items():
        device[(col + dx, GLYPH[name])] = "port " + name

    seen, owner, bad = {}, {}, []
    for f in found:
        if f["room"] != ctrl:
            continue
        key = (f["cell"][0], f["op"])
        name = device.get(key)
        if name is None:
            bad.append((f, "no device owns column %d for '%s'" % key))
            continue
        if seen.setdefault(name, f["pipe"]) != f["pipe"]:
            bad.append((f, "%s binds pipe %s here but %s elsewhere"
                        % (name, f["pipe"], seen[name])))
        elif owner.setdefault(f["pipe"], name) != name:
            bad.append((f, "%s shares pipe %s with %s"
                        % (name, f["pipe"], owner[f["pipe"]])))
    if verbose:
        n = len([f for f in found if f["room"] == ctrl])
        print("verify_bindings: %d controller port ops, %d devices, "
              "%d distinct pipes, %d bad"
              % (n, len(seen), len(owner), len(bad)))
        for f, why in bad[:10]:
            print("   %s at %s -> pipe %s: %s" % (f["op"], f["cell"], f["pipe"], why))
    return len(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--verify", action="store_true",
                    help="run verify_bindings() on the result (needs node)")
    ap.add_argument("--pitch", type=int, default=HOLDER_PITCH)
    ap.add_argument("--ring-lift", type=int, default=RING_LIFT)
    args = ap.parse_args()
    p, g, cols, blocks, pipes, ctrl = build(pitch=args.pitch,
                                            ring_lift=args.ring_lift)
    w, h, box = p.footprint()
    out = args.out or os.path.join(HERE, "m1-%dx%d.man" % (w, h))
    p.save(out)
    print("blocks=%d  width=%d  code_hi=%d  footprint=%dx%d box=%d"
          % (len(blocks), cols.width, cols.code_hi, w, h, box))
    print("saved", out)
    if args.verify and verify_bindings(out, cols):
        raise SystemExit("BINDINGS ARE WRONG -- do not ship this grid")


if __name__ == "__main__":
    main()


# ===========================================================================
# 5.  holder column order search
# ===========================================================================
def measure_order(order):
    """(code rows, controller width) for a candidate holder column order.

    A port op must sit on its own column, so whenever the next one lies behind
    the cursor the ribbon has to wrap -- one extra ROW.  Height is what the box
    is squared on, so the column order is worth searching.
    """
    flow = F.build_flow()
    blocks = split_blocks(flow)
    cols = Columns(blocks, order, lanes=plan_lanes(blocks, order))
    g = lay.Layout(lm.Program())
    placer = CodePlacer(g, cols, 1)
    placer.place(blocks)
    return placer.y, cols.width


def search_holder_order(iters=400, seed=12345, verbose=True):
    import random
    rng = random.Random(seed)
    best = list(F.HOLDERS)
    bh, bw = measure_order(best)
    bscore = max(bh, bw)
    if verbose:
        print("start rows=%d width=%d" % (bh, bw))
    for _ in range(iters):
        cand = list(best)
        for _ in range(rng.choice((1, 1, 2))):
            i, j = rng.randrange(len(cand)), rng.randrange(len(cand))
            cand[i], cand[j] = cand[j], cand[i]
        h, w = measure_order(cand)
        if max(h, w) < bscore:
            best, bh, bw, bscore = cand, h, w, max(h, w)
            if verbose:
                print("  rows=%d width=%d" % (h, w))
    return best, bh, bw
