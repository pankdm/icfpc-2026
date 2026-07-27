#!/usr/bin/env python3
"""micro_asm.py -- the control-flow / register layer over micro_core.Emit.

  Konst   shortest token sequence that leaves an arbitrary integer in A, found by
          BFS over (A, B) with digits + M W N + - * { }.  NO BACKTICK LITERALS:
          the oracle pairs backticks per row AND per column, so two unrelated
          literals that line up vertically make the whole program a loaderror and
          the Rust engine does not reproduce it.  Everything except the two 15-digit
          classifier tables is built arithmetically.

  Ring    the STATE ring, a FIFO of named slots.  `r:S s:S` is a rotation that
          preserves order, so the head index is known AT EMIT TIME and a read of
          slot i costs (i - head) mod n rotations.  Every block starts and ends at
          head 0 (`home()`), which makes joins trivially safe.

  Scratch the SCRATCH ring, used as a named temp file: `push(name)` sends A,
          `pop(name)` rotates the wanted value to the front and receives it.  This
          is what makes 3-operand expressions possible at all -- `r`/`s` clobber A,
          and only B survives a ring rotation.

  Blocks  one highway COLUMN per block; a jump places 'v' (target below) or '^'
          (above) and the block's entry glyph turns the man off the highway.  The
          same column works from both directions, and `verify()` re-checks that
          every highway is clear over the span it is used.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


# ──────────────────────────────────────────────────────────────────────────
# constant synthesis
# ──────────────────────────────────────────────────────────────────────────
_KCACHE = {}


def _bfs(limit=200000, maxdepth=9):
    """states (a, b) -> shortest token list; b is None while B is unknown."""
    best = {}
    frontier = []
    for d in range(10):
        st = (d, None)
        if st not in best:
            best[st] = [str(d)]
            frontier.append(st)
    for _ in range(maxdepth):
        nxt = []
        for st in frontier:
            a, b = st
            toks = best[st]
            cands = []
            for d in range(10):
                cands.append(((d, b), str(d)))
            cands.append(((a, a), "M"))
            cands.append(((-a, b), "N"))
            if b is not None:
                cands.append(((b, a), "W"))
                cands.append(((a + b, b), "+"))
                cands.append(((a - b, b), "-"))
                cands.append(((a * b, b), "*"))
                if 0 <= b <= 63:
                    cands.append(((a << b, b), "{"))
                    cands.append(((a >> b, b), "}"))
            for (na, nb), t in cands:
                if abs(na) > limit or (nb is not None and abs(nb) > limit):
                    continue
                s2 = (na, nb)
                if s2 in best:
                    continue
                best[s2] = toks + [t]
                nxt.append(s2)
        frontier = nxt
    out = {}
    for (a, b), toks in best.items():
        if a not in out or len(toks) < len(out[a]):
            out[a] = toks
    return out


def konst_tokens(v):
    if not _KCACHE:
        _KCACHE.update(_bfs())
    if v in _KCACHE:
        return list(_KCACHE[v])
    raise KeyError("no token sequence for %d" % v)


# ──────────────────────────────────────────────────────────────────────────
class Rows:
    def __init__(self, y0, dead=()):
        self.y = y0
        self.dead = dead

    def take(self, n=1):
        while self.y in self.dead:
            self.y += 1
        y = self.y
        self.y += n
        return y


class Ring:
    """FIFO of named slots on one lane; head tracked at emit time."""

    def __init__(self, asm, lane, names):
        self.asm, self.lane = asm, lane
        self.names = list(names)
        self.head = 0
        self.pending = False

    @property
    def n(self):
        return len(self.names)

    def rot(self, k):
        assert not self.pending
        for _ in range(k):
            self.asm.E.seq(["r:%s" % self.lane, "s:%s" % self.lane])
        self.head = (self.head + k) % self.n

    def to(self, name):
        self.rot((self.names.index(name) - self.head) % self.n)

    def home(self):
        self.rot((-self.head) % self.n)

    def get(self, name):
        """A = slot; the slot is now OUT of the ring until put()."""
        self.to(name)
        self.asm.E.tok("r:%s" % self.lane)
        self.head = (self.head + 1) % self.n
        self.pending = True

    def put(self):
        assert self.pending
        self.asm.E.tok("s:%s" % self.lane)
        self.pending = False

    def push_raw(self, name=None):
        self.asm.E.tok("s:%s" % self.lane)

    def pop_raw(self):
        self.asm.E.tok("r:%s" % self.lane)


class Scratch:
    """Named temp store on one lane.  pop() rotates the wanted name to the front."""

    def __init__(self, asm, lane, cap):
        self.asm, self.lane, self.cap = asm, lane, cap
        self.q = []
        self.peak = 0

    def push(self, name):
        self.asm.E.tok("s:%s" % self.lane)
        self.q.append(name)
        self.peak = max(self.peak, len(self.q))
        assert len(self.q) < self.cap, "scratch overflow (%d >= %d): %r" % (
            len(self.q), self.cap, self.q)

    def _rotate_to(self, name):
        assert name in self.q, "%r not in scratch %r" % (name, self.q)
        while self.q[0] != name:
            self.asm.E.seq(["r:%s" % self.lane, "s:%s" % self.lane])
            self.q.append(self.q.pop(0))

    def pop(self, name):
        self._rotate_to(name)
        self.asm.E.tok("r:%s" % self.lane)
        self.q.pop(0)

    def drop(self, name):
        self.pop(name)

    def normalize(self, order):
        """Leave the queue holding exactly `order` (front first)."""
        assert sorted(order) == sorted(self.q), "%r vs %r" % (order, self.q)
        for name in order:
            self._rotate_to(name)
            self.asm.E.seq(["r:%s" % self.lane, "s:%s" % self.lane])
            self.q.append(self.q.pop(0))
        assert self.q == list(order)


# ──────────────────────────────────────────────────────────────────────────
class Asm:
    def __init__(self, L, E, g, hw_cols):
        self.L, self.E, self.g = L, E, g
        self.R = Rows(g["IYLO"], E.dead)
        self.hw_free = list(hw_cols)
        self.hw_of = {}
        self.blocks = {}                 # name -> (col, row)
        self.jumps = []                  # (col, y_src, name)
        self.S = None
        self.T = None
        self.snap = {}                   # block -> (scratch queue, ring head)
        self.nocheck = {"HALTBLK"}       # dead ends: state is irrelevant

    # -- constants ---------------------------------------------------------
    def konst(self, v):
        self.E.seq(konst_tokens(v))

    def op(self, *toks):
        for t in toks:
            self.E.seq(t.split() if " " in t else [t])

    # -- highways ----------------------------------------------------------
    def _state(self):
        return (tuple(self.T.q), self.S.head, tuple(self.S.names))

    def align(self, name):
        """Rotate the rings into the state `name` was first entered with.

        Called from jump() BEFORE the man leaves the row, which is the only
        moment ops can still be emitted.  This is what lets every block keep
        whatever ring head it happens to end with instead of paying a `home()`
        (measured: 35 home() calls, ~350 pipe cells and ~40 of the 193 wraps).
        Branch arms cannot emit, so a block entered from an arm AND a jump has
        its state fixed by whichever came first -- the jump then aligns to it.
        """
        if name in self.nocheck or name not in self.snap:
            return
        q, head, names = self.snap[name]
        if tuple(self.S.names) != names:
            return
        if self.S.head != head:
            self.S.rot((head - self.S.head) % self.S.n)
        if tuple(self.T.q) != q:
            assert sorted(q) == sorted(self.T.q), (
                "scratch contents differ entering %s: %r vs %r"
                % (name, self.T.q, list(q)))
            for _ in range(len(self.T.q)):
                if tuple(self.T.q) == q:
                    break
                self.T.asm.E.seq(["r:%s" % self.T.lane, "s:%s" % self.T.lane])
                self.T.q.append(self.T.q.pop(0))

    def capture(self, name):
        """Record (or check) the symbolic ring/scratch state entering `name`.

        Blocks are EMITTED in source order but ENTERED along control-flow edges,
        so the emit-time model has to be saved per edge or a branch arm inherits
        the state its sibling left behind."""
        if name in self.nocheck:
            return
        st = self._state()
        if name in self.snap:
            assert self.snap[name] == st, (
                "state mismatch entering %s:\n  have %r\n  want %r"
                % (name, st, self.snap[name]))
        else:
            self.snap[name] = st

    def restore(self, name):
        if name in self.nocheck:
            return
        if name not in self.snap:
            self.snap[name] = self._state()
            return
        q, head, names = self.snap[name]
        assert tuple(self.S.names) == names, "ring schema mismatch at %s" % name
        self.T.q = list(q)
        self.S.head = head
        self.S.pending = False

    def hw(self, name):
        if name not in self.hw_of:
            assert self.hw_free, "out of highway columns"
            self.hw_of[name] = self.hw_free.pop(0)
        return self.hw_of[name]

    def _blank(self, x, y):
        return self.E.blank(x, y)

    def glide(self, col):
        E = self.E
        assert E.d in ("E", "W")
        while E.x != col:
            assert self._blank(E.x, E.y), "glide hits %r at %s" % (
                self.L.get(E.x, E.y), (E.x, E.y))
            E._step()

    def face(self, col, d="E"):
        E = self.E
        for _ in range(10):
            if d == "E" and E.d == "E" and E.x <= col:
                return
            if d == "W" and E.d == "W" and E.x >= col:
                return
            if E.d == "E":
                while E.x < E.xhi and E.x < col + 1 and self._blank(E.x, E.y):
                    E._step()
            else:
                while E.x > E.xlo and E.x > col - 1 and self._blank(E.x, E.y):
                    E._step()
            E.wrap()
        raise RuntimeError("cannot face column %d heading %s" % (col, d))

    def jump(self, name):
        """Leave the current row for block `name` via its highway column."""
        self.align(name)
        col = self.hw(name)
        E = self.E
        d = "E" if col >= E.x else "W"
        if (E.d == "E") != (d == "E"):
            self.face(col, d)
        else:
            self.face(col, E.d)
        self.glide(col)
        known = self.blocks.get(name)
        ch = "^" if (known is not None and known[1] < E.y) else "v"
        self.L.put(col, E.y, ch)
        self.jumps.append((col, E.y, name))
        self.capture(name)
        E.d = None

    def arm(self, x, y, d, name):
        """A branch outcome lands on (x,y) heading d; route it to block `name`.

        Heading N/S the man may be turned either way on the spot.  Heading E/W a
        target BEHIND him cannot be reached without walking back over the branch
        glyph, so he drops one row onto a fresh line first (the trampoline)."""
        col = self.hw(name)

        def drop(cx, cy):
            known = self.blocks.get(name)
            ch = "^" if (known is not None and known[1] < cy) else "v"
            self.L.put(cx, cy, ch)
            self.jumps.append((col, cy, name))
            self.capture(name)
            self.E.d = None

        if d in ("N", "S"):
            if col == x:
                drop(x, y)
                return
            st = 1 if col > x else -1
            self.L.put(x, y, ">" if st > 0 else "<")
            for xx in range(x + st, col, st):
                assert self._blank(xx, y), "arm blocked at %s" % ((xx, y),)
            drop(col, y)
            return
        st = 1 if d == "E" else -1
        if (col - x) * st >= 0:
            for xx in range(x, col, st):
                assert self._blank(xx, y), "arm blocked at %s" % ((xx, y),)
            drop(col, y)
            return
        fx = x
        while not (self.E._ok(fx) and self._blank(fx, y)):
            fx += st
            assert self.E.xlo <= fx <= self.E.xhi, "no trampoline column"
        yn = self.R.take()
        self.L.put(fx, y, "v")
        for yy in range(y + 1, yn):
            assert self._blank(fx, yy), "trampoline blocked at %s" % ((fx, yy),)
        st2 = 1 if col > fx else -1
        self.L.put(fx, yn, ">" if st2 > 0 else "<")
        for xx in range(fx + st2, col, st2):
            assert self._blank(xx, yn), "trampoline arm blocked at %s" % ((xx, yn),)
        drop(col, yn)

    def block(self, name, y=None):
        col = self.hw(name)
        y = self.R.take() if y is None else y
        assert name not in self.blocks, "duplicate block %r" % name
        self.blocks[name] = (col, y)
        self.restore(name)
        mid = (self.E.xlo + self.E.xhi) // 2
        if col <= mid:
            self.L.put(col, y, ">")
            self.E.at(col + 1, y, "E")
        else:
            self.L.put(col, y, "<")
            self.E.at(col - 1, y, "W")
        return y

    def endblock(self):
        self.R.y = max(self.R.y, self.E.y + 1)

    # -- branches ----------------------------------------------------------
    def branch(self, ch, up=None, down=None, straight=None):
        """Drop onto a fresh 3-row group, place `ch`, route the three outcomes.

        up/down/straight are block names (or None where the outcome is impossible).
        `ch` = 'X' (sign of A), 'x' (low bit of BP), 'd'/'a' (BP > 0).
        For 'X': up = A<0 (CCW), down = A>0 (CW), straight = A==0.
        """
        E = self.E
        # A branch ARM cannot emit anything, so the state its three targets are
        # entered with has to be pinned HERE, where ops are still legal.  Head 0
        # is the pin; every jump into those blocks then align()s to it.
        self.S.rot((-self.S.head) % self.S.n)
        self.endblock()
        ytop = max(self.R.y, E.y + 1)
        ymid, ybot = ytop + 1, ytop + 2
        self.R.y = ybot + 1
        # pick a drop column free on rows E.y .. ybot
        for _ in range(12):
            step = 1 if E.d == "E" else -1
            dc = E.x
            while E.xlo <= dc <= E.xhi:
                if (E._ok(dc) and E._ok(dc + step)
                        and all(self._blank(dc, y) for y in range(E.y, ybot + 1))
                        and all(self._blank(dc + step, y)
                                for y in (ytop, ymid, ybot))):
                    break
                dc += step
            else:
                # ran off the end of the row: take a fresh one and try again
                E.wrap()
                ytop = max(self.R.y, E.y + 1)
                ymid, ybot = ytop + 1, ytop + 2
                self.R.y = ybot + 1
                continue
            break
        else:
            raise RuntimeError("no drop column for a branch")
        step = 1 if E.d == "E" else -1
        self.glide(dc)
        self.L.put(dc, E.y, "v")
        self.L.put(dc, ymid, ">" if step > 0 else "<")
        bx = dc + step
        self.L.put(bx, ymid, ch)
        # `X` turns CLOCKWISE on A>0: heading E that is SOUTH, heading W it is
        # NORTH.  Getting this backwards silently swaps two branch arms.
        ccw_row, cw_row = (ytop, ybot) if step > 0 else (ybot, ytop)
        if up is not None:
            self.arm(bx, ccw_row, "N" if ccw_row == ytop else "S", up)
        if down is not None:
            self.arm(bx, cw_row, "N" if cw_row == ytop else "S", down)
        if straight is not None:
            self.arm(bx + step, ymid, "E" if step > 0 else "W", straight)
        self.R.y = max(self.R.y, ybot + 1)

    # -- inline counted loop ------------------------------------------------
    def tight(self, ops):
        """`while BP > 0 { BP--; ops }` in THREE rows, entered and left inline.

        Measured 2026-07-26: the block-structured `loop()` below costs ~190
        WALKED CELLS per iteration (block entry row, the body's own row, the
        jump's glide back to a highway column, the loop head's row and its two
        arms).  A LLLM tick rotates the 32-slot PROG ring twice, so those 190
        cells were the entire STEP tick budget.  This gadget costs len(ops)+8.

        Two mirrored shapes; which one is legal is decided by the LANES, not by
        where the man happens to be, because the body row is walked in ONE
        direction and every pipe op must land inside its own window:

          body runs EAST (lane indices ascending)     body runs WEST
             <  .  .  .  .  a                            >  .  .  .  .  d
                            m                            m
             ^ o2 o1 o0  >                               <  o0 o1 o2  ^

        The entry glyph is `a` for the east shape (heading WEST, CCW is south)
        and `d` for the west shape (heading EAST, CW is south).  On BP == 0 the
        man simply walks through it and carries on along the same row, so the
        loop needs no jump, no highway column and no block.
        """
        E = self.E
        n = len(ops)
        wide = n + 2

        def cols_for(c0, east):
            if east:
                return [c0 + 1 + i for i in range(n)], c0, c0 + n + 1
            return [c0 + n - i for i in range(n)], c0 + n + 1, c0

        def lanes_ok(cols):
            for t, x in zip(ops, cols):
                if ":" in t and not t.startswith("#"):
                    lo, hi = self.E.win[tuple(t.split(":"))]
                    if not (lo <= x <= hi):
                        return False
            return True

        for _ in range(14):
            y = E.y
            if y + 2 > E.g["IYHI"]:
                raise RuntimeError("no room below row %d for a tight loop" % y)
            east = E.d == "W"
            step = -1 if east else 1
            c0 = E.x - (wide - 1) if east else E.x
            while E.xlo <= c0 and c0 + wide - 1 <= E.xhi:
                span = range(c0, c0 + wide)
                if (all(E._ok(x) for x in span)
                        and all(self._blank(x, yy) for x in span
                                for yy in (y, y + 1, y + 2))):
                    body, entry, turn = cols_for(c0, east)
                    if lanes_ok(body):
                        self.glide(entry)
                        self.L.put(entry, y, "a" if east else "d")
                        self.L.put(entry, y + 1, "m")
                        self.L.put(entry, y + 2, ">" if east else "<")
                        for t, x in zip(ops, body):
                            if ":" in t and not t.startswith("#"):
                                o, lane = t.split(":")
                                E.ops.append((x, y + 2, o, lane))
                                self.L.put(x, y + 2, o)
                            else:
                                self.L.put(x, y + 2, t)
                        self.L.put(turn, y + 2, "^")
                        self.L.put(turn, y, "<" if east else ">")
                        for x in span:
                            E.res.add((x, y))   # the man GLIDES over these
                        E.dead.add(y + 1)
                        E.dead.add(y + 2)
                        for x in range(E.xlo, E.xhi + 1):
                            for yy in (y + 1, y + 2):
                                E.res.add((x, yy))
                        E.x = entry + (-1 if east else 1)
                        self.R.y = max(self.R.y, y + 3)
                        return
                c0 += step
            E.wrap()
        raise RuntimeError("cannot place a tight loop for %r" % (ops,))

    # -- counted loop ------------------------------------------------------
    def loop(self, name, body, exit_):
        """BP-counted loop head.  Enter with BP = n; `body` runs n times.

        The body block must end with `m` and a jump back to `name`.
        """
        y = self.block(name)
        E = self.E
        if E.d == "W":            # `d` turns CW: only heading EAST is that SOUTH
            E.wrap()
            y = E.y
            self.R.y = max(self.R.y, y + 1)
        step = 1
        c = E.x
        while not (E._ok(c) and self._blank(c, y) and self._blank(c, y + 1)):
            c += step
            assert E.xlo <= c <= E.xhi
        self.glide(c)
        self.L.put(c, y, "d")
        self.R.y = max(self.R.y, y + 2)
        self.arm(c, y + 1, "S", body)     # BP > 0 -> turn south into the body
        self.arm(c + step, y, "E" if step > 0 else "W", exit_)
        self.R.y = max(self.R.y, y + 2)

    # -- verification ------------------------------------------------------
    def verify(self):
        for (col, ysrc, name) in self.jumps:
            assert name in self.blocks, "jump to undefined block %r" % name
            hcol, ydst = self.blocks[name]
            assert hcol == col
            step = 1 if ydst > ysrc else -1
            want = "v" if step > 0 else "^"
            got = self.L.get(col, ysrc)
            assert got == want, "jump glyph at %s is %r, wanted %r (-> %s)" % (
                (col, ysrc), got, want, name)
            for y in range(ysrc + step, ydst, step):
                got = self.L.get(col, y)
                # another jump's arrowhead pointing the SAME way is harmless:
                # the traveller is already heading that way and glides through.
                assert got == " " or got == want, (
                    "highway %d blocked at row %d by %r (jump -> %s)"
                    % (col, y, got, name))
