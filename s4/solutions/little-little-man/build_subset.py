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
import flowgrid
import belt_ram


# Scalar addresses fit in one digit, allowing store() to preserve its payload in B.
W, HH, IX, IY, MAN, DIR, RA, RB, DEAD, K = range(10)
LEFT, RIGHT, TOP, BOTTOM = DIR, RA, RB, DEAD
TMP, TMP2, CH, CHR = K, HH, W, DIR
CELL0 = 32
RAM_N = 288


class Flow(flowgrid.Flow):

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


CTRL_CODE = 300


def lay_controller(
    p,
    flow,
    x0=0,
    y0=0,
    code_x=CTRL_CODE,
    port_profile="wide",
    local_edges=False,
    direct_edges=False,
    banked=False,
    pooled_edges=False,
    return_layout=False,
    tight_gaps=False,
    dedup_edges=False,
    lay_fn=None,
):
    if port_profile == "compact" and banked:
        spec = {
            "ri": (10, "r", 1, 19),
            "rp": (30, "r", 21, 51),
            "rr": (74, "r", 53, 152),
            "cr": (230, "r", 153, 240),
            "sp": (20, "s", 1, 34),
            "sc": (50, "s", 36, 64),
            "sd": (80, "s", 66, 98),
            "sa": (118, "s", 100, 149),
            "ss": (180, "s", 150, 189),
            "cc": (200, "s", 191, 240),
        }
    elif port_profile == "compact":
        # Each operation may be placed anywhere in its attachment's strict
        # nearest-pipe Voronoi zone. This lets repeated RAM sends continue on
        # one row instead of returning to the code column after every value.
        spec = {
            "ri": (10, "r", 1, 19),
            "rp": (30, "r", 21, 51),
            "rr": (74, "r", 53, 145),
            "sp": (20, "s", 1, 34),
            "sc": (50, "s", 36, 64),
            "sd": (80, "s", 66, 98),
            "sa": (118, "s", 100, 128),
            "ss": (140, "s", 130, 145),
        }
    else:
        spec = {
            "ri": (10, "r"),
            "sp": (20, "s"),
            "rp": (30, "r"),
            "sc": (50, "s"),
            "rr": (74, "r"),
            "sd": (80, "s"),
            "sa": (118, "s"),
            "ss": (140, "s"),
        }
    if lay_fn is not None:
        layout = lay_fn(p, flow, spec, code_x=code_x)
    else:
        layout = flowgrid.lay_cfg_controller(
            p,
            flow,
            spec,
            code_x=code_x,
            x0=x0,
            y0=y0,
            local_edges=local_edges,
            direct_edges=direct_edges,
            pooled_edges=pooled_edges,
            tight_gaps=tight_gaps,
            dedup_edges=dedup_edges,
        )
    return layout if return_layout else layout["ports"]


def _cmd_route(port_col, cy, command):
    """Controller port -> a belt RAM's bottom-wall command attachment.

    The attachment sits below the server, so the pipe must get past it and turn
    back NORTH into it -- ending on the arrival heading leaves the pipe dangling
    with ``dst: -1`` and no error, which silently re-binds the server's command
    reads to its own belt.  Hugging the room's left wall keeps the detour to the
    room's own height instead of the 80-row stagger the wide layout used.
    """
    lane = command[0] - 5
    below = command[1] + 3
    return [
        (port_col, cy),
        (port_col, cy + 1),
        (lane, cy + 1),
        (lane, below),
        (command[0], below),
        command,
    ]


def _attach_tight(p, ports, cy, ram_size, cell_ram_size, display_addr, gap):
    """Hardware packed into one shallow band right under the controller wall.

    The wide layout staggered every service 45-100 rows below the controller and
    dog-legged each pipe around it, which cost two things at once:

      * 143 grid rows of nothing but descending pipe (rows 994-1136 of the
        277x1137 champion carried 4-10 cells each), and
      * latency: the scalar-RAM command pipe was 122 cells and its reply 99, so
        every scalar access paid ~221 ticks of pure transport.  Profiling showed
        79% of the controller's ticks were stalled on `r`.

    Here every service sits directly under the port column it serves, in one
    43-row band, with `command_top` letting the command pipe be 2 cells long.
    Both dimensions of the score move: box and average ticks.
    """
    top = cy + gap
    ri, sp, rp = ports["ri"][0], ports["sp"][0], ports["rp"][0]
    sc, rr, sd = ports["sc"][0], ports["rr"][0], ports["sd"][0]
    ss = ports["ss"][0]

    # Input: 3x3 room immediately below its port.
    p.input_room(ri - 1, top)
    p.pipe([(ri, top - 1), (ri, cy)])

    # One-value scratch echo: stages a variable RAM address across payload
    # computation without nesting a RAM request inside a write transaction.
    sy = top + 4
    sx = sp - 2
    p.room(sx, sy, 8, 4)
    p.text(sx + 1, sy + 1, "@>rsv")
    p.put(sx + 5, sy + 2, "<")
    p.put(sx + 2, sy + 2, "^")
    p.pipe([(sp, cy), (sp, sy - 2), (sx + 3, sy - 2), (sx + 3, sy - 1)])
    p.pipe([(sx + 4, sy - 1), (sx + 4, sy - 3), (rp, sy - 3), (rp, cy)])

    # Scalar RAM directly under its command port; the command pipe hugs the
    # room's left wall instead of descending 80 rows first (122 cells -> 36).
    ram = belt_ram.build(p, sc - 2, top, ram_size)
    p.pipe(_cmd_route(sc, cy, ram["command"]))
    reply = ram["reply"]
    p.pipe([reply, (rr, reply[1]), (rr, cy)])

    # 16x16 display: ADDR on top (aligned to its port), DATA left, SWAP bottom.
    addr_col = ports["sa"][0] if display_addr else sd + 38
    dx, dy = addr_col - 8, top
    p.display(dx, dy, 18, 18)
    p.pipe([(sd, cy), (sd, dy + 8), (dx - 1, dy + 8)])
    if display_addr:
        p.pipe([(addr_col, cy), (addr_col, dy - 1)])
    p.pipe([(ss, cy), (ss, dy + 20), (dx + 8, dy + 20), (dx + 8, dy + 18)])

    if cell_ram_size is not None:
        cc, cr = ports["cc"][0], ports["cr"][0]
        cell = belt_ram.build(p, cc - 2, top, cell_ram_size)
        p.pipe(_cmd_route(cc, cy, cell["command"]))
        creply = cell["reply"]
        p.pipe([creply, (cr, creply[1]), (cr, cy)])
    return p


