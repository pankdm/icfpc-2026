#!/usr/bin/env python3
"""fast_ram_model.py -- structural + cost model of the Memory champion's random-access store.

Dependency-free (stdlib only).  Run it:

    python3 scratchpad/fast_ram_model.py            # self-test + geometry table
    python3 scratchpad/fast_ram_model.py --explain  # + derivation of every constant

WHAT THIS MODELS
----------------
solutions/memory/champion-6abc7461.man (108x108, box 11664, 7/7 public, 24/24 server).
A 100-cell random-access store built as a *length-matched systolic ring*: the address decode
is an O(cells-per-bank) walk, but 21 request-carrying men circulate a 168-tick loop, so the
ISSUE INTERVAL is 168/21 = 8 ticks.  8 ticks/op is a THROUGHPUT number, not a latency.

A parameterised builder already exists: solutions/memory/direct_memory.py (1029 lines,
committed 39de9ed, one commit before the champion 287fa0b).  It is hard-locked to k=20 today
(direct_memory.py:849) and its cell ids are 0-based, which is BROKEN -- see IDZERO below.
The champion = direct_memory output + an extra "payload -= 1" room that makes ids 1-based.

EVERYTHING BELOW IS EITHER
  [M] measured with interp/target/release/lm on the champion, or
  [S] read out of direct_memory.py source, or
  [D] derived arithmetic, flagged where it rests on a single data point.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field


# =============================================================================
# 1. PARAMETERISED STRUCTURE
# =============================================================================
#
# Component = `banks` (l) columns, each holding `cells_per_bank` (k) memory words.
# size = k * l.  A bank is a 17-column "megablock":
#
#   x+0 .. x+6    decode column   (outer 7 wide,  outer 3k+16+pad tall)   [M: 7x76 at k=20]
#   x+7 .. x+8    pipe gutter     (k length-2 command pipes, one per cell)
#   x+9 .. x+16   storage column  (outer 8 wide,  outer 3k+7 tall)        [M: 8x67 at k=20]
#
# The interior widths (5 and 6) are FIXED STRINGS in direct_memory.py -- HEADER/PAIR_DECODER
# are 5 wide, SECOND_FIRST/SECOND_OTHER are 6 wide -- so the pitch is 17 for every k.  [S]
# Verified on the champion: decode columns start at x = 0, 17, 34, 51, 68.  [M]
#
# Vertical stack of the whole component (y origin 0):
#
#   rows 0..4                      front end (parse/bias/multiply/decrement chain)
#   rows 5..9                      fanout room  (divmod by k, broadcast to all banks)
#   rows 10..10+3k+15+pad          bank region
#   rows 3k+26 .. +5*rows_dec+2    reply realigner ("decoder"), OPTIONAL
#
# H = 3k + 28 + 5*rows_dec          [M: k=20, rows_dec=4 -> 108 = the champion's exact height]
# W = max(17*l, 18*cols_dec + 10, front_end_width)

PITCH = 17                 # [S] bank-to-bank column pitch, independent of k
DECODE_COL_W = 7           # [M] outer width
STORAGE_COL_W = 8          # [M] outer width
CELL_ROWS = 3              # [M] one memory word = 3 grid rows x 6 interior cols
BANK_TOP = 10              # [S] MEGABLOCK_Y
REALIGN_TILE_W = 18        # [S] DECODER_BASE_WIDTH (champion drops the 12-wide prefix)
REALIGN_TILE_H = 5         # [S] DECODER_TILE_HEIGHT
REALIGN_SLACK_W = 10       # [S] spine + detour + walls + row shifts
FRONT_END_W_MEMORY = 108   # [M] champion rows 0..4 reach x=107, i.e. 108 columns from x=0
FRONT_END_W_REUSABLE = 50  # [D] est: bias(24) + multiply(10) + decrement(10) + 2 short pipes
CELL_SERVICE_TICKS = 8     # [M] both the READ lobe and the WRITE lobe are exactly 8 ticks

BIAS = 9 << 18             # [M] 2359296, built by the 4 glyphs `9M{{`
MAX_ABS_VALUE = 10 ** 6    # [S] the Memory problem's |value| bound; BIAS must exceed it


@dataclass(frozen=True)
class Pins:
    """Where external pipes attach -- mirrors tools/split_ram.py's return contract."""
    command: tuple[int, int]
    reply: tuple[int, int]
    reply_turn: tuple[int, int]


