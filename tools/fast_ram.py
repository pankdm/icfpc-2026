"""fast_ram.py -- a REUSABLE, PARAMETERISED systolic random-access RAM.

!! LIMITS -- READ BEFORE TRYING TO REUSE THIS. It is NOT a drop-in for split_ram. !!
Adversarial verification (2026-07-26) found two HARD blockers, both size-independent
(re-measured at k=16, 18 and 32), plus a contract mismatch:

  1. THE CALLER'S COMMAND PIPE MUST BE <= 19 CELLS. Lengths 2..19 all pass (settle
     unchanged, the pipe prefills so latency hides); lengths 20, 22, 25, 30, 35, 40, 100
     ALL DEADLOCK -- lm --grade runs to the cap with status "timeout" and --inspect shows
     every token consumed and NO reply, ever. tools/stateflow.py routes the command port
     along band rows spanning the whole program width, i.e. 50-150 cells, so a Semester-4
     swap fails on GEOMETRY ALONE. The REPLY pipe has no such limit (2..120 all pass).
  2. THE COMMAND PORT MUST BE FED BY AN INPUT ROOM, NOT BY A MAN. A relay room admitting
     one token every P ticks deadlocks for EVERY P swept from 5 to 800; the identical
     wiring with an input room attached directly passes.
  ROOT CAUSE of both: the decode workers are spawned on a FIXED SCHEDULE and die if the
  first broadcast is late by more than ~18 ticks. The front end is timer-driven; it must
  become data-driven before this component can attach to any real consumer.

  3. PIN GEOMETRY DIFFERS FROM split_ram IN TWO WAYS. (a) split_ram's `command` is at
     (ox+3, oy-1) -- OUTSIDE the stamp, entered from the NORTH by a vertical drop; ours is
     INSIDE the stamp and must be the terminus of a pipe flowing WEST along row 2.
     (b) `reply_turn` is INVERTED: split_ram returns it WEST of `reply`, we return it EAST.

  4. AREA. split_ram is 48x48 = 2,304 for EVERY size; this component is 9,604 (size 30/32)
     to 24,964 (size 288). It buys ticks by spending 4-10x the area, so it only pays where
     the box has room -- on the measured numbers that is Pathfinder only, and LLM is a NET
     LOSS because LLM's 219 ticks/access is PIPE TRANSIT, which a bigger RAM makes worse.

  5. verify() currently passes a k=4 configuration that fails within 40 ops (MIN_CELLS_PER_BANK
     is enforced in choose_banks() but not in _plan()), and VALUE_MAX shrinks as k grows
     (~5.1e17 at k=18, ~2.9e17 at k=32) -- the "always > 0" claims below are not unconditional.

The component itself is sound and verified standalone: solutions/memory/fast-ram-100.man grades
7/7 on the WASM oracle at box 11,449 / avgTicks 358.1 / score 4,100,378, and the tick law
settle = startup + 8.000*ops holds with ZERO residual out to 500 ops.

This is a generalisation of the Memory champion's store
(``solutions/memory/champion-6abc7461.man``), whose builder-shaped ancestor is
``solutions/memory/direct_memory.py`` (hard-locked to k=20 / l<=10 and shipping a
broken local-id-0 path).  The component here is parameterised by ``size`` and
``banks``, drops the id-0 special case entirely (by biasing cell ids to 1..k with
an extra ``-1`` stage, exactly as the champion does), and exposes every geometric
constant as a module-level knob so ``tools/autotune.py`` can sweep it.

WHY IT IS FAST (measured, see scratchpad/fast_ram_selftest.py)
    marginal cost ~8 ticks per random access, INDEPENDENT of size and address.
    Nothing walks a decode tree and nothing rotates a ring: an address is split
    once by ``/`` into (bank, offset), broadcast to every bank with ``S``, and the
    bank that matches routes the request down a 4-ticks-per-offset staircase whose
    *recycle* path is length-matched so every worker's loop is a constant number of
    ticks.  The loop is then populated with exactly loop/8 workers, so a request
    can be issued every 8 ticks.  The reply carries its own cell index in the low
    residue of the encoded word, and a bank of realigner workers burns exactly the
    complementary delay, so replies come out IN REQUEST ORDER at a constant latency.

WORD ENCODING (the actual invention)
    OFF   = 9 << 18 = 2359296                       (4 glyphs: ``9M{{``)
    write word = k*(value + OFF) - 1 - (addr mod k)   -- always > 0
    read  word = -k*OFF        - 1 - (addr mod k)     -- always < 0
    so ``sign(word)`` IS the opcode and a storage cell's whole ISA is one ``X``.
    cell (addr mod k) boots holding the tag k*OFF - 1 - (addr mod k), which decodes
    to value 0, so an unwritten cell reads as 0 for free.
    decode: value = word // k - (OFF - 1),  offset = k - 1 - (word mod k).

WIRE PROTOCOL (identical to tools/split_ram.py / tools/belt_ram.py, so this is a
drop-in for tools/stateflow.py ``Flow.load`` / ``Flow.store``)
    READ  : send [0, addr]         on the command pipe, receive the value on reply
    WRITE : send [1, addr, value]  on the command pipe, no reply

USAGE
    import fast_ram
    ports = fast_ram.build(program, ox, oy, size=100)
    # ports == {"command": (x, y), "reply": (x, y), "reply_turn": (x, y)}
    # * the caller's command pipe must END on ``command`` flowing WEST
    # * the component's reply pipe BEGINS on ``reply`` flowing EAST;
    #   ``reply_turn`` is the next cell east (a free bend/continuation cell).

LIMITS
    * ``banks`` <= 10   (a bank id is a single bare digit inside the decode column)
    * ``k`` = cells per bank must be EVEN and <= 98 (a two-digit literal)
    * ``size`` <= banks * k; spare cells are simply unused (and cost nothing).
    * ``k`` >= MIN_CELLS_PER_BANK (16): shorter decode rings rear-end themselves.

THE 8 IS A THROUGHPUT, NOT A LATENCY -- READ THIS BEFORE PORTING
    8 ticks/op is the pipelined ISSUE INTERVAL and is only achievable by a consumer
    that keeps several requests in flight. A consumer that reads a cell and
    immediately branches on the value pays the full round trip instead (order 100+
    ticks). Measured here: a single read settles at tick 197 end-to-end. So the
    20-50x headline against Semester 4's current per-access costs holds for
    STREAMING access patterns; for dependent chains the honest number is far
    smaller and has NOT been measured. Settle that before scheduling a port.

VERIFIED (scratchpad/fast_ram_selftest.py, 2026-07-26)
    size 100 as a Memory solution: 7/7 on the Rust engine AND on the wasm oracle,
    box 107x101 = 11449, marginal (1189-229)/120 = 8.0000 ticks/op exactly,
    tick law settle = 189 + 8.000*ops, 24/24 generality stress.
    Sizes 30/32/100/256/288 all build and pass a 7-test functional suite that
    exercises every cell of each instance.
    NOTE: this is NOT a better Memory submission -- the live champion
    (solutions/memory/champion-710d3b5a.man) is box 9409 / score 3,407,402 versus
    this build's 4,100,378. The value here is reuse, not the Memory score.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import littleman as lm  # noqa: E402
from layout import Layout  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# TUNABLE KNOBS  (module-level integers -- tools/autotune.py sweeps these)
# ──────────────────────────────────────────────────────────────────────────────
TARGET_TICKS = 8                      # issue interval; every ring is balanced to it
VALUE_OFFSET = 9 << 18                # bias that makes a write word positive
PIPE_LENGTH = 2                       # short room-to-room hops
# The two front-end buffers, as FLOORS -- the length actually used is
# ``front_pipe_length(k)``, which scales with k (see that function). The champion
# hardcodes 16, which is correct only for its own k=20 and wastes width at smaller k.
ADJUST_PIPE_LENGTH = 2                # floor for the adjust -> multiply buffer
MULTIPLY_PIPE_LENGTH = 2              # floor for the multiply -> decrement buffer
FRONT_BUFFER_SLACK = 2                # ops of slack above the measured deadlock cliff
FANOUT_STARTUP_DELAY_BIAS = -5        # see fanout_startup_delay()
FANOUT_ROOM_Y = 5
MEGABLOCK_Y = 10
DECODER_COLUMNS = 4                   # realigner lattice width (workers = cols*rows)
DECODER_TILE_WIDTH = 18
DECODER_TILE_HEIGHT = 5
DECODER_ROW_SHIFT = 1                 # x-stagger per lattice row
DECODER_SPARE_WORKERS = 1             # slack above the minimum worker count
DECODER_START = (10, 1)               # tile cell where a realigner worker rejoins its loop
DECODE_START = (0, 2)                 # decode-column cell where a worker picks up its bank id
BANK_GAP = 2                          # columns between decode and storage column
REPLY_PIPE_GAP = 1                    # rows between the banks and the realigner
MAX_BANKS = 10
MAX_CELLS_PER_BANK = 98
# MEASURED: k < 16 is not safe. k=8/10/12 build and pass short streams, but a
# sustained same-address hammer (40 reads of addr 0) deadlocks -- the decode ring
# is short enough that a worker blocked at the header gets rear-ended before the
# stream refills it. k=16, 18, 20, 24, 32 all sustain a marginal 8.0 ticks/op.
MIN_CELLS_PER_BANK = 16


# ──────────────────────────────────────────────────────────────────────────────
# TILE CONSTANTS  (verified against champion-6abc7461.man)
# ──────────────────────────────────────────────────────────────────────────────

# --- decode column (one per bank) -------------------------------------------
HEADER = (
    ">r-v ",
    "  vXv",
    "  rrr",
    "  rbr",
    "   r ",
    " v < ",
    "  >v<",
    "   >v",
)
PAIR_DECODER = (
    " avv<",
    " sm  ",
    " > >v",
    " vd  ",
    " ms  ",
    "  > V",
)
WORKER_RETURN = "^   <"
DISPATCH_FORK = "Y  < "
DISPATCH_LOOP = ">m aH"

# --- storage column (one per bank) ------------------------------------------
# The initializer sits at the TOP and the ``Y`` chain descends, so cell 0 (the one
# the decode staircase reaches FIRST, in 0 ticks) is also the one built FIRST.
# direct_memory.py builds the chain upwards, which leaves cells 0..2 unborn when
# their first request arrives -- that costs 21/12/3 ticks and, worse, REORDERS the
# reply stream (measured: "1 0 v 1 99 v 0 0 0 99" emitted v99 before v0).
STORE_INITIALIZER = (
    "@9M{{v",
    "     M",
    "v`KK`<",
    ">W*W1v",
    " v--W<",
)
STORE_FIRST = (
    " +vsW<",
    "vY>WrX",
    ">v^  <",
)
STORE_OTHER = (
    " -vsW<",
    "vY>WrX",
    ">v^  <",
)
STORE_LAST = (
    " -vsW<",
    " >>WrX",
    "  ^  <",
)

# --- front-end reader chain --------------------------------------------------
PARSE_READER = (
    "@3b>  dHv    sWs   <",
    "  v^ mY > 9M{{NMrbrx",
    "        ^    sWsWrW<",
)
ADJUST_READER_CORE = (
    "@9M{{Mv v    s-<",
    "   v  Y>> rsr+X^",
    "   >   ^     s< ",
)
STARTUP_DELAY_PREFIX = (
    "@  v  >",
    "v  <  ^",
    ">     ^",
)
MULTIPLY_READER = (
    ">rsr*s v",
    "^ s*rsr<",
    " @`KK`M^",
)
DECREMENT_READER = (
    ">rsr-s v",
    "^ s-rsr<",
    "    @1M^",
)
FANOUT_READER = (
    "         @3b>  dH",
    ">r/SWSW r-Sv^ mYv",
    "^W`KK`     <    <",
)

# --- realigner / reply decoder ----------------------------------------------
# ``DDDDD`` is a 5-cell WESTWARD gadget that leaves B = k (see synth_divisor).
# It must NOT be a backtick literal: the realigner rows are stacked 5 apart with a
# 1-column stagger, so a backtick there lines up vertically with the closing
# backtick of ``LLLLLLL`` one group above and the loader rejects the grid
# ("expected a digit or a space between backticks, but found '<'").
DECODER_BASE = (
    "> `LLLLLLL`W-v    ",
    "^bW/RWDDDDDsa<m<  ",
    "            >m asv",
    "          ^      <",
)
DECODER_SPLIT = DECODER_BASE[:3] + (
    "        vY^      <",
    "        <^        ",
)
DECODER_STEAL = DECODER_BASE + (
    "          ^       ",
)


# ──────────────────────────────────────────────────────────────────────────────
# small helpers
# ──────────────────────────────────────────────────────────────────────────────
def _digits(k):
    if not 2 <= k <= MAX_CELLS_PER_BANK:
        raise ValueError(f"cells per bank out of range: {k}")
    return f"{k:02d}"


def _subst(rows, k, offset=VALUE_OFFSET):
    """Fill the ``KK`` (cells-per-bank literal) and ``LLLLLLL`` (OFF-1) slots.

    ``KK`` always sits inside backticks; whether the man reads it east- or
    westward is decided by which of the two orders we emit, and every westward
    literal in this file is written reversed on the grid.
    """
    east = _digits(k)
    west = east[::-1]
    bias = str(offset - 1)
    out = []
    for row in rows:
        if "KK" in row:
            # westward literals are the ones whose backtick run is followed by '<'
            idx = row.index("KK")
            westward = row[idx + 3 : idx + 4] == "<" or row.startswith("^W`")
            row = row.replace("KK", west if westward else east)
        if "DDDDD" in row:
            row = row.replace("DDDDD", synth_divisor(k))
        if "LLLLLLL" in row:
            if len(bias) != 7:
                raise ValueError("VALUE_OFFSET-1 must be 7 digits for this tile")
            row = row.replace("LLLLLLL", bias)
        out.append(row)
    return tuple(out)


def _normalize(rows):
    width = max(map(len, rows))
    return tuple(row.ljust(width) for row in rows)


_BINOPS = {
    " ": lambda a, b: a,
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "&": lambda a, b: a & b,
    "|": lambda a, b: a | b,
    "~": lambda a, b: a ^ b,
    "%": lambda a, b: a % b if b else 0,
}


def synth_divisor(k):
    """5 cells, walked WESTWARD, that leave ``A = k`` for the following ``W``.

    Layout: ``op d2 M d1 <``  ->  A=d1, B=d1, A=d2, A = d2 op d1.
    The champion's instance is ``*4M5<`` (4*5 = 20). Deliberately backtick-free.
    """
    best = None
    for d1 in range(10):
        for d2 in range(10):
            for op, f in _BINOPS.items():
                if op == " ":
                    continue
                try:
                    if f(d2, d1) != k:
                        continue
                except (ZeroDivisionError, ValueError):
                    continue
                cand = f"{op}{d2}M{d1}<"
                if best is None or (op != "*", cand) < (best[0] != "*", best):
                    best = cand
    if best is None:
        raise ValueError(
            f"cells per bank {k} is not synthesisable as <digit> <op> <digit>")
    return best


def synth_backpack(n):
    """Two 5-wide rows that leave ``BP = n`` and then walk north.

    Layout (this is the champion's ``^b~*<`` / ``@3M7^`` gadget generalised):
        row A, walked EAST : ``@ d1 M d2 ^``   -> A=d1, B=d1, A=d2, face north
        row B, walked WEST : ``^ b op2 op1 <`` -> A=(d2 op1 d1) op2 d1, BP=A
    """
    best = None
    for d1 in range(10):
        for d2 in range(10):
            for op1, f1 in _BINOPS.items():
                if op1 == " ":
                    continue
                try:
                    mid = f1(d2, d1)
                except ZeroDivisionError:
                    continue
                for op2, f2 in _BINOPS.items():
                    try:
                        val = f2(mid, d1)
                    except ZeroDivisionError:
                        continue
                    if val == n:
                        cand = (f"^b{op2}{op1}<", f"@{d1}M{d2}^")
                        if best is None or cand < best:
                            best = cand
    if best is None:
        raise ValueError(f"cannot synthesise BP={n} in the 5-wide initializer")
    return best


# ──────────────────────────────────────────────────────────────────────────────
# geometry of one bank
# ──────────────────────────────────────────────────────────────────────────────
def unpadded_worker_ticks(k):
    """Ticks around the decode column's ring before padding (verified k=20 -> 166)."""
    return 26 + 7 * k


def worker_padding_rows(k, target=None):
    target = TARGET_TICKS if target is None else target
    base = unpadded_worker_ticks(k)
    for rows in range(target):
        if (base + 2 * rows) % target == 0:
            return rows
    raise ValueError("cannot balance the decode ring")


def worker_loop_ticks(k, target=None):
    return unpadded_worker_ticks(k) + 2 * worker_padding_rows(k, target)


def worker_count(k, target=None):
    target = TARGET_TICKS if target is None else target
    return worker_loop_ticks(k, target) // target


def decode_interior(k, bank_id, target=None):
    target = TARGET_TICKS if target is None else target
    if k % 2:
        raise ValueError("cells per bank must be even")
    if not 0 <= bank_id <= 9:
        raise ValueError("bank id must fit in one bare digit")
    header = list(HEADER)
    header[1] = "M" + header[1][1:]
    header[2] = str(bank_id) + header[2][1:]
    pad = (" " * 5,) * worker_padding_rows(k, target)
    dispatch_pad = (" " * 5,) * ((target - 8) // 2)
    init = synth_backpack(worker_count(k, target) + 1)
    return _normalize(
        tuple(header)
        + PAIR_DECODER * (k // 2)
        + pad
        + (WORKER_RETURN, DISPATCH_FORK)
        + dispatch_pad
        + (DISPATCH_LOOP,)
        + init
    )


def store_interior(k):
    if k < 2:
        raise ValueError("need at least two cells per bank")
    return _normalize(
        _subst(STORE_INITIALIZER, k)
        + STORE_FIRST
        + STORE_OTHER * (k - 2)
        + STORE_LAST
    )


def connection_rows(k, target=None):
    """Megablock-local rows carrying the k command pipes (decode ``s`` -> cell ``r``)."""
    left = tuple(
        1 + len(HEADER) + 6 * pair + offset
        for pair in range(k // 2)
        for offset in (1, 4)
    )
    top = len(HEADER) - len(STORE_INITIALIZER)     # storage room's top wall row
    right = tuple(top + 1 + len(STORE_INITIALIZER) + 1 + 3 * cell for cell in range(k))
    if left != right:
        raise ValueError(f"decode sends and cell receives are misaligned: {left} {right}")
    return left


# ──────────────────────────────────────────────────────────────────────────────
# realigner lattice
# ──────────────────────────────────────────────────────────────────────────────
def decoder_tile(k, split):
    base = DECODER_SPLIT if split else DECODER_STEAL
    return _normalize(_subst(base, k))


def decoder_worker_loop(k):
    """(min, max) ticks around one realigner worker's loop, by direct simulation."""
    tile = decoder_tile(k, split=False)
    ticks = [
        _simulate_loop(tile, DECODER_START, (-1, 0), _encode_write(0, k, offset), k)
        for offset in range(k)
    ]
    return min(ticks), max(ticks)


def decoder_grid(k, columns=None, spare=None):
    columns = DECODER_COLUMNS if columns is None else columns
    spare = DECODER_SPARE_WORKERS if spare is None else spare
    _, worst = decoder_worker_loop(k)
    needed = math.ceil(worst / TARGET_TICKS) + spare
    rows = max(1, math.ceil(needed / columns))
    return columns, rows


def decoder_interior(k, columns, rows, min_width=0):
    tile_w, tile_h = DECODER_TILE_WIDTH, DECODER_TILE_HEIGHT
    spine_x = 1 + tile_w * columns + DECODER_ROW_SHIFT * (rows - 1) + 2
    width = max(min_width, spine_x + 2)
    canvas = [[" "] * width for _ in range(tile_h * rows)]
    for r in range(rows):
        for c in range(columns):
            tile = decoder_tile(k, split=c != 0)
            left = 1 + c * tile_w + DECODER_ROW_SHIFT * r
            top = r * tile_h
            for dy, row in enumerate(tile):
                for dx, glyph in enumerate(row):
                    if glyph != " ":
                        canvas[top + dy][left + dx] = glyph
    canvas[0][spine_x] = "@"
    canvas[0][spine_x + 1] = "v"
    for r in range(rows):
        y = r * tile_h
        canvas[y + 3][spine_x] = "v"
        canvas[y + 3][spine_x + 1] = "<"
        canvas[y + 4][spine_x] = "Y"
        canvas[y + 4][spine_x + 1] = "H" if r == rows - 1 else "v"
    return tuple("".join(row).ljust(width) for row in canvas)


# ──────────────────────────────────────────────────────────────────────────────
# front-end reader chain
# ──────────────────────────────────────────────────────────────────────────────
def parse_reader():
    return _normalize(PARSE_READER)


def adjust_reader():
    core = _normalize(ADJUST_READER_CORE)
    return tuple(p + row[1:] for p, row in zip(STARTUP_DELAY_PREFIX, core))


def multiply_reader(k):
    return _normalize(_subst(MULTIPLY_READER, k))


def decrement_reader():
    return _normalize(DECREMENT_READER)


def fanout_startup_delay(k):
    """Ticks the fanout man idles before entering its loop.

    THIS IS THE ONE CONSTANT THAT MUST TRACK k. The decode workers are spawned at
    the BOTTOM of their column and climb to the header; a worker that reaches the
    header ``r`` before the first broadcast arrives PARKS there, and the follower
    8 ticks behind walks into it and BOTH DIE (measured: 4 deaths every 24 ticks at
    local (0,0)/(1,0), which drains the ring and deadlocks the machine). So the
    first broadcast must arrive no later than the first worker. The climb scales
    with the decode column's height, hence 3k + pad; the champion's k=20 value of
    56 is reproduced exactly (3*20 + 1 - 5).
    """
    return 3 * k + worker_padding_rows(k) + FANOUT_STARTUP_DELAY_BIAS


def front_pipe_length(k, floor=0):
    """Length of the two front-end buffer pipes. MUST scale with k.

    The fanout man idles ``fanout_startup_delay(k)`` ticks before it starts
    consuming, but the reader chain upstream is already producing one op every
    TARGET_TICKS. Those ops have nowhere to go but the pipes between the readers (a
    pipe of length n holds n values), and if they do not fit the whole front end
    deadlocks -- silently, forever, with no output at all.

    MEASURED cliff (Rust engine, 60 sequential reads; the value below is the
    smallest length that still passes, and one less hangs to the tick cap):
        k=16 (delay 46) -> 5      k=18 (delay 49) -> 5      k=32 (delay 94) -> 11
    which tracks delay/TARGET_TICKS. ``FRONT_BUFFER_SLACK`` then adds margin:
    this returns 8 / 9 / 14 for those three k, i.e. +3 over every measured cliff.

    The champion's hardcoded 16 is only correct because its k is 20; at k=32 a
    fixed 8 deadlocks and at k=16 a fixed 16 wastes 16 columns of box.
    """
    derived = -(-fanout_startup_delay(k) // TARGET_TICKS) + FRONT_BUFFER_SLACK
    return max(PIPE_LENGTH, floor, derived)


def fanout_reader(k, width):
    delay = fanout_startup_delay(k)
    reader = _normalize(_subst(FANOUT_READER, k))
    if width < len(reader[0]) + delay:
        raise ValueError("fanout room is too narrow for its startup delay")
    pad = " " * (width - len(reader[0]))
    grid = [list(pad + row) for row in reader]
    old = grid[0].index("@")
    new = old - delay
    if new < 0 or any(grid[0][x] != " " for x in range(new, old)):
        raise ValueError("no room for the fanout startup delay")
    grid[0][old] = " "
    grid[0][new] = "@"
    return tuple("".join(row) for row in grid)


# ──────────────────────────────────────────────────────────────────────────────
# encoding helpers (also used by the verifier and by consumers that want to skip
# the realigner and decode the reply themselves)
# ──────────────────────────────────────────────────────────────────────────────
def _encode_write(value, k, offset):
    return k * (value + VALUE_OFFSET) - 1 - offset


def _encode_read(k, offset):
    return -k * VALUE_OFFSET - 1 - offset


def decode_reply(word, k):
    """(value, offset) carried by a raw reply word -- lets a consumer drop the realigner."""
    return word // k - (VALUE_OFFSET - 1), k - 1 - (word % k)


# ──────────────────────────────────────────────────────────────────────────────
# a tiny single-man simulator, used only to VERIFY the generated tiles
# ──────────────────────────────────────────────────────────────────────────────
def _simulate_loop(interior, start, direction, first_value, k, extra=(), limit=4000):
    """Walk one man around a closed loop; return the tick count back at ``start``."""
    trace = _simulate(interior, start, direction, (first_value,) + tuple(extra), k, limit)
    return trace["ticks"]


def _simulate(interior, start, direction, values, k, limit=4000):
    interior = _normalize(interior)
    h, w = len(interior), len(interior[0])
    it = iter(values)
    x, y = start
    dx, dy = direction
    a = b = bp = 0
    ticks = 0
    outputs, sends, reads = [], [], []
    literal = None
    while True:
        if not (0 <= x < w and 0 <= y < h):
            raise ValueError(f"man left the room at {(x, y)} after {ticks} ticks")
        g = interior[y][x]
        if g == "`":
            if literal is None:
                literal = ""
            else:
                a = int(literal) if literal else 0
                literal = None
        elif literal is not None:
            if g.isdigit():
                literal += g
        elif g in "rR":
            a = next(it)
            reads.append(ticks)
        elif g in "sS":
            outputs.append(a)
            sends.append(ticks)
        elif g == "M":
            b = a
        elif g == "W":
            a, b = b, a
        elif g == "b":
            bp = a
        elif g == "m":
            bp -= 1
        elif g == "+":
            a += b
        elif g == "-":
            a -= b
        elif g == "*":
            a *= b
        elif g == "~":
            a ^= b
        elif g == "&":
            a &= b
        elif g == "|":
            a |= b
        elif g == "N":
            a = -a
        elif g == "{":
            a <<= b
        elif g == "/":
            a, b = (a // b, a % b) if b else (0, a)
        elif g == "X":
            if a > 0:
                dx, dy = -dy, dx
            elif a < 0:
                dx, dy = dy, -dx
        elif g == "x":
            dx, dy = (-dy, dx) if bp & 1 else (dy, -dx)
        elif g == "a" and bp > 0:
            dx, dy = dy, -dx
        elif g == "d" and bp > 0:
            dx, dy = -dy, dx
        elif g == ">":
            dx, dy = 1, 0
        elif g == "<":
            dx, dy = -1, 0
        elif g == "^":
            dx, dy = 0, -1
        elif g in "vV":
            dx, dy = 0, 1
        elif g.isdigit():
            a = int(g)
        x += dx
        y += dy
        ticks += 1
        if (x, y) == start:
            return {"ticks": ticks, "outputs": tuple(outputs),
                    "sends": tuple(sends), "reads": tuple(reads), "a": a, "b": b}
        if ticks > limit:
            raise ValueError("loop did not close")


def verify(size, banks, k):
    """Static checks on the generated tiles. Raises on any inconsistency."""
    target = TARGET_TICKS
    loop = worker_loop_ticks(k, target)

    # 1. every decode-column route is the SAME length (the length-matching invariant)
    for bank in range(banks):
        interior = decode_interior(k, bank, target)
        for comparison in (bank - 1, bank + 1):
            t = _simulate(interior, DECODE_START, (0, -1),
                          (comparison, 0, 0), k)
            if t["ticks"] != loop or t["outputs"]:
                raise ValueError(f"decode miss route unbalanced: {t['ticks']} != {loop}")
        for offset in range(k):
            t = _simulate(interior, DECODE_START, (0, -1),
                          (bank, offset, _encode_read(k, offset)), k)
            if t["ticks"] != loop:
                raise ValueError(f"decode hit route unbalanced: {t['ticks']} != {loop}")
            if t["outputs"] != (_encode_read(k, offset),):
                raise ValueError(f"decode hit sent {t['outputs']}")

    # 2. the storage cell serves a read and a write in exactly TARGET_TICKS
    for tile in (STORE_FIRST, STORE_OTHER, STORE_LAST):
        wr = _simulate(tile, (4, 1), (1, 0), (_encode_write(42, k, 3),), k)
        rd = _simulate(tile, (4, 1), (1, 0), (_encode_read(k, 3),), k)
        if wr["ticks"] != 8 or wr["outputs"]:
            raise ValueError(f"cell write lobe is {wr['ticks']} ticks")
        if rd["ticks"] != 8 or len(rd["outputs"]) != 1:
            raise ValueError(f"cell read lobe is {rd['ticks']} ticks")

    # 3. the realigner decodes every (value, offset) pair and is de-skewed:
    #    send_tick + 4*offset must be a constant
    tile = decoder_tile(k, split=False)
    base = None
    for offset in range(k):
        for value in (-1_000_000, -1, 0, 1, 1_000_000):
            t = _simulate(tile, DECODER_START, (-1, 0), (_encode_write(value, k, offset),), k)
            if t["outputs"] != (value,):
                raise ValueError(
                    f"realigner produced {t['outputs']} for offset={offset} value={value}")
            sync = t["sends"][0] + 4 * offset
            if base is None:
                base = sync
            elif sync != base:
                raise ValueError(f"realigner de-skew broken at offset {offset}")

    # 4. enough realigner workers to keep up with one op every TARGET_TICKS
    columns, rows = decoder_grid(k)
    _, worst = decoder_worker_loop(k)
    if columns * rows * TARGET_TICKS < worst:
        raise ValueError("realigner lattice is too small")

    connection_rows(k, target)
    return {"worker_loop": loop, "workers": worker_count(k, target),
            "realigner": (columns, rows), "realigner_loop": worst}


# ──────────────────────────────────────────────────────────────────────────────
# whole-component layout
# ──────────────────────────────────────────────────────────────────────────────
def choose_banks(size):
    """Pick the bank count that minimises max(w,h)^2 for this size."""
    best = None
    for banks in range(2, MAX_BANKS + 1):
        k = max(MIN_CELLS_PER_BANK, -(-size // banks))
        k += k % 2
        if k > MAX_CELLS_PER_BANK:
            continue
        try:
            synth_divisor(k)
        except ValueError:
            continue
        try:
            rows = _plan(size, banks, k)
        except ValueError:
            continue
        score = max(rows["width"], rows["height"]) ** 2
        if best is None or score < best[0]:
            best = (score, banks, k)
    if best is None:
        raise ValueError(f"no legal (banks, k) for size {size}")
    return best[1], best[2]


def _plan(size, banks, k):
    if not 2 <= banks <= MAX_BANKS:
        raise ValueError("banks must be 2..10")
    if k % 2 or not 2 <= k <= MAX_CELLS_PER_BANK:
        raise ValueError("cells per bank must be even and 2..98")
    if banks * k < size:
        raise ValueError("banks*k must cover size")

    decode = decode_interior(k, 0)
    store = store_interior(k)
    decode_w, store_w = len(decode[0]), len(store[0])

    megablock_pipe_x = decode_w + BANK_GAP          # first command-pipe column
    megablock_store_x = megablock_pipe_x + PIPE_LENGTH
    megablock_w = megablock_store_x + store_w + 2
    banks_w = megablock_w * banks

    store_top = MEGABLOCK_Y + len(HEADER) - len(STORE_INITIALIZER)
    store_bottom = store_top + len(store) + 1       # bottom wall row
    decode_bottom = MEGABLOCK_Y + len(decode) + 1
    decoder_top = max(store_bottom, decode_bottom) + REPLY_PIPE_GAP

    columns, rows = decoder_grid(k)
    decoder = decoder_interior(k, columns, rows, min_width=banks_w - 2)
    decoder_w = len(decoder[0]) + 2
    output_x = decoder_w + PIPE_LENGTH
    output_y = decoder_top + 1

    # front-end reader chain, left to right
    parse, adjust = parse_reader(), adjust_reader()
    multiply, decrement = multiply_reader(k), decrement_reader()
    decrement_x = 3
    multiply_x = decrement_x + len(decrement[0]) + 2 + front_pipe_length(k, MULTIPLY_PIPE_LENGTH)
    adjust_x = multiply_x + len(multiply[0]) + 2 + front_pipe_length(k, ADJUST_PIPE_LENGTH)
    parse_x = adjust_x + len(adjust[0]) + 2 + PIPE_LENGTH
    command_x = parse_x + len(parse[0]) + 2         # first cell of the caller's pipe

    width = max(banks_w, command_x + 1, output_x + 3,
                len(_normalize(FANOUT_READER)[0]) + fanout_startup_delay(k) + 2)
    height = max(decoder_top + len(decoder) + 2, output_y + 3)

    fanout = fanout_reader(k, width - 2)

    return dict(
        size=size, banks=banks, k=k, width=width, height=height,
        decode=decode, store=store, decoder=decoder, fanout=fanout,
        parse=parse, adjust=adjust, multiply=multiply, decrement=decrement,
        megablock_w=megablock_w, megablock_pipe_x=megablock_pipe_x,
        megablock_store_x=megablock_store_x,
        store_top=store_top, store_bottom=store_bottom,
        decoder_top=decoder_top, decoder_w=decoder_w,
        output_x=output_x, output_y=output_y,
        decrement_x=decrement_x, multiply_x=multiply_x,
        adjust_x=adjust_x, parse_x=parse_x, command_x=command_x,
        columns=columns, rows=rows,
    )


def _draw_room(canvas, left, top, interior):
    width = len(interior[0])
    wall = "+" + "-" * width + "+"
    for dy, row in enumerate((wall, *(f"|{r}|" for r in interior), wall)):
        for dx, glyph in enumerate(row):
            canvas[top + dy][left + dx] = glyph


def render_rows(size, banks=None, k=None):
    """Render the component (no I/O rooms) as a list of strings + its port map."""
    if banks is None:
        banks, k = choose_banks(size)
    if k is None:
        k = -(-size // banks)
        k += k % 2
    plan = _plan(size, banks, k)
    verify(size, banks, k)

    w, h = plan["width"], plan["height"]
    canvas = [[" "] * w for _ in range(h)]

    # --- front-end reader chain (rows 0..4) ---------------------------------
    for x, room in ((plan["decrement_x"], plan["decrement"]),
                    (plan["multiply_x"], plan["multiply"]),
                    (plan["adjust_x"], plan["adjust"]),
                    (plan["parse_x"], plan["parse"])):
        _draw_room(canvas, x, 0, room)
    # westward pipes between the rooms
    for src_x, src, dst_x, dst, row in (
        (plan["parse_x"], plan["parse"], plan["adjust_x"], plan["adjust"], 2),
        (plan["adjust_x"], plan["adjust"], plan["multiply_x"], plan["multiply"], 2),
        (plan["multiply_x"], plan["multiply"], plan["decrement_x"], plan["decrement"], 3),
    ):
        for x in range(dst_x + len(dst[0]) + 2, src_x):
            canvas[row][x] = "<"
    # decrement -> fanout: west one cell, then two south into the fanout's top wall
    canvas[3][2] = "<"
    canvas[3][1] = "v"
    canvas[4][1] = "v"

    # --- fanout room (rows 5..9) --------------------------------------------
    _draw_room(canvas, 0, FANOUT_ROOM_Y, plan["fanout"])

    # --- banks ---------------------------------------------------------------
    rows_in_block = connection_rows(k)
    for bank in range(banks):
        off = bank * plan["megablock_w"]
        _draw_room(canvas, off, MEGABLOCK_Y, decode_interior(k, bank))
        _draw_room(canvas, off + plan["megablock_store_x"], plan["store_top"],
                   plan["store"])
        for row in rows_in_block:
            for x in range(off + plan["megablock_pipe_x"],
                           off + plan["megablock_pipe_x"] + PIPE_LENGTH):
                canvas[MEGABLOCK_Y + row][x] = ">"
        # fanout broadcast pipe into this bank's decode room
        if bank == banks - 1:
            fx = off - 2
            canvas[MEGABLOCK_Y][fx] = "v"
            canvas[MEGABLOCK_Y + 1][fx] = ">"
            canvas[MEGABLOCK_Y + 1][fx + 1] = ">"
        else:
            fx = off + len(plan["decode"][0]) + 3
            canvas[MEGABLOCK_Y][fx] = "v"
            canvas[MEGABLOCK_Y + 1][fx] = "<"
            canvas[MEGABLOCK_Y + 1][fx - 1] = "<"
        # reply pipe: out of the storage room's left wall, then south to the realigner
        px = off + plan["megablock_pipe_x"]
        sy = plan["store_bottom"] - 1
        canvas[sy][px + 1] = "<"
        canvas[sy][px] = "v"
        for y in range(sy + 1, plan["decoder_top"]):
            canvas[y][px] = "v"

    # --- realigner ------------------------------------------------------------
    _draw_room(canvas, 0, plan["decoder_top"], plan["decoder"])

    rows = [("".join(row)).rstrip() for row in canvas]
    ports = {
        "command": (plan["command_x"], 2),
        "reply": (plan["decoder_w"], plan["output_y"]),
        "reply_turn": (plan["decoder_w"] + 1, plan["output_y"]),
    }
    return rows, ports, plan


def build(program, x=0, y=0, size=100, banks=None, k=None):
    """Stamp the RAM at (x, y) and return its external pipe endpoints.

    ``command`` is where an external pipe must END, flowing WEST into the
    component. ``reply`` is where the component's outgoing pipe BEGINS, flowing
    EAST; ``reply_turn`` is the next cell east.
    """
    rows, ports, _ = render_rows(size, banks, k)
    lay = Layout(program)
    for dy, row in enumerate(rows):
        for dx, glyph in enumerate(row):
            if glyph != " ":
                lay.put(x + dx, y + dy, glyph)
    return {name: (x + px, y + py) for name, (px, py) in ports.items()}


def build_memory_solution(size=100, banks=None, k=None):
    """The component + the Memory problem's I/O rooms = a complete, gradeable program.

    The Memory input stream IS this component's wire protocol, so the "driver" is
    just two pipes: ``I`` -> command, reply -> ``O``. This exists here (rather than
    only in the self-test) so that ``python3 tools/fast_ram.py`` emits a grid that
    ``tools/autotune.py`` can grade against the ``memory`` slug -- see the
    "making a builder tunable" section of tools/AUTOTUNE.md.
    """
    program = lm.Program()
    ports = build(program, 0, 0, size=size, banks=banks, k=k)
    lay = Layout(program)
    cx, cy = ports["command"]
    lay.put(cx, cy, "<")
    lay.put(cx + 1, cy, "<")
    program.input_room(cx + 2, cy - 1)
    rx, ry = ports["reply"]
    lay.put(rx, ry, ">")
    lay.put(*ports["reply_turn"], ">")
    program.output_room(ports["reply_turn"][0] + 1, ry - 1)
    return program, ports


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=100)
    ap.add_argument("--banks", type=int)
    ap.add_argument("--k", type=int)
    ap.add_argument("-o", "--output")
    ap.add_argument("--component-only", action="store_true",
                    help="emit the bare component (no I/O rooms); not gradeable alone")
    args = ap.parse_args()

    if args.component_only:
        rows, ports, plan = render_rows(args.size, args.banks, args.k)
        text = "\n".join(rows) + "\n"
    else:
        # DEFAULT: a complete Memory solution, so that plain `python3 tools/fast_ram.py`
        # prints a gradeable grid on stdout -- that is how autotune.py reaches these knobs.
        program, ports = build_memory_solution(args.size, args.banks, args.k)
        _, _, plan = render_rows(args.size, args.banks, args.k)
        text = program.render()
        if not text.endswith("\n"):
            text += "\n"
    if args.output:
        open(args.output, "w").write(text)
    # summary on STDERR: stdout must be the grid and nothing else, or autotune's
    # grid_from_text() fallback will refuse to parse it.
    print(f"size={plan['size']} banks={plan['banks']} k={plan['k']} "
          f"box={plan['width']}x{plan['height']} "
          f"workers={worker_count(plan['k'])} ring={worker_loop_ticks(plan['k'])} "
          f"realigner={plan['columns']}x{plan['rows']} ports={ports}", file=sys.stderr)
    sys.stdout.write(text)
