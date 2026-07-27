"""LLLM interpreter op-stream, v4 -- v2 plus DELTA FETCH.

v2 re-fetched `cells[mi]` by rotating the whole cells belt one full revolution
(N = W*H) per emulated tick: N iterations of a three-op loop whose rail
back-edge costs ~15 real ticks each, i.e. ~36% of the program's ticks.

v4 keeps the belt head where the last fetch left it and rotates only the
DIFFERENCE.  The trick that makes it fit a `do`-loop is that the loop body
`rc sc` leaves the last value read in A -- `sc` does not touch A -- so

    count = ((delta - 1) mod N) + 1 ;  BPLOOP { rc ; sc } ;  cw := A

both lands the head at `mi+1` again AND leaves `cells[mi]` in A, for every
delta including the +1 (walk east) case that would otherwise need a zero-trip
loop, which `b`/`m`/`d` cannot express.  Average count falls 256 -> ~128.

Original v2 notes follow.

v2 -- table-driven decode, register-only constants.

v1 (`lllm_build.py`) spent 94.4% of its emitted ops rotating a 30-slot state belt:
281 belt accesses per input character in `fill`, 323 per emulated tick, at ~45
emitted ops per access.  v2 attacks both factors.

  * TABLE DECODE.  ascii -> class is one nibble-table shift instead of nine `EQ`
    chains.  The perfect hash `idx = (asc*5)>>4 - 4` separates the eleven interior
    non-digit characters and folds all ten digits into three slots of their own
    (searched; no 16-slot hash exists, this one fits because `|` is positional and
    `@` shares SPACE's class).
  * CHEAP PRIMITIVES.  `eq(x,k) = 1/((k-x)^2+1)` by floored division needs no
    scratch slot, where v1's EQ needed three.  `x & 15` / `x >> 4` come from one
    `/` (quotient and remainder in A and B).  Sign comes from `>>63`.
  * REGISTER-ONLY CONSTANTS.  Every literal is built from single digits in A/B, so
    `K()` never touches the belt -- v1 paid two belt accesses just to *build* each
    of 43,45,60,62,77,88,94,118.  `B survives belt rotations`, which is what makes
    "park a constant in B, then load the operand" work.
  * STRUCTURAL FILL.  Border rows and columns are separate loops with a constant
    class and colour, so the four border comparisons vanish from the hot body.
  * DELTA RENDER.  SWAP=1 preserves the display's next buffer, so a round repaints
    two pixels instead of all 256, and the cells belt holds one packed word per
    cell instead of a triple (a fetch is one revolution, not three).

Packed cell word: `class | colour<<4 | (asc&15)<<8`, chosen so the two fields the
hot tick needs (`class`, digit value) are a single `/` apart.
"""

# ---------------------------------------------------------------- ring layout
# `da` (fill cursor) shares the round-counter slot: they are never both live.
# Slot -> ring-position assignment is free (the belt is symmetric under
# relabelling) and every access costs (pos(target)-head) mod n rotations, so this
# order is the output of `ringopt2.py`: 5,179 -> 4,589 emitted ops at identical
# semantics.
STATE = ['Wd', 'Nn', 't0', 'TCLS', 't3', 't2', 'md', 'mi', 'cw', 'mdp', 'hd',
         'AA', 't1', 'clrp', 'TCOL', 'TDIR', 'kc', 't5', 't4', 'BB']
DA = 'kc'            # fill display cursor reuses the k counter

C_SPACE, C_N, C_E, C_S, C_W = 0, 1, 2, 3, 4
C_X, C_M, C_PLUS, C_MINUS, C_H, C_WALL, C_DIGIT = 5, 6, 7, 8, 9, 10, 11
COLOR = [0, 3, 3, 3, 3, 3, 12, 10, 10, 3, 4, 8]

# two-stage perfect hash: idx = ((((asc*5)>>4)&31)*3>>2)&15  -- searched; a
# single-stage 16-slot hash does not exist for this character set.
H1M, H1S, H2M, H2S = 5, 4, 49, 5
CHARCLS = {32: C_SPACE, 64: C_SPACE, 94: C_N, 62: C_E, 118: C_S, 60: C_W,
           88: C_X, 77: C_M, 43: C_PLUS, 45: C_MINUS, 72: C_H}
