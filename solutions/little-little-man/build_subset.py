#!/usr/bin/env python3
"""LLM interpreter, first correctness slice: one rectangular room, no pipes.

This is deliberately generated and kept separate from the eventual full interpreter.
It implements every non-pipe LLM instruction, persistent step rounds, H/wall stopping,
and exact 16x16 display frames.  State lives in a 288-slot circulating RAM service.
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import littleman as lm


# Scalar addresses fit in one digit, allowing store() to preserve its payload in B.
W, HH, IX, IY, MAN, DIR, RA, RB, DEAD, K = range(10)
LEFT, RIGHT, TOP, BOTTOM = DIR, RA, RB, DEAD
TMP, TMP2, CH, CHR = K, HH, W, DIR
CELL0 = 32
RAM_N = 288


def cseq(n):
    """Load a small non-negative integer without backtick literals."""
    assert 0 <= n < 2048
    if n < 10:
        return [str(n)]
    bits = bin(n)[2:]
    out = [bits[0]]
    for bit in bits[1:]:
        out += ["M", "+"]
        if bit == "1":
            out += ["M", "1", "+"]
    return out


class Flow:
    def __init__(self):
        self.blocks = {}
        self.cur = None

    def at(self, label):
        assert label not in self.blocks
        self.cur = []
        self.blocks[label] = self.cur
        return self

    def e(self, *xs):
        self.cur.extend(xs)
        return self

    def const(self, n):
        return self.e(*cseq(n))

    def load(self, addr):
        # RAM READ protocol [0,addr], then reply. B is preserved.
        return self.const(0).e("sc").const(addr).e("sc", "rr")

    def store(self, addr):
        # Preserve payload in B while sending [1,addr,payload].
        return self.e("M").const(1).e("sc").const(addr).e("sc", "W", "sc")

    def inp(self):
        return self.e("ri")

    def raw(self, cell_addr=None):
        """A := ascii from packed record already in A, or loaded from cell_addr."""
        if cell_addr is not None:
            self.load(cell_addr)
        # Divide by 16 using only the single-digit divisor 2, preserving the
        # dividend each time. Multi-digit constant synthesis clobbers B.
        return self.e(*(["M", "2", "W", "/"] * 4))

    def bin(self, op, x, y, dst=None):
        # A = RAM[x] op RAM[y].
        self.load(y).e("M").load(x).e(op)
        if dst is not None:
            self.store(dst)
        return self

    def addc(self, addr, n, dst=None):
        self.const(n).e("M").load(addr).e("+")
        if dst is not None:
            self.store(dst)
        return self

    def subc(self, addr, n, dst=None):
        self.const(n).e("M").load(addr).e("-")
        if dst is not None:
            self.store(dst)
        return self

    def go(self, label):
        return self.e(("go", label))

    def br(self, pos, zero, neg):
        return self.e(("br", pos, zero, neg))

    def eq(self, addr, value, yes, no):
        self.subc(addr, value).br(no, yes, no)
        return self


def build_flow():
    f = Flow()
    # Read dimensions and initialize scalar state.
    f.at("START").inp().store(W).inp().store(HH)
    for a in (IX, IY, MAN, DIR, RA, RB, DEAD):
        f.const(0).store(a)
    f.go("READ_TEST")

    # Stream W*H chars, writing into fixed-stride (16*y+x) cells.
    f.at("READ_TEST").bin("-", IY, HH).br("AFTER_READ", "AFTER_READ", "READ_ROW")
    f.at("READ_ROW").bin("-", IX, W).br("NEXT_ROW", "NEXT_ROW", "READ_ONE")
    f.at("NEXT_ROW").const(1).e("M").load(IY).e("+").store(IY)
    f.const(0).store(IX).go("READ_TEST")
    f.at("READ_ONE").inp().store(CHR)
    # addr = 16*y+x
    f.load(IY).e("M").const(4).e("W", "{", "M").load(IX).e("+").store(TMP)
    # record = ascii<<4 (color filled in after room bounds are known)
    # Stage the variable address in the scratch echo while payload is computed.
    f.addc(TMP, CELL0).e("sp")
    f.load(CHR).e("M").const(4).e("W", "{", "M")
    f.const(1).e("sc", "rp", "sc", "W", "sc")
    # Remember @.
    f.subc(CHR, 64).br("NOT_AT", "IS_AT", "NOT_AT")
    f.at("IS_AT").load(TMP).store(MAN).go("READ_ADV")
    f.at("NOT_AT").go("READ_ADV")
    f.at("READ_ADV").const(1).e("M").load(IX).e("+").store(IX).go("READ_ROW")

    # Derive room boundaries.  '|' is not an LLM instruction, so horizontal scans
    # from @ cannot confuse a wall with code.
    f.at("AFTER_READ").load(MAN).e("M").const(4).e("W", "}").store(IY)
    f.load(IY).e("M").const(4).e("W", "{", "M").load(MAN).e("-").store(IX)
    f.load(IX).store(LEFT).go("LEFT_SCAN")
    f.at("LEFT_SCAN").subc(LEFT, 1, LEFT)
    f.load(IY).e("M").const(4).e("W", "{", "M").load(LEFT).e("+").store(TMP)
    f.addc(TMP, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH)
    f.eq(CH, 124, "LEFT_DONE", "LEFT_SCAN")
    f.at("LEFT_DONE").load(IX).store(RIGHT).go("RIGHT_SCAN")
    f.at("RIGHT_SCAN").addc(RIGHT, 1, RIGHT)
    f.load(IY).e("M").const(4).e("W", "{", "M").load(RIGHT).e("+").store(TMP)
    f.addc(TMP, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH)
    f.eq(CH, 124, "RIGHT_DONE", "RIGHT_SCAN")

    # Corners at LEFT identify top/bottom; scan vertically from the man.
    f.at("RIGHT_DONE").load(IY).store(TOP).go("TOP_SCAN")
    f.at("TOP_SCAN").subc(TOP, 1, TOP)
    f.load(TOP).e("M").const(4).e("W", "{", "M").load(LEFT).e("+").store(TMP)
    f.addc(TMP, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH)
    f.eq(CH, 43, "TOP_DONE", "TOP_SCAN")
    f.at("TOP_DONE").load(IY).store(BOTTOM).go("BOTTOM_SCAN")
    f.at("BOTTOM_SCAN").addc(BOTTOM, 1, BOTTOM)
    f.load(BOTTOM).e("M").const(4).e("W", "{", "M").load(LEFT).e("+").store(TMP)
    f.addc(TMP, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH)
    f.eq(CH, 43, "COLOR_INIT", "BOTTOM_SCAN")

    # Color all 256 display cells.  Padding cells were seeded as zero.
    f.at("COLOR_INIT").const(0).store(TMP).go("COLOR_TEST")
    # Only classify rows through the room's bottom wall; remaining display cells
    # stay at the RAM's seeded black value.
    f.at("COLOR_TEST").load(TMP).e("M").const(4).e("W", "}").store(IY)
    f.bin("-", IY, BOTTOM).br("COLOR_DONE", "COLOR_ONE", "COLOR_ONE")
    f.at("COLOR_ONE").addc(TMP, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH)
    # x/y and boundary test.
    f.load(TMP).e("M").const(4).e("W", "}").store(IY)
    f.load(IY).e("M").const(4).e("W", "{", "M").load(TMP).e("-").store(IX)
    # Cells outside the single room's rectangle are black.
    f.bin("-", IX, LEFT).br("COLOR_IN_XL", "COLOR_IN_XL", "COLOR_ZERO")
    f.at("COLOR_IN_XL").bin("-", IX, RIGHT).br("COLOR_ZERO", "COLOR_IN_YT", "COLOR_IN_YT")
    f.at("COLOR_IN_YT").bin("-", IY, TOP).br("COLOR_IN_YB", "COLOR_IN_YB", "COLOR_ZERO")
    f.at("COLOR_IN_YB").bin("-", IY, BOTTOM).br("COLOR_ZERO", "COLOR_BOUNDARY", "COLOR_BOUNDARY")
    f.at("COLOR_BOUNDARY")
    for name, addr in (("L", LEFT), ("R", RIGHT), ("T", TOP), ("B", BOTTOM)):
        f.bin("-", IX if name in "LR" else IY, addr).br(
            f"COLOR_{name}_NEXT", "COLOR_WALL", f"COLOR_{name}_NEXT")
        f.at(f"COLOR_{name}_NEXT")
    # Interior ASCII dispatch.
    mapping = {
        72: 3, 118: 3, 94: 3, 62: 3, 60: 3, 88: 3,
        77: 12, 43: 10, 45: 10, 115: 13, 114: 13,
    }
    f.subc(CH, 48).br("COLOR_DIG_HI", "COLOR_DIGIT", "COLOR_MAP_0")
    f.at("COLOR_DIG_HI").subc(CH, 57).br("COLOR_MAP_0", "COLOR_DIGIT", "COLOR_DIGIT")
    labels = list(mapping.items())
    for j, (asc, color) in enumerate(labels):
        lab = f"COLOR_MAP_{j}"
        nxt = f"COLOR_MAP_{j+1}" if j + 1 < len(labels) else "COLOR_ZERO"
        if lab not in f.blocks:
            f.at(lab)
        f.subc(CH, asc).br(nxt, f"COLOR_C{color}", nxt)
    f.at("COLOR_WALL").const(4).go("COLOR_WRITE")
    f.at("COLOR_DIGIT").const(8).go("COLOR_WRITE")
    f.at("COLOR_ZERO").const(0).go("COLOR_WRITE")
    for color in sorted(set(mapping.values())):
        f.at(f"COLOR_C{color}").const(color).go("COLOR_WRITE")
    f.at("COLOR_WRITE").store(TMP2)  # color
    # rec=(ascii<<4)+color
    f.addc(TMP, CELL0).e("sp")
    f.load(CH).e("M").const(4).e("W", "{", "M").load(TMP2).e("+", "M")
    f.const(1).e("sc", "rp", "sc", "W", "sc")
    f.addc(TMP, 1, TMP).go("COLOR_TEST")

    # Overlay the starting man and commit initial frame.
    f.at("COLOR_DONE")
    for a in (DIR, RA, RB, DEAD):
        f.const(0).store(a)
    f.const(15).store(IX)  # draw-time low-nibble mask
    f.go("DRAW")

    # Per-round command.
    f.at("ROUND").inp().store(K).go("STEP_TEST")
    f.at("STEP_TEST").load(DEAD).br("DRAW", "K_TEST", "DRAW")
    f.at("K_TEST").load(K).br("STEP_ONE", "DRAW", "DRAW")

    # Fetch current opcode.
    f.at("STEP_ONE").addc(MAN, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH).go("DISPATCH")
    # Dispatch supported instructions; default is space/no-op.
    dispatch = [
        (94, "OP_N"), (62, "OP_E"), (118, "OP_S"), (60, "OP_W"),
        (77, "OP_M"), (43, "OP_ADD"), (45, "OP_SUB"), (88, "OP_X"), (72, "OP_H"),
    ]
    for j, (asc, lab) in enumerate(dispatch):
        here = "DISPATCH" if j == 0 else f"DISPATCH_{j}"
        if here not in f.blocks:
            f.at(here)
        nxt = f"DISPATCH_{j+1}" if j + 1 < len(dispatch) else "DIGIT_TEST"
        f.subc(CH, asc).br(nxt, lab, nxt)
    f.at("DIGIT_TEST").subc(CH, 48).br("DIGIT_HI", "OP_DIGIT", "MOVE")
    f.at("DIGIT_HI").subc(CH, 57).br("MOVE", "OP_DIGIT", "OP_DIGIT")

    for lab, d in (("OP_E", 0), ("OP_S", 1), ("OP_W", 2), ("OP_N", 3)):
        f.at(lab).const(d).store(DIR).go("MOVE")
    f.at("OP_DIGIT").subc(CH, 48).store(RA).go("MOVE")
    f.at("OP_M").load(RA).store(RB).go("MOVE")
    f.at("OP_ADD").bin("+", RA, RB, RA).go("MOVE")
    f.at("OP_SUB").bin("-", RA, RB, RA).go("MOVE")
    f.at("OP_H").const(1).store(DEAD).go("STEP_FINISH")
    f.at("OP_X").load(RA).br("X_POS", "MOVE", "X_NEG")
    f.at("X_POS").addc(DIR, 1).e("M").const(3).e("W", "&").store(DIR).go("MOVE")
    f.at("X_NEG").addc(DIR, 3).e("M").const(3).e("W", "&").store(DIR).go("MOVE")

    # Move address by +1,+16,-1,-16 according to DIR.
    f.at("MOVE").load(DIR).br("DIR_NONZERO", "MOVE_E", "DIR_NONZERO")
    f.at("DIR_NONZERO").subc(DIR, 1).br("DIR_2PLUS", "MOVE_S", "DIR_2PLUS")
    f.at("DIR_2PLUS").subc(DIR, 2).br("MOVE_N", "MOVE_W", "MOVE_N")
    f.at("MOVE_E").addc(MAN, 1, MAN).go("WALL_TEST")
    f.at("MOVE_S").addc(MAN, 16, MAN).go("WALL_TEST")
    f.at("MOVE_W").subc(MAN, 1, MAN).go("WALL_TEST")
    f.at("MOVE_N").subc(MAN, 16, MAN).go("WALL_TEST")
    f.at("WALL_TEST").addc(MAN, CELL0).e("M").const(0).e("sc", "W", "sc", "rr").raw().store(CH).go("WALL_DISP")
    # Any room-wall glyph is fatal in this one-room slice.
    for j, asc in enumerate((43, 45, 124)):
        lab = "WALL_DISP" if j == 0 else f"WALL_DISP_{j}"
        if lab not in f.blocks:
            f.at(lab)
        nxt = f"WALL_DISP_{j+1}" if j < 2 else "STEP_FINISH"
        f.subc(CH, asc).br(nxt, "HIT_WALL", nxt)
    f.at("HIT_WALL").const(1).store(DEAD).go("STEP_FINISH")
    f.at("STEP_FINISH").subc(K, 1, K).go("STEP_TEST")

    # Full raster. Display cursor wraps after 256 DATA writes, so no ADDR pipe needed.
    f.at("DRAW").const(0).store(TMP).go("DRAW_TEST")
    f.at("DRAW_TEST").subc(TMP, 256).br("DRAW_SWAP", "DRAW_SWAP", "DRAW_CELL")
    f.at("DRAW_CELL").addc(TMP, CELL0).e("M").const(0).e("sc", "W", "sc", "rr")
    # Low nibble is base color. IX holds 15 and RAM loads preserve B.
    f.e("M").load(IX).e("W", "&").store(TMP2)
    f.bin("-", TMP, MAN).br("DRAW_BASE", "DRAW_MAN", "DRAW_BASE")
    f.at("DRAW_MAN").const(9).e("sd").go("DRAW_ADV")
    f.at("DRAW_BASE").load(TMP2).e("sd").go("DRAW_ADV")
    f.at("DRAW_ADV").addc(TMP, 1, TMP).go("DRAW_TEST")
    f.at("DRAW_SWAP").const(1).e("ss").go("ROUND")
    return f


def build_ram(p, ox, oy, n=RAM_N, foldw=48):
    """Addressable circulating RAM server. Protocol [op,addr,(value)], read replies."""
    put, text = p.put, p.text
    # Adapted from memory/belt5: OFF encoding gives a sign-only sentinel drain.
    put(ox + 1, oy + 1, "@"); text(ox + 2, oy + 1, "`" + str(n) + "`")
    put(ox + 2 + len(str(n)) + 2, oy + 1, "b")
    x = ox + 2 + len(str(n)) + 3
    text(x, oy + 1, "`2000000`"); put(x + 9, oy + 1, "v")
    # Seed loop.
    put(x + 9, oy + 2, "<"); put(ox + 6, oy + 2, "a"); put(ox + 7, oy + 2, "m")
    put(ox + 8, oy + 2, "s"); put(ox + 9, oy + 2, "<")
    put(ox + 6, oy + 3, ">"); put(ox + 9, oy + 3, "^")
    put(ox + 1, oy + 2, "v"); put(ox + 1, oy + 3, "v")
    put(ox + 1, oy + 4, ">"); put(ox + 2, oy + 4, "1"); put(ox + 3, oy + 4, "N")
    put(ox + 4, oy + 4, "s"); put(ox + 5, oy + 4, "v"); put(ox + 5, oy + 5, "<")
    put(ox + 2, oy + 5, "v"); put(ox + 16, oy + 5, "<")
    # command read and seek
    put(ox + 2, oy + 6, "r"); put(ox + 2, oy + 7, "M")
    put(ox + 2, oy + 8, "r"); put(ox + 2, oy + 9, "b")
    put(ox + 2, oy + 10, ">"); put(ox + 6, oy + 10, "v")
    put(ox + 6, oy + 11, "r"); put(ox + 6, oy + 12, "d")
    put(ox + 5, oy + 12, "s"); put(ox + 4, oy + 12, "m")
    put(ox + 3, oy + 12, "^"); put(ox + 3, oy + 10, ">")
    put(ox + 6, oy + 13, "W"); put(ox + 6, oy + 14, "X")
    # read
    put(ox + 6, oy + 15, "W"); put(ox + 6, oy + 16, ">")
    put(ox + 7, oy + 16, "s"); put(ox + 8, oy + 16, "M")
    text(ox + 9, oy + 16, "`2000000`"); put(ox + 18, oy + 16, "-")
    put(ox + 19, oy + 16, "N"); put(ox + 20, oy + 16, "s"); put(ox + 21, oy + 16, "v")
    put(ox + 21, oy + 17, "v"); put(ox + 21, oy + 18, "v"); put(ox + 21, oy + 19, "<")
    # write
    put(ox + 4, oy + 14, "v"); put(ox + 4, oy + 15, "r"); put(ox + 4, oy + 16, "M")
    put(ox + 4, oy + 17, ">"); text(ox + 5, oy + 17, "`2000000`")
    put(ox + 14, oy + 17, "+"); put(ox + 15, oy + 17, "v")
    put(ox + 15, oy + 18, "<"); put(ox + 10, oy + 18, "s")
    put(ox + 9, oy + 18, "v"); put(ox + 9, oy + 19, ">"); put(ox + 10, oy + 19, "v")
    # drain
    put(ox + 10, oy + 20, "v"); put(ox + 10, oy + 21, "r")
    put(ox + 10, oy + 22, "s"); put(ox + 10, oy + 23, "X")
    put(ox + 9, oy + 23, "^"); put(ox + 9, oy + 20, ">"); put(ox + 16, oy + 23, "^")
    p.room(ox, oy, 24, 25)
    # Command uses bottom col2 (preserves the proven input-vs-belt tie-break);
    # reply exits the right wall beside the read-only send.
    return (ox + 2, oy + 25), (ox + 6, oy + 25), (ox + 10, oy + 25), (ox + 24, oy + 16)


CTRL_CODE = 300


def lay_controller(p, flow, x0=0, y0=0):
    """Crossing-safe CFG layout.

    Code lives at CODE. Each label owns a vertical target lane on the left. Every
    edge descends on a unique source highway, crosses on a unique row below all
    code, then rises on the target lane. Thus blank crossings contain no turn glyph.
    """
    CODE = x0 + CTRL_CODE
    cols = {"ri": CODE + 10, "sp": CODE + 20, "rp": CODE + 30,
            "sc": CODE + 50, "rr": CODE + 74, "sd": CODE + 80, "ss": CODE + 140}
    glyph = {"ri": "r", "rp": "r", "rr": "r", "sp": "s", "sc": "s", "sd": "s", "ss": "s"}
    heads, pending = {}, []
    y = y0 + 3

    def put(x, yy, ch):
        cur = p.get(x, yy)
        assert cur in (" ", ch), (x, yy, cur, ch)
        p.put(x, yy, ch)

    for bi, (label, toks) in enumerate(flow.blocks.items()):
        heads[label] = y
        put(CODE, y, "@" if bi == 0 else ">")
        x = CODE + 1
        for tok in toks:
            if isinstance(tok, tuple):
                if tok[0] == "go":
                    pending.append(("go", (x, y), tok[1:]))
                    break
                if tok[0] == "br":
                    put(x, y, "v"); put(x, y + 1, "X")
                    pending.append(("br", (x, y + 1), tok[1:]))
                    y += 1
                    break
            elif tok in cols:
                c = cols[tok]
                if x > c:
                    put(x, y, "v"); put(x, y + 1, "<"); put(CODE, y + 1, "v")
                    y += 2; put(CODE, y, ">"); x = CODE + 1
                put(c, y, glyph[tok]); x = c + 1
                put(x, y, "v"); put(x, y + 1, "<"); put(CODE, y + 1, "v")
                y += 2; put(CODE, y, ">"); x = CODE + 1
            else:
                put(x, y, tok); x += 1
        # Leave two rows exclusively for incoming control-flow merges.
        y += 6

    target_col = {lab: x0 + 2 + i for i, lab in enumerate(flow.blocks)}
    right_hw = CODE + 150
    left_hw = CODE - 2
    routes = []
    for kind, (x, sy), tgts in pending:
        if kind == "go":
            edges = [((x, sy), "E", tgts[0])]
        else:
            pos, zero, neg = tgts
            edges = [((x - 1, sy), "W", pos),
                     ((x, sy + 1), "S", zero),
                     ((x + 1, sy), "E", neg)]
        for (sx, yy), sd, target in edges:
            if sd == "W":
                hw = left_hw; left_hw -= 1
                put(sx, yy, "<")
            elif sd == "E":
                hw = right_hw; right_hw += 1
                put(sx, yy, ">")
            else:
                hw = right_hw; right_hw += 1
                put(sx, yy, "v")
                yy += 1
                put(sx, yy, ">")
            put(hw, yy, "v")
            routes.append((hw, target))

    channel_y = y + 3
    for hw, target in routes:
        tc = target_col[target]
        put(hw, channel_y, "<")
        put(tc, channel_y, "^")
        put(tc, heads[target], ">")
        channel_y += 1
    width = right_hw - x0 + 3
    height = channel_y - y0 + 2
    p.room(x0, y0, width, height)
    return (CODE + 10, y0 + height), (CODE + 74, y0 + height), (CODE + 50, y0 + height), \
           (CODE + 80, y0 + height), (CODE + 140, y0 + height)


def build():
    p = lm.Program()
    flow = build_flow()
    inp, ram_reply, ram_cmd, data, swap = lay_controller(p, flow)
    # Place RAM and display below the controller, then route outside its bbox.
    cy = inp[1]
    rox, roy = CTRL_CODE + 48, cy + 80
    ram_in, ram_out, belt_out, read_reply = build_ram(p, rox, roy)
    # RAM belt + relay.
    base = roy + 32
    pts = [(belt_out[0], belt_out[1]), (belt_out[0], base), (rox + 48, base)]
    yy = base
    for j in range(7):
        nx = rox + (70 if j % 2 == 0 else 48)
        pts += [(nx, yy), (nx, yy + 1)]
        yy += 1
    pts += [(rox + 71, yy)]
    p.pipe(pts)
    rx = rox + 72
    p.room(rx, yy - 2, 6, 6)
    p.text(rx + 1, yy, ">@rv"); p.text(rx + 4, yy + 1, "<s.^", "W")
    p.pipe([(rx - 1, yy + 1), (ram_out[0], yy + 1),
            (ram_out[0], ram_out[1] + 2), ram_out])
    # Input room.
    p.input_room(inp[0] - 1, cy + 12)
    p.pipe([(inp[0], cy + 11), (inp[0], cy)])
    # One-value scratch echo used to stage a variable RAM address across payload
    # computation without nesting a RAM request inside a write transaction.
    sy = cy + 28
    sx = CTRL_CODE + 18
    p.room(sx, sy, 8, 4)
    p.text(sx + 1, sy + 1, "@>rsv")
    p.put(sx + 5, sy + 2, "<"); p.put(sx + 2, sy + 2, "^")
    p.pipe([(CTRL_CODE + 20, cy), (CTRL_CODE + 20, sy - 3),
            (sx + 3, sy - 3), (sx + 3, sy - 1)])
    p.pipe([(sx + 4, sy - 1), (sx + 4, sy - 3),
            (CTRL_CODE + 30, sy - 3), (CTRL_CODE + 30, cy)])
    # Command dog-legs around the RAM's left wall, then enters bottom-col2.
    p.pipe([(ram_cmd[0], cy), (ram_cmd[0], roy - 3), (rox - 3, roy - 3),
            (rox - 3, ram_in[1] + 3), (ram_in[0], ram_in[1] + 3), ram_in])
    p.pipe([(read_reply[0], read_reply[1]), (ram_reply[0], read_reply[1]),
            (ram_reply[0], cy)])
    # 16x16 display, DATA on left and SWAP on bottom.
    dx, dy = CTRL_CODE + 110, cy + 45
    p.display(dx, dy, 18, 18)
    p.pipe([(data[0], cy), (data[0], dy - 3), (dx - 3, dy - 3),
            (dx - 3, dy + 8),
            (dx - 1, dy + 8)])
    p.pipe([(swap[0], cy), (swap[0], dy + 20), (dx + 8, dy + 20), (dx + 8, dy + 18)])
    return p


if __name__ == "__main__":
    p = build()
    out = os.path.join(HERE, "subset-room.man")
    p.save(out)
    print("saved", out, "footprint", p.footprint())
