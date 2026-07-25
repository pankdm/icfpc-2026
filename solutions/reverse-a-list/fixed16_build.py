#!/usr/bin/env python3
"""Coordinate-based builder for the fixed-16 reverse-a-list machine (littleman).

NO HAND-LAYOUT: every glyph/room/pipe is placed by coordinate through a Grid
that collision-checks. Design (validated in fixed16_model / pad-first fuzz):

  C = 1<<21 = 2097152   (> max|value|=1e6, so every biased real is > 0)

  READER (1 man, 1 incoming pipe I, 1 outgoing pipe SEQ) -- NO holder:
     r  A=n
     M  B=n
     `16` -  A = 16-n           (pad count; B still = n)
     b  BP = 16-n
     PAD LOOP (test-first): emit (16-n) zeros to SEQ   [touches only A,BP; B kept = n]
     W  A=n, B=0                (recover n)
     b  BP = n
     `2097152` M  B = C         (bias)
     READ LOOP (test-first): r + s  -> emit n biased reals to SEQ
     -> round return corridor -> back to the read of n (blocks until next round)
     Stream E = [0]*(16-n) + [v0+C .. v_{n-1}+C]   (pad first)

  SEQUENCER (1 man, 1 incoming SEQ, 16 outgoing lanes): branchless snake,
     for k=0..15: r (from SEQ) ; walk to column k ; s (to lane k)

  WRITER (1 man, 16 incoming lanes, 1 outgoing O): read lane15..lane0,
     X-test A>0 -> real: A-=C, print ; else padding 0 -> skip.  loop for rounds.

Build stages selectable on argv[1]: 'reader' | 'full'.
"""
import sys

C = 2097152


class Grid:
    def __init__(self):
        self.g = {}          # (x,y) -> ch
        self.maxx = self.maxy = 0

    def put(self, x, y, ch, allow_same=True):
        assert x >= 0 and y >= 0, (x, y)
        old = self.g.get((x, y), ' ')
        if old != ' ' and old != ch:
            raise AssertionError(f"collision at ({x},{y}): '{old}' vs '{ch}'")
        self.g[(x, y)] = ch
        self.maxx = max(self.maxx, x)
        self.maxy = max(self.maxy, y)

    def text(self, x, y, s):
        for i, ch in enumerate(s):
            self.put(x + i, y, ch)

    def vtext(self, x, y, s):
        for i, ch in enumerate(s):
            self.put(x, y + i, ch)

    def room(self, x0, y0, x1, y1):
        self.put(x0, y0, '+'); self.put(x1, y0, '+')
        self.put(x0, y1, '+'); self.put(x1, y1, '+')
        for x in range(x0 + 1, x1):
            self.put(x, y0, '-'); self.put(x, y1, '-')
        for y in range(y0 + 1, y1):
            self.put(x0, y, '|'); self.put(x1, y, '|')

    def render(self):
        rows = []
        for y in range(self.maxy + 1):
            row = ''.join(self.g.get((x, y), ' ') for x in range(self.maxx + 1))
            rows.append(row.rstrip())
        return '\n'.join(rows) + '\n'


# ----- literal helpers (HORIZONTAL only) -----
def lit(n):
    return '`' + str(n) + '`'