# heading codes 0..3 = N,E,S,W
DCOL = [0, 1, 0, -1]
DROW = [-1, 0, 1, 0]


def _hash(asc):
    return ((((asc * H1M) >> H1S) * H2M) >> H2S) & 15


def build_tables():
    slots = {}
    for asc, cl in CHARCLS.items():
        h = _hash(asc)
        assert h not in slots, (asc, h)
        slots[h] = cl
    for asc in range(48, 58):
        h = _hash(asc)
        assert slots.get(h, C_DIGIT) == C_DIGIT, (asc, h)
        slots[h] = C_DIGIT
    assert 0 <= min(slots) and max(slots) < 16, sorted(slots)
    tcls = 0
    for h, cl in slots.items():
        tcls |= cl << (4 * h)
    tcol = 0
    for cl, c in enumerate(COLOR):
        tcol |= c << (4 * cl)
    # TDIR: nibble h = DCOL[h]+1, nibble h+8 = DROW[h]+1
    tdir = 0
    for h in range(4):
        tdir |= (DCOL[h] + 1) << (4 * h)
        tdir |= (DROW[h] + 1) << (4 * (h + 8))
    return tcls, tcol, tdir


def digits_for(k):
    out = []
    while k > 9:
        out.append(9)
        k -= 9
    out.append(k)
    return out


class Asm:
    WRITES_A = set(['+', '-', '*', '/', 'N', '&', '|', '~', '{', '}', 'W',
                    'r', 'rc', 'ri'])

    def __init__(self, ring=None):
        self.ring = list(ring if ring is not None else STATE)
        self.ops = []
        self.av = None

    # --- raw ---------------------------------------------------------------
    def e(self, *o):
        for x in o:
            self.ops.append(x)
            if isinstance(x, tuple) or x in self.WRITES_A:
                self.av = None
        return self

    def K(self, d):
        assert 0 <= d <= 9, d
        return self.e(('#', d))

    def bigK(self, k):
        """A := k (k >= 0), registers only, single digits only (octal chain).

        Only single-digit `('#', d)` may ever be emitted: the placer despines a
        multi-digit constant into `d M d *`, which clobbers B -- and the whole
        design relies on B surviving.
        """
        ch = []
        v = k
        while v:
            ch.append(v & 7)
            v >>= 3
        if not ch:
            ch = [0]
        ch.reverse()
        self.K(ch[0])
        for n in ch[1:]:
            self.e('M', ('#', 3), 'W', '{')
            if n:
                self.e('M', ('#', n), '+')
        self.av = None
        return self

    def negsub(self, k):
        """A := k - A."""
        ds = digits_for(k)
        self.e('M', ('#', ds[0]), '-')
        for d in ds[1:]:
            self.e('M', ('#', d), '+')
        self.av = None
        return self

    def addk(self, k):
        """A := A + k."""
        for d in digits_for(k):
            self.e('M', ('#', d), '+')
        self.av = None
        return self

    def subk(self, k):
        """A := A - k."""
        return self.negsub(k).e('N')

    def mulk(self, d):
        """A := A * d, d <= 9."""
        return self.e('M', ('#', d), '*')

    def shl(self, n):
        """A := A << n (n doublings, keeps B free of constants)."""
        for _ in range(n):
            self.e('M', '+')
        return self

    def Bset(self, k):
        """B := k (A := k too), registers only."""
        return self.bigK(k).e('M')

    def eqk(self, k):
        """A := (A == k)."""
        self.negsub(k)
        self.e('M', '*')
        self.e('M', ('#', 1), '+')
        self.e('M', ('#', 1), '/')
        return self

    # --- belt --------------------------------------------------------------
    def rot(self):
        self.ops.extend(('r', 's'))
        self.ring.append(self.ring.pop(0))
        self.av = None

    def tf(self, n):
        assert n in self.ring, n
        while self.ring[0] != n:
            self.rot()

    def LA(self, n):
        if self.av == n:
            return self
        self.tf(n)
        self.ops.extend(('r', 's'))
        self.ring.append(self.ring.pop(0))
        self.av = n
        return self

    def SA(self, n):
        self.ops.append('M')
        self.tf(n)
        self.ops.extend(('r', 'W', 's'))
        self.ring.append(self.ring.pop(0))
        self.av = n
        return self

    def rem(self, src, m):
        """A := src % m  (m a power of two, src >= 0)."""
        self.Bset(m); self.LA(src); return self.e('/', 'W')

    def quo(self, src, m):
        """A := src / m."""
        self.Bset(m); self.LA(src); return self.e('/')

    def tab(self, tslot, tmp):
        """A holds a shift; leaves A := (tslot >> shift) & 15, via `tmp`.

        Two different constants (the shift, then the mask) cannot both sit in B,
        so the shifted word makes one trip through the belt.  3 accesses.
        """
        self.e('M'); self.LA(tslot); self.e('}'); self.SA(tmp)
        return self.rem(tmp, 16)

    def sign(self, src, tmp):
        """A := sign(src)."""
        self.e(('#', 7), 'M', ('#', 9), '*', 'M')      # B := 63
        self.LA(src); self.e('}'); self.SA(tmp)
        self.e(('#', 7), 'M', ('#', 9), '*', 'M')
        self.LA(src); self.e('N', '}', 'M'); self.LA(tmp)
        return self.e('-')

    # --- control -----------------------------------------------------------
    def _sub(self):
        s = Asm.__new__(Asm)
        s.ring = self.ring
        s.ops = []
        s.av = None
        return s

    def BPLOOP(self, cnt_slot, bodyfn):
        self.LA(cnt_slot)
        self.BPLOOPA(bodyfn)

    def BPLOOPA(self, bodyfn):
        entry = self.ring[0]
        s = self._sub()
        bodyfn(s)
        s.tf(entry)
        self.ops.append(('BPLOOP', s.ops))
        self.av = None

    def LOOPX(self, bodyfn, testslot):
        succ = STATE[(STATE.index(testslot) + 1) % len(STATE)]
        self.tf(succ)
        entry = self.ring[0]
        s = self._sub()
        bodyfn(s)
        assert self.ring[0] == entry, ("LOOPX ring", self.ring[0], entry)
        self.ops.append(('LOOPX', s.ops))
        self.av = None

    def FOREVER(self, bodyfn):
        entry = self.ring[0]
        s = self._sub()
        bodyfn(s)
        s.tf(entry)
        self.ops.append(('FOREVER', s.ops))
        self.av = None


