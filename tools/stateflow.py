"""Shared Flow macros and hardware for stateful 16x16 display problems.

The component combines a small scalar belt, a 256-cell belt, one-value scratch
FIFO, round input, and an addressable 16x16 display.  Problem builders provide
only the control-flow graph.
"""

import belt_ram
import flowgrid
import littleman as lm


class Flow(flowgrid.Flow):
    """Flow with scalar RAM, cell RAM, input, scratch, and display macros."""

    def load(self, addr):
        """A := scalar[addr], preserving B."""
        if addr < 10:
            return self.const(0).e("sc").const(addr).e("sc", "rr")
        return (
            self.e("W", "sp", "W")
            .const(0).e("sc").const(addr).e("sc", "rr")
            .e("M", "rp", "W")
        )

    def store(self, addr):
        """scalar[addr] := A."""
        if addr < 10:
            return self.e("M").const(1).e("sc").const(addr).e("sc", "W", "sc")
        return self.e("sp").const(1).e("sc").const(addr).e("sc", "rp", "sc")

    def loadv(self):
        """A := scalar[A]."""
        return self.e("M").const(0).e("sc", "W", "sc", "rr")

    def storev(self):
        """scalar[B] := A, using the scratch FIFO."""
        return (
            self.e("W", "sp", "W", "sp")
            .const(1).e("sc", "rp", "sc", "rp", "sc")
        )

    def cell_loadv(self):
        """A := cell[A]."""
        return self.e("M").const(0).e("cc", "W", "cc", "cr")

    def cell_storev(self):
        """cell[B] := A, using the scratch FIFO."""
        return (
            self.e("W", "sp", "W", "sp")
            .const(1).e("cc", "rp", "cc", "rp", "cc")
        )

    def cell_load(self, index_addr):
        return self.load(index_addr).cell_loadv()

    def cell_store(self, index_addr, stage_addr):
        return (
            self.store(stage_addr).load(index_addr).e("M")
            .load(stage_addr).cell_storev()
        )

    def inp(self):
        return self.e("ri")

    def addc(self, addr, value, dst=None):
        self.const(value).e("M").load(addr).e("+")
        return self.store(dst) if dst is not None else self

    def subc(self, addr, value, dst=None):
        self.const(value).e("M").load(addr).e("-")
        return self.store(dst) if dst is not None else self

    def bin(self, op, left, right, dst=None):
        self.load(right).e("M").load(left).e(op)
        return self.store(dst) if dst is not None else self

    def index(self, x_addr, y_addr, dst):
        """dst := 16 * scalar[y_addr] + scalar[x_addr]."""
        return (
            self.load(y_addr).e("M").const(4).e("W", "{", "M")
            .load(x_addr).e("+").store(dst)
        )

    def display_const(self, index_addr, color):
        """Write a constant color to the display at scalar[index_addr]."""
        return self.load(index_addr).e("sa").const(color).e("sd")

    def display_value(self, index_addr, color_addr):
        """Write scalar[color_addr] at display scalar[index_addr]."""
        return self.load(index_addr).e("sa").load(color_addr).e("sd")

    def commit(self):
        return self.const(1).e("ss")


DEFAULT_PORTS = {
    "ri": (10, "r", 1, 19),
    "sp": (20, "s", 1, 34),
    "rp": (30, "r", 21, 51),
    "sc": (50, "s", 36, 64),
    "rr": (74, "r", 53, 152),
    "sd": (130, "s", 100, 135),
    "sa": (140, "s", 136, 179),
    "cc": (200, "s", 191, 240),
    "cr": (230, "r", 153, 240),
    "ss": (250, "s", 241, 260),
}


def build_program(
    flow,
    scalar_size=32,
    code_x=380,
    pooled_edges=True,
    tight_gaps=True,
    dedup_edges=True,
    coalesce_targets=True,
):
    """Compile *flow* and attach the shared stateful-problem hardware."""
    p = lm.Program()
    layout = flowgrid.lay_cfg_controller(
        p,
        flow,
        DEFAULT_PORTS,
        code_x=code_x,
        pooled_edges=pooled_edges,
        tight_gaps=tight_gaps,
        dedup_edges=dedup_edges,
        coalesce_targets=coalesce_targets,
        local_edges=True,
    )
    ports = layout["ports"]
    bottom = layout["bottom"]

    # Components sit below the controller. All controller ports leave through
    # its bottom wall and route outside the room before entering a component.
    scalar_x, scalar_y = code_x + 48, bottom + 5
    cell_x, cell_y = code_x + 148, bottom + 5
    scalar = belt_ram.build(p, scalar_x, scalar_y, scalar_size)
    cell = belt_ram.build(p, cell_x, cell_y, 256)

    # Round input.
    p.input_room(ports["ri"][0] - 1, bottom + 12)
    p.pipe([(ports["ri"][0], bottom + 11), ports["ri"]])

    # Two-value scratch echo. This is used to stage dynamic addresses/payloads.
    scratch_y = bottom + 12
    scratch_x = code_x + 18
    p.room(scratch_x, scratch_y, 8, 4)
    p.text(scratch_x + 1, scratch_y + 1, "@>rsv")
    p.put(scratch_x + 5, scratch_y + 2, "<")
    p.put(scratch_x + 2, scratch_y + 2, "^")
    p.pipe([
        (code_x + 20, bottom),
        (code_x + 20, scratch_y - 3),
        (scratch_x + 3, scratch_y - 3),
        (scratch_x + 3, scratch_y - 1),
    ])
    p.pipe([
        (scratch_x + 4, scratch_y - 1),
        (scratch_x + 4, scratch_y - 3),
        (code_x + 30, scratch_y - 3),
        (code_x + 30, bottom),
    ])

    command = scalar["command"]
    p.pipe([
        ports["sc"],
        (ports["sc"][0], scalar_y - 3),
        (scalar_x - 3, scalar_y - 3),
        (scalar_x - 3, command[1] + 3),
        (command[0], command[1] + 3),
        command,
    ])
    p.pipe([
        scalar["reply"],
        (ports["rr"][0], scalar["reply"][1]),
        ports["rr"],
    ])
    p.pipe([
        ports["cc"],
        (ports["cc"][0], cell_y - 3),
        (cell_x - 3, cell_y - 3),
        (cell_x - 3, cell["command"][1] + 3),
        (cell["command"][0], cell["command"][1] + 3),
        cell["command"],
    ])
    p.pipe([
        cell["reply"],
        (ports["cr"][0], cell["reply"][1]),
        ports["cr"],
    ])

    # Addressable 16x16 display.
    display_x, display_y = code_x + 110, bottom + 60
    p.display(display_x, display_y, 18, 18)
    # RAM now sits immediately below the controller. Leave each display port
    # vertically, turn in the two-row band above RAM, and descend around the
    # components instead of crossing their rooms or recirculation belts.
    p.pipe([
        ports["sa"],
        (ports["sa"][0], display_y - 3),
        (display_x + 8, display_y - 3),
        (display_x + 8, display_y - 1),
    ])
    p.pipe([
        ports["sd"],
        (ports["sd"][0], display_y - 4),
        (scalar_x - 3, display_y - 4),
        (scalar_x - 3, display_y + 8),
        (display_x - 1, display_y + 8),
    ])
    p.pipe([
        ports["ss"],
        (ports["ss"][0], display_y + 20),
        (display_x + 8, display_y + 20),
        (display_x + 8, display_y + 18),
    ])
    return p