def build_reader(gr, x0, y0, out_to_O=True, ack=False):
    """Reader room with top-left interior origin near (x0,y0). Returns dict of
    key attach points. If out_to_O, add an O room fed by the SEQ pipe (stage a).
    If ack, add an ACK incoming pipe (from writer) read once per round in the
    return corridor -> serializes rounds (reader won't emit next round until the
    writer has drained the current one)."""
    # We lay the spine row (S) and gadget bodies below it, plus a cold return
    # corridor. Coordinates are chosen generously; fold later.
    # Interior spine row:
    S = y0 + 1
    # Build the spine left-to-right with a cursor.
    x = x0 + 2                     # leave col x0(=wall) ; col x0+1 = return-rail '>'
    # return rail: '>' at x0+1 pushing man east into the setup
    # setup: @ r M `16` -  b
    setup = '@rM' + lit(16) + '-b'
    self_start_x = x
    gr.text(x, S, setup); x += len(setup)
    # '>' (pad up-path rejoin + force E) then padT 'd'
    padG = x                       # '>' col
    gr.put(padG, S, '>'); x += 1
    padT = x                       # 'd' col
    gr.put(padT, S, 'd'); x += 1
    # segment2 after pad exit: W b `2097152` M
    seg2 = 'W' + 'b' + lit(C) + 'M'
    gr.text(x, S, seg2); x += len(seg2)
    # '>' (read up-path rejoin) then readT 'd'
    readG = x
    gr.put(readG, S, '>'); x += 1
    readT = x
    gr.put(readT, S, 'd'); x += 1
    exit_x = x                     # cell east of readT: read-loop exit lands here

    # ---- pad gadget body (down col padT, up col padG) ----
    # rows S+1..S+3
    gr.put(padT, S + 1, '0')
    gr.put(padT, S + 2, 's')
    gr.put(padT, S + 3, '<')
    gr.put(padG, S + 3, '^')
    gr.put(padG, S + 2, 'm')
    gr.put(padG, S + 1, '.')

    # ---- read gadget body (down col readT, up col readG) ----
    gr.put(readT, S + 1, 'r')
    gr.put(readT, S + 2, '+')
    gr.put(readT, S + 3, 's')
    gr.put(readT, S + 4, '<')
    gr.put(readG, S + 4, '^')
    gr.put(readG, S + 3, 'm')
    gr.put(readG, S + 2, '.')
    gr.put(readG, S + 1, '.')

    # ---- cold round-return corridor ----
    # From exit_x,S go east to a turn, down to a bottom row, west, up to the
    # left return rail, east into @.
    bottom = S + 6                 # bottom corridor row (below deepest gadget S+4)
    right = exit_x + 1             # small east margin then turn down
    gr.put(exit_x, S, '>')         # keep going east (nop-ish, force E)
    gr.put(right, S, 'v')          # turn south
    down_n = (bottom - S - 2) if ack else (bottom - S - 1)
    gr.vtext(right, S + 1, 'v' * down_n)
    if ack:
        gr.put(right, bottom - 1, 'r')   # ACK-read (blocks until writer drains)
    gr.put(right, bottom, '<')     # turn west
    left = x0 + 1                  # return-rail column
    for cx in range(left + 1, right):
        gr.put(cx, bottom, '<')
    gr.put(left, bottom, '^')      # turn north at left col
    for cy in range(S + 1, bottom):
        gr.put(left, cy, '^')
    gr.put(left, S, '>')           # at spine, face east -> travels to @
    # fill spine between left+1 and setup start with '>' rail
    for cx in range(left + 1, self_start_x):
        gr.put(cx, S, '>')

    # ---- room walls ----
    rx0, ry0 = x0, y0
    rx1, ry1 = right + 1, bottom + 1
    gr.room(rx0, ry0, rx1, ry1)

    # ---- I room + input pipe into reader top wall ----
    # I room above, its outgoing pipe drops onto reader top wall above the read
    # gadget's 'r' column so the reader's r reads from I (only incoming pipe).
    ipipe_x = readT               # attach column on reader top wall
    # pipe cells occupy cells ABOVE the wall; the wall stays '-'.
    gr.put(ipipe_x, ry0 - 1, 'v')
    gr.put(ipipe_x, ry0 - 2, 'v')
    # I room (3x3) above the pipe
    iy1 = ry0 - 3
    iy0 = iy1 - 2
    gr.room(ipipe_x - 1, iy0, ipipe_x + 1, iy1)
    gr.put(ipipe_x, iy0 + 1, 'I')

    attaches = dict(seq_bottom_row=ry1, room_x0=rx0, room_x1=rx1, room_y1=ry1,
                    padT=padT, readT=readT, ack_x=right, ack_bottom=ry1)

    # ---- SEQ outgoing pipe: exits reader bottom wall. For stage a, -> O. ----
    # place SEQ attach on bottom wall under the pad 's' / read 's' columns? The
    # reader's 's' cells (padT col row S+2, readT col row S+3) send to nearest
    # outgoing = SEQ. SEQ attach column: put under readT.
    seq_x = 2                     # bottom-wall attach column for SEQ (non-lane col)
    gr.put(seq_x, ry1 + 1, 'v')   # pipe cells below the wall (wall stays '-')
    gr.put(seq_x, ry1 + 2, 'v')
    if out_to_O:
        oy0 = ry1 + 3
        gr.room(seq_x - 1, oy0, seq_x + 1, oy0 + 2)
        gr.put(seq_x, oy0 + 1, 'O')
    attaches['seq_x'] = seq_x
    return attaches