# ---------------------------------------------------------------- fill
WALLWORD = C_WALL | (4 << 4)          # class WALL, colour 4, digit field 0


def emit_border_cell(a):
    a.e('ri')
    a.bigK(WALLWORD); a.e('sc')
    a.LA(DA); a.e('cmd'); a.addk(1); a.SA(DA)
    a.K(4); a.e('cmd')
    a.av = None


def emit_hash_shift(a, src):
    """A := 4 * hash(src ascii); uses t2 as scratch."""
    a.LA(src); a.mulk(5)
    a.e('M', ('#', 4), 'W', '}')          # (asc*5) >> 4
    a.mulk(7); a.mulk(7)                  # * 49
    a.e('M', ('#', 5), 'W', '}')          # >> 5
    a.SA('t2'); a.rem('t2', 16)           # & 15
    a.mulk(4)


def emit_interior_cell(a):
    a.e('ri'); a.SA('t0')                            # t0 = ascii
    a.rem('t0', 16); a.shl(8); a.SA('t1')            # word bits 8.. = digit
    emit_hash_shift(a, 't0')
    a.tab('TCLS', 't3'); a.SA('t2')                  # t2 = class
    a.mulk(4); a.tab('TCOL', 't3'); a.SA('t4')       # t4 = colour
    a.shl(4)
    a.e('M'); a.LA('t1'); a.e('+', 'M'); a.LA('t2'); a.e('+')
    a.SA('t1'); a.e('sc')                            # packed cell word
    a.LA(DA); a.e('cmd'); a.addk(1); a.SA(DA)        # ADDR
    a.LA('t4'); a.e('cmd')                           # DATA
    a.LA('t0'); a.eqk(64)                            # man discovery
    a.e('M'); a.LA('t5'); a.e('-'); a.SA('t5')       # nf -= (asc=='@')
    a.e('M'); a.LA('mi'); a.e('+'); a.SA('mi')       # mi += nf
    a.av = None