def build_program(
    flow,
    ram_size,
    display_addr=False,
    controller_code=CTRL_CODE,
    port_profile="wide",
    local_edges=False,
    direct_edges=False,
    cell_ram_size=None,
    pooled_edges=False,
    tight_gaps=False,
    dedup_edges=False,
    lay_fn=None,
    hw_layout="wide",
    hw_gap=2,
):
    """Attach a compiled Flow to the shared input/RAM/scratch/display hardware."""
    p = lm.Program()
    ports = lay_controller(
        p,
        flow,
        code_x=controller_code,
        port_profile=port_profile,
        local_edges=local_edges,
        direct_edges=direct_edges,
        banked=cell_ram_size is not None,
        pooled_edges=pooled_edges,
        tight_gaps=tight_gaps,
        dedup_edges=dedup_edges,
        lay_fn=lay_fn,
    )
    inp = ports["ri"]
    ram_reply = ports["rr"]
    ram_cmd = ports["sc"]
    data = ports["sd"]
    swap = ports["ss"]
    cy = inp[1]
    if hw_layout == "tight":
        return _attach_tight(
            p, ports, cy, ram_size, cell_ram_size, display_addr, hw_gap
        )
    # Place RAM and display below the controller, then route outside its bbox.
    rox, roy = controller_code + 48, cy + 80
    ram = belt_ram.build(p, rox, roy, ram_size)
    # Input room.
    p.input_room(inp[0] - 1, cy + 12)
    p.pipe([(inp[0], cy + 11), (inp[0], cy)])
    # One-value scratch echo used to stage a variable RAM address across payload
    # computation without nesting a RAM request inside a write transaction.
    sy = cy + 28
    sx = controller_code + 18
    p.room(sx, sy, 8, 4)
    p.text(sx + 1, sy + 1, "@>rsv")
    p.put(sx + 5, sy + 2, "<"); p.put(sx + 2, sy + 2, "^")
    p.pipe([(controller_code + 20, cy), (controller_code + 20, sy - 3),
            (sx + 3, sy - 3), (sx + 3, sy - 1)])
    p.pipe([(sx + 4, sy - 1), (sx + 4, sy - 3),
            (controller_code + 30, sy - 3), (controller_code + 30, cy)])
    # Command dog-legs around the RAM's left wall, then enters bottom-col2.
    ram_cmd = ram["command"]
    p.pipe([(ram_cmd[0], cy), (ram_cmd[0], roy - 3), (rox - 3, roy - 3),
            (rox - 3, ram_cmd[1] + 3), (ram_cmd[0], ram_cmd[1] + 3), ram_cmd])
    read_reply = ram["reply"]
    p.pipe([(read_reply[0], read_reply[1]), (ram_reply[0], read_reply[1]),
            (ram_reply[0], cy)])
    if cell_ram_size is not None:
        cell_cmd = ports["cc"]
        cell_reply = ports["cr"]
        crox, croy = controller_code + 148, cy + 100
        cell_ram = belt_ram.build(p, crox, croy, cell_ram_size)
        command = cell_ram["command"]
        p.pipe([
            (cell_cmd[0], cy),
            (cell_cmd[0], croy - 3),
            (crox - 3, croy - 3),
            (crox - 3, command[1] + 3),
            (command[0], command[1] + 3),
            command,
        ])
        reply = cell_ram["reply"]
        p.pipe([
            (reply[0], reply[1]),
            (cell_reply[0], reply[1]),
            (cell_reply[0], cy),
        ])
    # 16x16 display, DATA on left and SWAP on bottom.
    dx, dy = controller_code + 110, cy + 45
    p.display(dx, dy, 18, 18)
    p.pipe([(data[0], cy), (data[0], dy - 3), (dx - 3, dy - 3),
            (dx - 3, dy + 8),
            (dx - 1, dy + 8)])
    if display_addr:
        addr = ports["sa"]
        p.pipe([(addr[0], cy), (addr[0], dy - 1)])
    p.pipe([(swap[0], cy), (swap[0], dy + 20), (dx + 8, dy + 20), (dx + 8, dy + 18)])
    return p


def build():
    return build_program(build_flow(), RAM_N)


if __name__ == "__main__":
    p = build()
    out = os.path.join(HERE, "subset-room.man")
    p.save(out)
    print("saved", out, "footprint", p.footprint())