def build(stage):
    gr = Grid()
    if stage == 'reader':
        build_reader(gr, 0, 6, out_to_O=True)
    else:
        raise SystemExit('only reader stage implemented so far')
    return gr.render()


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'reader'
    out = sys.argv[2] if len(sys.argv) > 2 else None
    txt = build(stage)
    if out:
        open(out, 'w').write(txt)
    for i, l in enumerate(txt.rstrip('\n').split('\n')):
        print(f'{i:2d}|{l}')


def build_writer_micro(gr):
    """Micro-test the writer's X-process loop: I -> one pipe -> writer reads 16
    via `r`, debias reals (A>0), skip pads (A==0), print to O. Validates the
    branch/debias/counter before wiring 16 lanes."""
    # writer man at origin
    wy = 10
    wx = 2
    # setup row: @ `2097152` M `16` b  > (B=C, BP=16, face E)
    s = '@' + lit(C) + 'M' + lit(16) + 'b'
    gr.text(wx, wy, s)
    entryx = wx + len(s)         # '>' entry to loop, faces E
    gr.put(entryx, wy, '>')
    # loop cells on row LY = wy (continue east)
    cAm = entryx                 # '>' entry (cA-1)
    cA = cAm + 1                 # 'r'
    cB = cA + 1                  # 'X'
    cC = cB + 1                  # pad down 'v'
    cD = cC + 1                  # 'm'
    ry = wy
    gr.put(cA, ry, 'r')
    gr.put(cB, ry, 'X')
    gr.put(cC, ry, 'v')          # pad path (X straight = east into 'v')
    # real path (X CW from E -> S)
    gr.put(cB, ry + 1, '-')
    gr.put(cB, ry + 2, 's')
    gr.put(cB, ry + 3, '>')
    # pad path down col cC
    gr.put(cC, ry + 1, 'v')
    gr.put(cC, ry + 2, 'v')
    gr.put(cC, ry + 3, '>')      # both paths exit east
    # counter
    gr.put(cD, ry + 3, 'm')
    gr.put(cD + 1, ry + 3, 'a')  # BP>0 -> CCW -> N loopback ; else E exit
    # loopback up col cD+1 to ry-1
    for yy in range(ry - 1, ry + 3):
        gr.put(cD + 1, yy, '<' if yy == ry - 1 else '^')
    # west along ry-1 rail to cAm
    for xx in range(cAm + 1, cD + 1):
        gr.put(xx, ry - 1, '<')
    gr.put(cAm, ry - 1, 'v')     # turn south into '>' entry
    gr.put(cAm, ry, '>')
    # exit (BP==0) at (cD+2, ry+3)
    gr.put(cD + 2, ry + 3, 'H')

    # room walls around everything
    rx0 = wx - 2
    ry0 = ry - 3
    rx1 = cD + 4
    ry1 = ry + 5
    gr.room(rx0, ry0, rx1, ry1)

    # ---- input pipe: I room above, pipe down into writer top wall near 'r' ----
    ipx = cA                     # attach above the 'r' cell column
    gr.put(ipx, ry0 - 1, 'v')
    gr.put(ipx, ry0 - 2, 'v')
    iy1 = ry0 - 3
    gr.room(ipx - 1, iy1 - 2, ipx + 1, iy1)
    gr.put(ipx, iy1 - 1, 'I')

    # ---- O pipe: writer sends to O (only outgoing). attach at bottom wall. ----
    opx = cB                     # under the 's' column
    gr.put(opx, ry1 + 1, 'v')
    gr.put(opx, ry1 + 2, 'v')
    gr.room(opx - 1, ry1 + 3, opx + 1, ry1 + 5)
    gr.put(opx, ry1 + 4, 'O')