def emit_fill(a):
    def row_end(b):
        b.LA('Wd'); b.negsub(16); b.e('M'); b.LA(DA); b.e('+'); b.SA(DA)

    def border_row(b):
        b.BPLOOP('Wd', emit_border_cell)
        row_end(b)

    def mid_row(b):
        emit_border_cell(b)
        b.LA('Wd'); b.subk(2)
        b.BPLOOPA(emit_interior_cell)                # inner loop owns BP
        emit_border_cell(b)
        row_end(b)
        b.LA('md'); b.subk(1); b.SA('md'); b.LA('md')

    # the row loop must be an X back-edge, not BP: BP is a single register and the
    # interior loop inside the body would destroy an outer BP counter.
    border_row(a)
    a.LA('Wd'); a.e('M'); a.LA('Nn'); a.e('/')       # A = N / W = H
    a.subk(2); a.SA('md')                            # md doubles as the row count
    a.LOOPX(mid_row, 'md')
    border_row(a)


def emit_manpos(a):
    """mi currently counts interior cells before '@'; turn it into mi and md."""
    a.LA('Wd'); a.subk(2); a.SA('t0')                # t0 = W-2
    a.e('M'); a.LA('mi'); a.e('/')                   # A = irow, B = icol
    a.SA('t1')
    a.e('M'); a.LA('t0'); a.e('*', 'M'); a.LA('mi'); a.e('-')
    a.SA('t2')                                       # t2 = icol
    a.LA('t1'); a.addk(1); a.e('M'); a.LA('Wd'); a.e('*', 'M')
    a.LA('t2'); a.e('+'); a.addk(1); a.SA('mi')      # mi = (irow+1)*W + icol+1
    a.LA('t1'); a.addk(1); a.shl(4)
    a.e('M'); a.LA('t2'); a.e('+'); a.addk(2); a.SA('md')   # md = 16*row+col+1
    a.LA('md'); a.SA('mdp')
    a.K(0); a.SA('clrp')
    a.K(1); a.SA('hd')                               # start facing east
    a.K(0); a.SA('AA')
    a.K(0); a.SA('BB')


def emit_fetch(a):
    """cw := cells[mi], rotating the cells belt by the MOVE DELTA only.

    Invariant: the belt head is at `mi_prev + 1`.  Running the loop
    `((delta-1) mod N) + 1` times reads indices `head .. mi`, so the last `rc`
    leaves `cells[mi]` in A and the head lands on `mi + 1` again.
    """
    a.LA('t0'); a.subk(1); a.SA('t1')                # t1 = delta - 1
    a.LA('Nn'); a.e('M'); a.LA('t1'); a.e('/', 'W')  # A = (delta-1) mod N
    a.addk(1)
    a.BPLOOPA(lambda b: b.e('rc', 'sc'))
    a.SA('cw')                                       # A already holds cells[mi]
    a.av = None