@dataclass(frozen=True)
class FastRam:
    """Parameterised description of one instance."""
    size: int
    banks: int                 # l
    cells_per_bank: int        # k
    target_ticks: int = 8      # issue interval the rings are tuned to
    realign: bool = True       # keep the reply de-skewer (in-order replies) or drop it
    realign_rows: int = 0      # tiles down; 0 = auto
    realign_cols: int = 0      # tiles across; 0 = auto
    front_end_width: int = FRONT_END_W_REUSABLE

    # ---- validity -------------------------------------------------------
    def problems(self) -> list[str]:
        p = []
        k, l = self.cells_per_bank, self.banks
        if k <= 0 or k % 2:
            p.append("k must be positive and EVEN (PAIR_DECODER is a 6-row/2-cell tile) [S:132]")
        if l <= 0:
            p.append("l must be positive")
        if k * l < self.size:
            p.append(f"k*l={k*l} < size={self.size}")
        if self.target_ticks < CELL_SERVICE_TICKS or self.target_ticks % 2:
            p.append("target_ticks must be even and >= 8 (the cell service loop is 8) [S:139]")
        if l > 10:
            p.append("l>10 needs a multi-digit bank literal; today the bank id is one "
                     "digit at decode-column local (1,13) [S:171]")
        return p

    # ---- ring timing ----------------------------------------------------
    @property
    def ring_unpadded(self) -> int:
        """Decode-column loop length before balancing.  [S] unpadded_worker_ticks()"""
        return 26 + 7 * self.cells_per_bank

    @property
    def ring_pad_rows(self) -> int:
        """Blank rows added so the loop divides target_ticks.  [S] worker_padding_rows()"""
        base = self.ring_unpadded
        for r in range(self.target_ticks):
            if (base + 2 * r) % self.target_ticks == 0:
                return r
        raise ValueError("cannot balance the decode ring")

    @property
    def ring_period(self) -> int:
        """[M] 168 for k=20 -- man #10 hits the ring head at t=253,421,589,757."""
        return self.ring_unpadded + 2 * self.ring_pad_rows

    @property
    def ring_workers(self) -> int:
        """[M] 21 for k=20, counted live in the champion under load."""
        return self.ring_period // self.target_ticks

    # ---- reply realigner ------------------------------------------------
    @property
    def realign_worker_loop(self) -> int:
        """Longest realigner tile cycle.  [S] builder prints 'decoder max loop=114' at k=20;
        the printed cycle list runs 36..114 in +6/+2 steps => 4k + 34.  [D]"""
        return 4 * self.cells_per_bank + 34

    @property
    def realign_workers(self) -> int:
        """Workers needed to absorb one reply every target_ticks.  [S] verify_decoder():
        max(cycle) <= COLS*ROWS*8.  k=20 -> 15 needed; the champion ships 16 (a 4x4 grid)."""
        t = self.target_ticks
        return -(-self.realign_worker_loop // t)

    @property
    def realign_grid(self) -> tuple[int, int]:
        """(rows, cols) of 18x5 realigner tiles.  Auto-picks the shape that minimises
        max(width, height) of the whole component."""
        if self.realign_rows and self.realign_cols:
            return self.realign_rows, self.realign_cols
        need = self.realign_workers
        best = None
        for cols in range(1, need + 1):
            rows = -(-need // cols)
            h = self._height_for(rows)
            w = self._width_for(cols)
            key = (max(w, h), h, w)
            if best is None or key < best[0]:
                best = (key, (rows, cols))
        return best[1]

    # ---- footprint ------------------------------------------------------
    def _height_for(self, realign_rows: int) -> int:
        # bank region outer height = interior (3k + 13 + pad) + 2 walls
        k = self.cells_per_bank
        bank_region = BANK_TOP + CELL_ROWS * k + 15 + self.ring_pad_rows
        if not self.realign:
            return bank_region
        return bank_region + REALIGN_TILE_H * realign_rows + 2

    def _width_for(self, realign_cols: int) -> int:
        w = max(PITCH * self.banks, self.front_end_width)
        if self.realign:
            w = max(w, REALIGN_TILE_W * realign_cols + REALIGN_SLACK_W)
        return w

    @property
    def height(self) -> int:
        rows, _ = self.realign_grid if self.realign else (0, 0)
        return self._height_for(rows)

    @property
    def width(self) -> int:
        _, cols = self.realign_grid if self.realign else (0, 0)
        return self._width_for(cols)

    @property
    def box(self) -> int:
        return max(self.width, self.height) ** 2

    @property
    def men(self) -> int:
        """Live man census at steady state.  [M] champion under load = 231."""
        cells = self.cells_per_bank * self.banks
        decode = self.ring_workers * self.banks
        rows, cols = self.realign_grid if self.realign else (0, 0)
        realign = rows * cols
        front = 7 + 3  # [M] front-end chain 7 + fanout 3
        return cells + decode + realign + front

    # ---- pin coordinates (relative to the component's own (0,0)) --------
    def pins(self, x: int = 0, y: int = 0) -> Pins:
        """Where a caller's pipes attach.  Command enters the front end's top-right;
        reply leaves the realigner's east wall (or, with realign=False, the bank reply
        pipes are exposed individually at the bottom of each gutter)."""
        return Pins(
            command=(x + self.front_end_width - 2, y + 2),
            reply=(x + self.width - 2, y + self.height - REALIGN_TILE_H * self.realign_grid[0] - 1)
            if self.realign else (x + 9, y + self._height_for(0) - 2),
            reply_turn=(x + self.width - 1,
                        y + self.height - REALIGN_TILE_H * self.realign_grid[0] - 1)
            if self.realign else (x + 10, y + self._height_for(0) - 2),
        )

    # ---- word encoding --------------------------------------------------
    def encode_write(self, value: int, addr: int) -> int:
        """The single i64 the cell man receives.  Always > 0."""
        k = self.cells_per_bank
        return k * (value + BIAS) - 1 - (addr % k)

    def encode_read(self, addr: int) -> int:
        """Always < 0, so the cell's `X` needs no comparison -- sign IS the opcode."""
        k = self.cells_per_bank
        return -(k * BIAS) - 1 - (addr % k)

    def decode_reply(self, word: int) -> tuple[int, int]:
        """(value, local_id).  The reply self-identifies: this is why out-of-order
        replies are recoverable and why the realigner is optional."""
        k = self.cells_per_bank
        return word // k - (BIAS - 1), k - 1 - (word % k)


# =============================================================================
# 2. TICK-ACCURATE COST MODEL
# =============================================================================
#
# THREE DIFFERENT NUMBERS.  Confusing them is the single biggest porting risk.
#
#   ISSUE INTERVAL  (throughput)  = 8 ticks.  What you pay per op if you can keep
#                                   requests in flight without waiting for replies.
#   ROUND-TRIP LATENCY            = 4k + 57 ticks (137 at k=20).  What you pay per op
#                                   if you must see the value before issuing the next
#                                   request -- i.e. Pathfinder's BFS inner loop.
#   STARTUP                       = 205 ticks on the champion; ring_period + ~37 for the core.
#
# All three are ADDRESS-INDEPENDENT on the champion.  [M]

FRONT_END_LATENCY_MEMORY = 76      # [M] 213 (single-read settle) - 137 (traced core)
CORE_LATENCY_CONST = 61            # [D] 137 - 4*(20-1); rests on ONE traced k
RAW_LATENCY_CONST = 31             # [M] reply enters the bank->realigner pipe at 31+4*offset
STARVED_WORKERS_PER_BANK = 7       # [M] see starvation() below


def cost(size: int, banks: int, addr: int, *, realign: bool = True,
         dependent: bool = False, warm: bool = True,
         front_end_latency: int = FRONT_END_LATENCY_MEMORY) -> dict:
    """Ticks for ONE random access at `addr`.

    dependent=False  -> streaming/decoupled caller: returns the issue interval.
    dependent=True   -> caller blocks on the reply: returns the full round trip.
    warm=False       -> the rings have been starved and lost workers (see starvation()).
    """
    k, l = _split(size, banks)
    ram = FastRam(size=size, banks=l, cells_per_bank=k, realign=realign)
    offset = addr % k

    if not dependent:
        interval = ram.target_ticks
        if not warm:
            interval = ram.ring_period // STARVED_WORKERS_PER_BANK
        return {"ticks": interval, "kind": "issue-interval",
                "issue_interval": interval, "warm": warm}

    if realign:
        core = 4 * (k - 1) + CORE_LATENCY_CONST      # constant in addr, by construction
    else:
        core = RAW_LATENCY_CONST + 4 * offset        # exposed skew, addr-dependent
    return {"ticks": core + front_end_latency, "kind": "round-trip",
            "core": core, "front_end": front_end_latency, "offset": offset,
            "issue_interval": ram.target_ticks, "warm": warm}


def startup(size: int, banks: int, *, memory_front_end: bool = True) -> int:
    """Ticks before the first reply can appear.  [M] 205 on the champion (k=20,l=5)."""
    k, l = _split(size, banks)
    ram = FastRam(size=size, banks=l, cells_per_bank=k)
    if memory_front_end and (k, l) == (20, 5):
        return 205                                    # [M] exact
    return ram.ring_period + 37                       # [D] fill the ring + parse/decode latency


def stream_ticks(size: int, banks: int, ops_through_last_read: int, **kw) -> int:
    """Total settleTick for a stream.  [M] EXACT on the champion for every input tried."""
    return startup(size, banks, **kw) + CELL_SERVICE_TICKS * ops_through_last_read


def starvation(size: int, banks: int) -> dict:
    """What happens when the request stream goes idle.  ALL MEASURED on the champion.

    A fully-populated machine (21 decode workers/bank at t=600) collapses to 7 within one
    ring period of the input draining, and NEVER RECOVERS -- the spawner has already halted.
    Front-end chain 7 -> 3 men, fanout 3 -> 1 man.  Population 231 -> 155, stable to t=5000.

    Mechanism: a ring worker walking into a leader parked on `r` kills both
    (docs/multi-man-interactions.md; PROBLEM.md 'movement into a blocked man').
    """
    k, l = _split(size, banks)
    ram = FastRam(size=size, banks=l, cells_per_bank=k)
    return {
        "warm_workers_per_bank": ram.ring_workers,       # [M] 21
        "starved_workers_per_bank": STARVED_WORKERS_PER_BANK,  # [M] 7
        "warm_interval": ram.target_ticks,               # [M] 8
        "starved_interval": ram.ring_period // STARVED_WORKERS_PER_BANK,  # [D] 168//7 = 24
        "onset_ticks": ram.ring_period,                  # [M] complete within ~1 ring period
        "recovers": False,                               # [M] flat at 155 men out to t=5000
    }


def _split(size: int, banks: int) -> tuple[int, int]:
    k = -(-size // banks)
    if k % 2:
        k += 1
    return k, banks


# =============================================================================
# 3. VALIDATION AGAINST THE MEASURED CHAMPION
# =============================================================================

# [M] Every one of these was produced by
#     interp/target/release/lm --grade champion-6abc7461.man --input=.. --expected=..
MEASURED_SINGLE_READ_SETTLE = {a: 213 for a in
                               (0, 1, 2, 5, 19, 20, 21, 40, 60, 80, 94, 99)}
MEASURED_N_READS = {1: 213, 2: 221, 3: 229, 4: 237, 8: 269, 16: 333,
                    32: 461, 64: 717, 128: 1229, 256: 2253}
MEASURED_MIXED = {52: 621, 59: 677, 66: 733, 62: 701, 85: 885, 18: 349}
MEASURED_PUBLIC_CASES = {  # [M] tools/grade_fast.py memory champion-6abc7461.man -> 7/7
    "fresh cell reads zero": (1, 213), "write then read": (2, 221),
    "overwrite": (5, 245), "boundary addresses and values": (5, 245),
    "write zero, trailing write": (5, 245), "reads only": (5, 245),
    "interleaved cells": (125, 1205)}
MEASURED_CHAMPION_BOX = (108, 108, 11664)
MEASURED_CHAMPION_MEN = 231
MEASURED_RING_PERIOD_K20 = 168
MEASURED_RING_WORKERS_K20 = 21


def validate(verbose: bool = True) -> bool:
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        if verbose:
            print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")
        return good

    if verbose:
        print("--- ring timing (k=20) ---")
    champ = FastRam(size=100, banks=5, cells_per_bank=20, realign=True,
                    front_end_width=FRONT_END_W_MEMORY)
    check("ring_period", champ.ring_period, MEASURED_RING_PERIOD_K20)
    check("ring_workers", champ.ring_workers, MEASURED_RING_WORKERS_K20)
    check("realign_workers <= shipped 16", champ.realign_workers <= 16, True)
    check("realign_worker_loop", champ.realign_worker_loop, 114)  # builder prints 114

    if verbose:
        print("--- footprint ---")
    champ44 = FastRam(size=100, banks=5, cells_per_bank=20, realign=True,
                      realign_rows=4, realign_cols=4,
                      front_end_width=FRONT_END_W_MEMORY)
    check("champion height", champ44.height, MEASURED_CHAMPION_BOX[1])
    check("champion width", champ44.width, MEASURED_CHAMPION_BOX[0])
    check("champion box", champ44.box, MEASURED_CHAMPION_BOX[2])
    check("champion men", champ44.men, MEASURED_CHAMPION_MEN)

    if verbose:
        print("--- stream cost law: settle = 205 + 8*n ---")
    for n, want in MEASURED_N_READS.items():
        check(f"{n} reads", stream_ticks(100, 5, n), want)
    for n, want in MEASURED_MIXED.items():
        check(f"mixed {n} ops", stream_ticks(100, 5, n), want)
    for name, (n, want) in MEASURED_PUBLIC_CASES.items():
        check(f"public '{name}'", stream_ticks(100, 5, n), want)

    if verbose:
        print("--- address independence ---")
    ticks = {a: cost(100, 5, a, dependent=True)["ticks"]
             for a in MEASURED_SINGLE_READ_SETTLE}
    check("all addresses same round trip", len(set(ticks.values())), 1)
    check("round trip = 137 core + 76 front", cost(100, 5, 99, dependent=True)["ticks"], 213)
    check("issue interval", cost(100, 5, 99)["ticks"], 8)

    if verbose:
        print("--- word encoding round-trips ---")
    for addr in (0, 7, 19, 20, 55, 99):
        for v in (-10 ** 6, -1, 0, 1, 42, 10 ** 6):
            w = champ.encode_write(v, addr)
            got_v, got_id = champ.decode_reply(w)
            check(f"enc/dec addr={addr} v={v}", (got_v, got_id), (v, addr % 20))
            check(f"write word positive addr={addr} v={v}", w > 0, True)
        check(f"read word negative addr={addr}", champ.encode_read(addr) < 0, True)
    # [M] traced values from the champion
    check("write 42 -> addr 7 word", champ.encode_write(42, 7), 47186752)
    check("read addr 7 word", champ.encode_read(7), -47185928)

    if verbose:
        print("--- starvation (measured) ---")
    s = starvation(100, 5)
    check("warm workers", s["warm_workers_per_bank"], 21)
    check("starved workers", s["starved_workers_per_bank"], 7)
    check("starved interval", s["starved_interval"], 24)
    check("starved cost()", cost(100, 5, 0, warm=False)["ticks"], 24)

    if verbose:
        print("\nVALIDATION:", "ALL PASS" if ok else "FAILURES ABOVE")
    return ok


# =============================================================================
# 4. GEOMETRY SEARCH
# =============================================================================

def best_geometry(size: int, *, realign: bool, front_end_width: int = FRONT_END_W_REUSABLE,
                  max_banks: int = 10) -> FastRam:
    """score = max(w,h)^2 * avgTicks, and avgTicks is 8 for EVERY legal (k,l).
    So this is purely 'minimise the longer side'."""
    best = None
    for l in range(1, max_banks + 1):
        for k in range(2, 4 * size + 2, 2):
            if k * l < size:
                continue
            if k * l > size + 2 * k:          # don't over-provision by more than a bank
                continue
            r = FastRam(size=size, banks=l, cells_per_bank=k, realign=realign,
                        front_end_width=front_end_width)
            if r.problems():
                continue
            key = (max(r.width, r.height), r.width * r.height, k * l)
            if best is None or key < best[0]:
                best = (key, r)
    return best[1] if best else None


TARGET_SIZES = [(30, "LLLM registers"), (32, "pathfinder + LLM scalar"),
                (100, "memory"), (256, "LLLM program store"),
                (288, "pathfinder cell RAM")]


def geometry_table(front_end_width: int = FRONT_END_W_REUSABLE) -> str:
    rows = []
    hdr = (f"{'size':>5} {'use':<24} {'mode':<12} {'banks':>5} {'k':>4} "
           f"{'w':>4} {'h':>4} {'box':>7} {'men':>5} {'issue':>5} {'dep':>9} {'boot':>5}")
    rows.append(hdr)
    rows.append("-" * len(hdr))
    for size, use in TARGET_SIZES:
        for realign, label in ((True, "in-order"), (False, "out-of-order")):
            r = best_geometry(size, realign=realign, front_end_width=front_end_width)
            if r is None:
                rows.append(f"{size:>5} {use:<24} {label:<12} -- infeasible --")
                continue
            lo = cost(size, r.banks, 0, realign=realign,
                      dependent=True, front_end_latency=0)["ticks"]
            hi = cost(size, r.banks, r.cells_per_bank - 1, realign=realign,
                      dependent=True, front_end_latency=0)["ticks"]
            dep = f"{lo}" if lo == hi else f"{lo}-{hi}"
            rows.append(f"{size:>5} {use:<24} {label:<12} {r.banks:>5} {r.cells_per_bank:>4} "
                        f"{r.width:>4} {r.height:>4} {max(r.width,r.height)**2:>7} "
                        f"{r.men:>5} {r.target_ticks:>5} {dep:>9} "
                        f"{r.ring_period + 37:>5}")
        rows.append("")
    champ = FastRam(size=100, banks=5, cells_per_bank=20, realign=True,
                    realign_rows=4, realign_cols=4, front_end_width=FRONT_END_W_MEMORY)
    rows.append(f"{'100':>5} {'(the SHIPPED champion)':<24} {'in-order':<12} "
                f"{champ.banks:>5} {champ.cells_per_bank:>4} {champ.width:>4} "
                f"{champ.height:>4} {champ.box:>7} {champ.men:>5} {8:>5} {137:>9} {205:>5}")
    rows.append("")
    rows.append("SENSITIVITY: at sizes 30/32 the long side is 51 (banks) vs "
                f"{front_end_width} (front end) -- essentially tied.  A front end wider than")
    rows.append("~55 columns starts driving the box for the small instances; fold it "
                "vertically there.  At 100/256/288 the")
    rows.append("bank pitch dominates and the front-end width is free.")
    return "\n".join(rows)


EXPLAIN = """
DERIVATION OF EVERY CONSTANT
============================

RING PERIOD.  [S] direct_memory.py:178  unpadded_worker_ticks = 26 + 7k.  Blank rows are
added (2 ticks each) until the loop divides target_ticks: k=20 -> 166, +2 -> 168, /8 -> 21
workers.  [M] Confirmed on the champion: a tagged man re-enters the ring head at
t = 253, 421, 589, 757 (168 apart) and the live decode population is exactly 21 per bank.

WHY 8.  Three independent rate limiters all equal 8 and none can go lower today:
  * cell service loop = 8 ticks (both the READ and the WRITE lobe of the 6x3 storage tile);
  * decode ring 168/21 = 8;
  * fanout room 24 ticks / 3 men = 8.
The cell loop is the hard floor.  Its tile has 18 cells and the loop uses 8, so a 6-tick
loop may be geometrically possible -- but the store commits on the LAST tick of the lap, so
a 6-tick interval would have to be re-checked against write-then-read on the same address.
NOT ATTEMPTED HERE.

HEIGHT.  H = 3k + 28 + 5*realign_rows.  [M] k=20, rows=4 -> 108, the champion's exact height.
Components: BANK_TOP 10 (front end 5 + fanout 5), decode column interior 3k+13+pad, walls 2,
gap 2, realigner 5*rows + 2.

WIDTH.  W = max(17*l, 18*cols + 10, front_end_width).  17 is fixed by the builder's
fixed-width interior strings (5 + 2 gutter + 6 + 4 walls).  [M] the champion's banks sit at
x = 0, 17, 34, 51, 68 and its bank region spans x=0..84 = 17*5.

ROUND-TRIP LATENCY.  [M] the traced request->reply path through the champion is 137 ticks
for EVERY address; the decode staircase costs 4*offset and the realigner adds exactly
4*(k-1-offset) back.  So core = 4*(k-1) + 61.  THE 61 IS FITTED FROM ONE k.  If you build a
second k, re-fit it before trusting the number.
Drop the realigner and the skew is exposed: core = 31 + 4*offset  [M, offsets 0..19].

STARTUP.  [M] 205 on the champion = ring fill (168) + parse/decode latency (~37).

IDZERO -- A REAL BUG IN direct_memory.py, MEASURED
--------------------------------------------------
direct_memory.py numbers cells 0..k-1 and gives local id 0 a special-case detour.  I built
`python3 direct_memory.py --k 20 --l 5` and graded it: it passes 7/7 public (box 19321,
avgTicks 373.1) but

    128 reads of addr 0   -> CRASH at tick 644
    128 reads of addr 20  -> CRASH at tick 351   (also 40, 60, 80: every addr = 0 mod 20)
    128 reads of addr 1   -> pass, settle 1240
    128 reads of addr 19  -> pass, settle 1228

and its latency is NOT de-skewed (single read: addr 0 -> 227, addr 1 -> 224, addr 2 -> 223,
addr 19 -> 212).  The champion's extra "payload -= 1" room makes ids 1..k, which deletes the
id-0 detour and restores address independence (all 12 addresses -> 213).
=> tools/fast_ram.py MUST use 1-BASED CELL IDS.  This is not cosmetic.

THE OTHER TWO HARD LOCKS IN THE BUILDER
---------------------------------------
  direct_memory.py:849  raise unless k == 20 and worker_count == 21   <- blocks every other size
  direct_memory.py:171  bank id must be one digit                     <- blocks l > 10
Both are the real work in writing tools/fast_ram.py.  The realigner tile geometry is NOT
k-dependent (the delay is a loop, 4 ticks per BP unit, on a fixed 18x5 tile); only the
NUMBER of realigner workers scales, as ceil((4k+34)/8).  That is much better news than the
decode brief assumed.

FREE WIN FOR THE MEMORY PROBLEM ITSELF
--------------------------------------
The champion ships a 4x4 realigner but only needs ceil(114/8) = 15 workers.  A 3x5 grid gives
H = 3*20 + 28 + 15 = 103 and W = max(85, 18*5+10, front) = 100 if the front end is folded
under 100 wide.  Box 10609 vs 11664 = -9% score for zero logic risk.  UNBUILT, UNVERIFIED.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--front-end-width", type=int, default=FRONT_END_W_REUSABLE)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    ok = validate(verbose=not a.quiet)
    print()
    print("RECOMMENDED GEOMETRY  (score = max(w,h)^2 * ticks; ticks/op = 8 for every legal "
          "(k,l), so this minimises the long side)")
    print("  'issue' = pipelined ticks/op.  'dep' = ticks a BLOCKING caller pays per access, "
          "excluding the front end.")
    print()
    print(geometry_table(a.front_end_width))
    if a.explain:
        print(EXPLAIN)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