def build_sequencer(gr, seqtop, lane_x0, seq_attach_x):
    """Branchless boustrophedon snake. 16 lanes at columns lane_x0..lane_x0+15,
    attaching at the sequencer bottom wall. Reads the single incoming SEQ pipe
    (attach column seq_attach_x on the top wall) 16 times, sending e_k to the
    k-th visited lane (visited RIGHT->LEFT so col(hi) gets e0 ... col(lo) gets
    e15). Returns dict with bottom-wall row (where lanes attach) and lane cols."""
    ST = seqtop                    # top wall row
    Rspine = ST + 1
    Rtop = ST + 2
    Rr1 = ST + 3
    Rr2 = ST + 4
    Rbot = ST + 5
    SB = ST + 6                    # bottom wall row (lanes attach here)
    cols = list(range(lane_x0, lane_x0 + 16))
    hi, lo = cols[-1], cols[0]     # rightmost, leftmost
    # snake cells
    for i, c in enumerate(cols[::-1]):     # process right->left: i=0 -> hi (down)
        down = (i % 2 == 0)
        if down:
            gr.put(c, Rtop, 'v'); gr.put(c, Rr1, 'r'); gr.put(c, Rr2, 's')
            gr.put(c, Rbot, '<')           # turn W to next (up) column
        else:
            gr.put(c, Rbot, '^'); gr.put(c, Rr2, 'r'); gr.put(c, Rr1, 's')
            # top connector: '<' to next down-column, EXCEPT the last (leftmost)
            if c == lo:
                gr.put(c, Rtop, '^')       # go up to spine, return east
            else:
                gr.put(c, Rtop, '<')
    # first (rightmost, down) column entered from spine
    gr.put(hi, Rspine, 'v')
    # spine: from lo..hi, '>' filler, drop 'v' at hi ; @ at lo-1
    gr.put(lo, Rspine, '>')
    for c in range(lo + 1, hi):
        gr.put(c, Rspine, '>')
    gr.put(lo - 1, Rspine, '@')            # start (executed once)
    # SEQ incoming pipe attaches at top wall seq_attach_x (pipe cells above)
    gr.put(seq_attach_x, ST - 1, 'v')
    gr.put(seq_attach_x, ST - 2, 'v')
    # room walls
    rx0 = lo - 2
    rx1 = hi + 2
    gr.room(rx0, ST, rx1, SB)
    return dict(SB=SB, cols=cols, rx0=rx0, rx1=rx1, seqtop=ST)


def _xproc(gr, x, y):
    """X-process gadget. Man enters (x,y)='X' moving EAST, A holds a lane value.
    A>0 (biased real): CW->S, debias (A-=C, needs B=C), send to O, rejoin.
    A==0 (padding): straight->E, skip. Both exit at (x+4,y) moving EAST.
    Occupies cols x..x+3, rows y..y+3."""
    gr.put(x, y, 'X')
    # pad path (straight E)
    gr.put(x + 1, y, '>'); gr.put(x + 2, y, '>')
    gr.put(x + 3, y, '>')          # common exit cell (also real rejoin) -> E
    # real path (CW -> S)
    gr.put(x, y + 1, '-')          # A -= C
    gr.put(x, y + 2, 's')          # send to O
    gr.put(x, y + 3, '>')
    gr.put(x + 1, y + 3, '>'); gr.put(x + 2, y + 3, '>')
    gr.put(x + 3, y + 3, '^')      # climb back to exit row
    gr.put(x + 3, y + 2, '^'); gr.put(x + 3, y + 1, '^')
    return x + 4                    # exit column (man moving E at row y)