def emit_step(a):
    """one emulated tick; cw holds the packed word of the cell under the man."""
    a.rem('cw', 16); a.SA('t1')                      # t1 = class
    # ---- A / B ----
    a.eqk(C_PLUS); a.SA('t2')                        # isP
    a.LA('t1'); a.eqk(C_MINUS)
    a.e('M'); a.LA('t2'); a.e('-'); a.SA('t2')       # t2 = isP - isS
    a.e('M'); a.LA('BB'); a.e('*'); a.SA('t2')       # t2 = pm * B
    a.LA('t1'); a.eqk(C_DIGIT); a.SA('t3')           # isd
    a.quo('cw', 256)                                 # digit value
    a.e('M'); a.LA('AA'); a.e('-', 'N')              # dv - A
    a.e('M'); a.LA('t3'); a.e('*')
    a.e('M'); a.LA('t2'); a.e('+', 'M'); a.LA('AA'); a.e('+')
    a.SA('t2')                                       # t2 = new A
    a.LA('t1'); a.eqk(C_M); a.SA('t3')               # isM
    a.LA('AA'); a.e('M'); a.LA('BB'); a.e('-', 'N')  # A - B
    a.e('M'); a.LA('t3'); a.e('*', 'M'); a.LA('BB'); a.e('+')
    a.SA('BB')
    a.LA('t2'); a.SA('AA')
    # ---- heading: hd = (hd + isarrow*(cl-1-hd) + isX*sign(A)) & 3 ----
    a.LA('t1'); a.subk(1); a.SA('t2')                # t2 = cl-1
    a.e('M', ('#', 4), 'W', '/')                     # (cl-1)/4
    a.eqk(0); a.SA('t3')                             # isarrow
    a.LA('t1'); a.eqk(C_X); a.SA('t4')               # isX
    a.sign('AA', 't5'); a.e('M'); a.LA('t4'); a.e('*'); a.SA('t4')
    a.LA('t2'); a.e('M'); a.LA('hd'); a.e('-', 'N')  # (cl-1) - hd
    a.e('M'); a.LA('t3'); a.e('*', 'M'); a.LA('hd'); a.e('+')
    a.e('M'); a.LA('t4'); a.e('+'); a.SA('t2')
    a.rem('t2', 4); a.SA('hd')
    # ---- move ----
    a.LA('t1'); a.eqk(C_H); a.SA('t2')
    a.LA('t1'); a.eqk(C_WALL); a.e('M'); a.LA('t2'); a.e('+')
    a.negsub(1); a.SA('t2')                          # go = 1 - stay
    a.LA('hd'); a.mulk(4); a.tab('TDIR', 't5'); a.subk(1); a.SA('t3')  # dcol
    a.LA('hd'); a.addk(8); a.mulk(4); a.tab('TDIR', 't5'); a.subk(1)
    a.SA('t4')                                       # drow
    a.e('M'); a.LA('Wd'); a.e('*', 'M'); a.LA('t3'); a.e('+')
    a.e('M'); a.LA('t2'); a.e('*')
    a.SA('t0')                                       # t0 = the move delta
    a.e('M'); a.LA('mi'); a.e('+'); a.SA('mi')
    a.LA('t4'); a.shl(4)
    a.e('M'); a.LA('t3'); a.e('+')
    a.e('M'); a.LA('t2'); a.e('*', 'M'); a.LA('md'); a.e('+'); a.SA('md')
    a.av = None


def emit_render(a):
    """two-pixel delta repaint + commit; `cw` must hold the cell under the man.

    No fetch here: `emit_step` leaves `cw` pointing at the cell the man landed on,
    and the initial '@' cell packs to exactly 0, so the interpreter never needs a
    second static copy of the fetch (which cost six pipe excursions of grid rows).
    """
    a.quo('cw', 16); a.SA('t1'); a.rem('t1', 16); a.SA('t1')   # colour
    a.LA('mdp'); a.e('cmd'); a.LA('clrp'); a.e('cmd')
    a.LA('md'); a.e('cmd'); a.K(9); a.e('cmd')
    a.K(1); a.e('N', 'cmd')                          # commit (SWAP preserve)
    a.LA('md'); a.SA('mdp')
    a.LA('t1'); a.SA('clrp')
    a.av = None


def build():
    tcls, tcol, tdir = build_tables()
    a = Asm()
    for _ in STATE:
        a.e(('#', 0), 's')
    a.e('ri'); a.SA('Wd')
    a.e('ri'); a.e('M'); a.LA('Wd'); a.e('*'); a.SA('Nn')
    a.bigK(tcls); a.SA('TCLS')
    a.bigK(tcol); a.SA('TCOL')
    a.bigK(tdir); a.SA('TDIR')
    a.K(1); a.SA(DA)
    a.K(0); a.SA('mi')
    a.K(1); a.SA('t5')                               # nf = 1
    emit_fill(a)
    emit_manpos(a)
    # prime the delta-fetch invariant: rotate to head = mi+1.  The last value
    # read is cells[mi], the '@' cell, which packs to exactly 0 -- so this also
    # replaces v2's `K(0); SA('cw')`.
    a.LA('mi'); a.addk(1)
    a.BPLOOPA(lambda b: b.e('rc', 'sc'))
    a.SA('cw')
    emit_render(a)

    def round_body(b):
        b.e('ri'); b.SA('kc')

        def kbody(c):
            emit_step(c)
            emit_fetch(c)
            c.LA('kc'); c.subk(1); c.SA('kc')
            c.LA('kc')
        b.LOOPX(kbody, 'kc')
        emit_render(b)
    a.FOREVER(round_body)
    return a.ops


def flat(o):
    n = 0
    for x in o:
        if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
            n += flat(x[1])
        else:
            n += 1
    return n


if __name__ == '__main__':
    ops = build()
    print("ring", len(STATE), "flat ops", flat(ops))
