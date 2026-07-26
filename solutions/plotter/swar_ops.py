#!/usr/bin/env python3
"""Plotter: verified SWAR inner loop + per-round constants for a rebuild.

WHY THIS EXISTS
  The live build (plotter-tight31-polished.man, 79x79, server 258,415,158) spends
  ~187 executed ops per plotted pixel because all state lives on a 7-slot pipe
  "belt" and every access pays rotations.  ~320 ticks/pixel, ~6,400 ticks/round.
  The board leader is 3,487,941 (74x better).  Folding cannot close that: the
  inner loop has to stop touching a belt.

THE LEVER
  Littleman's binary ops (+ - * % & | ~ { } and N) leave B UNCHANGED.  So a value
  parked in B is a free operand for an unlimited number of 1-op updates.  Two
  registers per man is not enough for Bresenham (needs err, addr, dx, dy, steps),
  BUT the whole loop collapses to ONE register + ONE constant if the accumulator
  and the address are packed into a single i64 and the carry test is a sign test.

PACKING (verified pixel-exact on all 32*24*32*24 = 589,824 segments)
    P = f * 1024 + addr           addr in [0,768) so it never disturbs f
    f = 2*(acc - 2L) + 1          odd => f != 0 => sign(P) == sign(f), a clean flag
  per pixel:   send addr(P) ; P += Ic ; if P > 0: P += Jc
    Ic = 4096*S + majd           Jc = -4096*L + mind
    L = max(|dx|,|dy|)  S = min(|dx|,|dy|)
    majd/mind = (sx, 32*sy) if |dx| >= |dy| else (32*sy, sx)
    P0 = 1024*f0 + 32*y0 + x0    f0 = 1 - 2*max(L,1)      cnt = L+1
  Use Q = -P instead if the man's loop ring must turn clockwise on the common
  (no-carry) branch: Q > 0 <=> no carry;  IcQ = -Ic, JcQ = -Jc, Q0 = -P0.
  Only 2 registers are ever needed by the pixel loop: A = P, B = Ic.
  => 3 ops per pixel of real work (send, add, test) instead of ~187.

RING LAYOUTS (a man's loop costs one tick per cell, so turns must do work)
  `d`/`a` turn iff BP>0 and `X` turns on sign(A): both are *turns that also test*,
  so they belong at ring corners.  A rectangular ring of perimeter p has exactly
  4 corners, so a ring can host at most 2 pixels' worth of (test + counter) work.
  Derived assignment for a 4x4 ring (12 cells, 2 pixels/lap, 6 ticks/pixel),
  clockwise, per-pixel op order  X, s, m, d, +  (+1 direction filler):
     (0,0)=d  (1,0)=+  (2,0)=>  (3,0)=X        <- top row, heading E
     (3,1)=s  (3,2)=m  (3,3)=d                 <- right column, heading S
     (2,3)=+  (1,3)=<  (0,3)=X                 <- bottom row, heading W
     (0,2)=s  (0,1)=m                          <- left column, heading N
  The two `>`/`<` filler cells are the ONLY cells a man can enter from outside in
  a well-defined heading (direction glyphs are absolute; every other op derives
  its outgoing heading from the incoming one, so its predecessor is always a ring
  cell).  Enter at (2,0) from the north with A = Q0: the following `X` sees
  Q0 > 0 (guaranteed by f0 < 0) and falls straight through to the first send.
  `X`'s minority branch leaves the ring for a 4-cell detour that sends P to the
  carry-correction man and reads P+Jc back, re-entering at the same filler cell.
  A counterclockwise ring is the mirror image with `a` for `d`; use it when the
  man must hold P (not Q), which saves the consumer an `N`.

CONSUMER SIDE
  The display validates colour strictly: sending 1023 as "15 mod 16" is a
  `display-value` crash (probed on the oracle), so DATA must be exactly 15 and a
  4-cell backtick literal or a dedicated B=15 man is unavoidable.
  One man can do the whole display side in 8 ops/pixel with B = 1024 parked:
      r ; % (A = P mod 1024 = addr, B survives) ; s->ADDR ; `15` ; s->DATA
  Splitting ADDR and DATA across two men is faster (4+4 ops) but then ADDR_{k+1}
  can overtake DATA_k at the display; keeping both sends in ONE man makes the
  order a program-order guarantee.  General rule for this pipeline: every
  downstream ring must be strictly shorter than the upstream cadence so each man
  parks on its blocking `r` and all latencies stay deterministic.

SUGGESTED TOPOLOGY (5 rooms + display, 8 pipes, ~40x40 box)
  IN -> BRAIN -> MAIN -> BRAIN -> PLOT -> display(ADDR, DATA); BRAIN -> SWAP
  MAIN (setup + carry correction) then has exactly one incoming and one outgoing
  pipe, so every r/s in its serpentine is pipe-unambiguous, and BRAIN's unrolled
  `r;s` echo corridor doubles as MAIN's FIFO scratch (3-tick round trip) - no
  extra relay room.  MAIN ends each round with `b` (BP := S = the exact number of
  carries) and B := Jc, then walks into the correction ring and back to the top.
  Modelled cost: setup ~100-160 t, plot 10 t/pixel, drain ~15 t  =>  ~320 t/round
  => avgTicks ~1,100 local, ~1,650 server, box 1,600-1,936  =>  2.6-3.2M.
"""

def consts(x0, y0, x1, y1, negate=False):
    """Per-round constants for the packed loop. negate=True returns the Q form."""
    DX, DY = x1 - x0, y1 - y0
    adx, ady = abs(DX), abs(DY)
    sx = 1 if DX > 0 else -1
    sy = 1 if DY > 0 else -1
    if adx >= ady:
        L, S, majd, mind = adx, ady, sx, 32 * sy
    else:
        L, S, majd, mind = ady, adx, 32 * sy, sx
    Ic = 4096 * S + majd
    Jc = -4096 * L + mind
    P0 = 1024 * (1 - 2 * max(L, 1)) + (32 * y0 + x0)
    out = (P0, Ic, Jc, L + 1, S)
    if negate:
        out = (-P0, -Ic, -Jc, L + 1, S)
    return out


def pixels(x0, y0, x1, y1):
    """Run the packed loop exactly as the grid will; returns the address list."""
    P, Ic, Jc, cnt, _ = consts(x0, y0, x1, y1)
    out = []
    for i in range(cnt):
        out.append(P & 1023)
        if i == cnt - 1:
            break
        P += Ic
        if P > 0:
            P += Jc
    return out


def reference(x0, y0, x1, y1):
    """The assignment's Bresenham, symmetric error form, as addresses."""
    dx = abs(x1 - x0); dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1
    err = dx + dy; out = []
    while True:
        out.append(32 * y0 + x0)
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy


if __name__ == "__main__":
    bad = n = 0
    for x0 in range(32):
        for y0 in range(24):
            for x1 in range(32):
                for y1 in range(24):
                    n += 1
                    if pixels(x0, y0, x1, y1) != reference(x0, y0, x1, y1):
                        bad += 1
                        if bad < 4:
                            print("MISMATCH", x0, y0, x1, y1)
    print(f"checked {n} segments, {bad} mismatches")