def _hrail(gr, x_from, x_to, y, turn_end):
    """Lay a horizontal '<' or '>' rail between columns (exclusive of endpoints'
    turn glyphs). Man travels from x_from toward x_to. Places '<'/'>' fill."""
    step = 1 if x_to > x_from else -1
    fill = '>' if step == 1 else '<'
    for c in range(x_from, x_to, step):
        gr.put(c, y, fill)
    gr.put(x_to, y, turn_end)


def build_writer(gr, lanetop_wall, lane_cols, ack=False):
    """Full multi-round writer. Lanes attach at TOP wall (lanetop_wall) at
    lane_cols. Barrier `r` on leftmost lane (last-filled), then 15x `R`, reading
    lanes in reading order (left->right = reversed emission). Loops per round.
    Man phases flow generally downward; a west+up corridor returns to RESET.
    If ack, send an ACK to the reader after fully draining each round (16 reads)."""
    WT = lanetop_wall
    lo = lane_cols[0]                    # leftmost lane column (barrier target)
    bcol = lo - 1                        # barrier approach column (r at col lo)
    LC = 1                               # left corridor column (return path)
    rx1 = lane_cols[-1] + 2              # right wall

    # ---- setup (once): @ `2097152` M  -> B=C ----
    gr.text(2, WT + 1, '@' + lit(C) + 'M')
    ex = 2 + len('@' + lit(C) + 'M')
    gr.put(ex, WT + 1, 'v')              # drop
    _hrail(gr, ex, LC, WT + 2, 'v')      # west to left corridor, turn S

    # ---- RESET (per round entry): `15` b -> BP=15 ----
    # place the literal at col 7 so its backticks (col7,col10) don't column-align
    # with the reader's literals (cols 5,8,15,23) -> avoids spurious vertical lit.
    rr = WT + 3
    gr.put(LC, rr, '>')
    for c in range(LC + 1, 7):
        gr.put(c, rr, '>')
    gr.text(7, rr, lit(15) + 'b')
    rex = 7 + len(lit(15) + 'b')
    gr.put(rex, rr, 'v')
    _hrail(gr, rex, bcol, WT + 4, 'v')   # west to barrier column, turn S

    # ---- BARRIER: r at col lo, then barrier X-process (rows by..by+3) ----
    by = WT + 5
    gr.put(bcol, by, '>')
    gr.put(lo, by, 'r')                  # barrier read (col lo -> lane lo)
    bxo = _xproc(gr, lo + 1, by)         # exit col bxo, row by
    # barrier exit -> down (col bxo) below xproc, then west to barrier column
    gr.put(bxo, by, 'v')
    for yy in range(by + 1, WT + 9):
        gr.put(bxo, yy, 'v')
    _hrail(gr, bxo, bcol, WT + 9, 'v')   # west at WT+9, turn S at bcol
    gr.put(bcol, WT + 10, 'v')           # drop toward loop entry

    # ---- LOOP (15x): R, X-process, m, a(loop/exit) ----
    ly = WT + 11
    gr.put(bcol, ly, '>')
    gr.put(lo, ly, 'R')                  # loop read
    lxo = _xproc(gr, lo + 1, ly)         # exit col lxo, row ly
    gr.put(lxo, ly, 'm')                 # BP--
    gr.put(lxo + 1, ly, 'a')             # BP>0 -> CCW -> N loopback ; else E -> exit
    # loopback (BP>0): N to row ly-1 then west to barrier col, drop into '>' at (bcol,ly)
    _hrail(gr, lxo + 1, bcol, ly - 1, 'v')   # (bcol,ly-1)='v' (shared with barrier drop)
    gr.put(lxo + 1, ly - 1, '<')             # N-arrival turns W
    # exit (BP==0): straight E. If ack, detour east to ACK-send near right wall.
    ack_attach = None
    if ack:
        _hrail(gr, lxo + 2, rx1 - 2, ly, 's')    # east rail, ACK-send at rx1-2
        ack_attach = (rx1, ly)                   # ACK exits right wall at row ly
        gr.put(rx1 - 1, ly, 'v')                 # then drop
        dropx = rx1 - 1
    else:
        gr.put(lxo + 2, ly, 'v')
        dropx = lxo + 2
    botrow = ly + 5
    for yy in range(ly + 1, botrow):
        gr.put(dropx, yy, 'v')
    _hrail(gr, dropx, LC, botrow, '^')       # west along bottom, turn N at LC
    for yy in range(rr + 1, botrow):         # climb LC up to RESET row
        gr.put(LC, yy, '^')
    # (LC,rr)='>' already -> climbing man arrives facing E into RESET.

    # ---- room walls + O pipe ----
    rx0 = 0
    ry1 = botrow + 1
    gr.room(rx0, WT, rx1, ry1)
    ocol = lo + 1                        # under the xproc 's' columns
    gr.put(ocol, ry1 + 1, 'v')
    gr.put(ocol, ry1 + 2, 'v')
    gr.room(ocol - 1, ry1 + 3, ocol + 1, ry1 + 5)
    gr.put(ocol, ry1 + 4, 'O')
    return dict(rx0=rx0, rx1=rx1, ry1=ry1, ack_attach=ack_attach)


def build_seqwriter(gr):
    """Test rig: I -> SEQ pipe -> sequencer -> 16 lanes -> writer -> O.
    Feed 16-value stream on stdin; writer should print reversed reals."""
    lane_x0 = 3
    seqtop = 5
    seq_attach_x = 2              # SEQ attaches at sequencer top wall col2 (interior)
    seq = build_sequencer(gr, seqtop, lane_x0, seq_attach_x)
    # I room above sequencer feeding SEQ pipe (down into seq top col2)
    gr.room(seq_attach_x - 1, seqtop - 5, seq_attach_x + 1, seqtop - 3)
    gr.put(seq_attach_x, seqtop - 4, 'I')
    # (pipe cells at seqtop-1, seqtop-2 already placed by build_sequencer)
    # lanes: from SB down 2 cells to writer top wall
    SB = seq['SB']
    cols = seq['cols']
    WT = SB + 3
    for c in cols:
        gr.put(c, SB + 1, 'v')
        gr.put(c, SB + 2, 'v')
    build_writer(gr, WT, cols)


def build_full(gr, ack=True):
    """Complete machine: reader -> SEQ -> sequencer -> lanes -> writer -> O.
    With ack=True, add the writer->reader ACK pipe that serializes rounds."""
    # Reader at top (no O). It emits 16 values to SEQ (bottom wall).
    att = build_reader(gr, 0, 6, out_to_O=False, ack=ack)
    seq_x = att['seq_x']
    reader_bottom = att['room_y1']
    seqtop = reader_bottom + 4
    for yy in range(reader_bottom + 3, seqtop - 2):
        gr.put(seq_x, yy, 'v')
    seq = build_sequencer(gr, seqtop, 3, seq_x)
    SB = seq['SB']; cols = seq['cols']
    WT = SB + 3
    for c in cols:
        gr.put(c, SB + 1, 'v'); gr.put(c, SB + 2, 'v')
    wr = build_writer(gr, WT, cols, ack=ack)

    if ack:
        # Route ACK pipe: writer right wall -> up the free right corridor -> east
        # -> up into reader bottom-right. Flow is upward (writer -> reader).
        wx, wy = wr['ack_attach']            # writer right-wall attach (rx1, row)
        rx = att['ack_x']                    # reader ACK column
        rby = att['ack_bottom']              # reader bottom wall row
        col_up = wx + 2                      # free column just right of writer
        turn_row = rby + 2                   # horizontal run just below the reader
        gr.put(wx + 1, wy, '>')              # exit EAST (perpendicular to wall = outgoing)
        gr.put(col_up, wy, '^')              # bend up
        for yy in range(turn_row + 1, wy):
            gr.put(col_up, yy, '^')
        gr.put(col_up, turn_row, '>')        # bend east
        for xx in range(col_up + 1, rx):
            gr.put(xx, turn_row, '>')
        gr.put(rx, turn_row, '^')            # bend north
        for yy in range(rby + 1, turn_row):
            gr.put(rx, yy, '^')
        # (rx, rby+1) is the reader attach pipe cell (into reader bottom wall)
