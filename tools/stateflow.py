"""Shared Flow macros and hardware for stateful 16x16 display problems.

The component combines a small scalar belt, a 256-cell belt, one-value scratch
FIFO, round input, and an addressable 16x16 display.  Problem builders provide
only the control-flow graph.
"""

import belt_ram
import flowgrid
import littleman as lm
import packed_ram_proxy
import split_ram


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

    def out(self):
        """Send A to the output room (requires output_port=True)."""
        return self.e("so")

    def queue_push(self):
        return self.e("qs")

    def queue_pop(self):
        return self.e("qr")


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
    "qs": (270, "s", 261, 290),
    "qr": (260, "r", 246, 310),
}

# Compressed port map for compact_components mode. Zones are Voronoi cells of
# the port column among same-direction ports (band rule), and sa sits WEST of
# sd so a display write (load, sa, const, sd) stays column-monotone on one row.
COMPACT_PORTS = {
    # Columns from the tools/smtrows.py port search (the greedy layout is
    # per-block row-optimal for ANY fixed map — Z3-certified — so searching
    # port columns with the greedy evaluator is exact): 154->142 op rows,
    # width 105->93 on the snake flow. Zones are strict Voronoi midpoints
    # of same-direction neighbours.
    "ri": (6, "r", 1, 12),
    "sp": (12, "s", 1, 24),
    "rp": (20, "r", 14, 33),
    "sc": (37, "s", 25, 49),
    "rr": (47, "r", 34, 86),
    "sd": (62, "s", 50, 67),
    "sa": (73, "s", 68, 78),
    "ss": (85, "s", 80, 87),
    "cc": (90, "s", 88, 155),
    "cr": (127, "r", 88, 155),
}

# Queue overlay for compact mode. The queue component is translated 100 columns
# west of its DEFAULT position (queue_x 268 -> 168), landing it just east of the
# 52-wide cell RAM (code_x+112..163). The translation is RIGID: every segment of
# the return pipe keeps its exact length, and that length IS the queue's
# capacity, so occupancy bounds are unchanged by construction.
#
# Only cc/cr's band ceilings move (155 -> 130/143, the Voronoi midpoints against
# the new qs/qr columns). Kept as an overlay rather than folded into
# COMPACT_PORTS so compact-without-queue users (snake) keep the full 88..155.
COMPACT_QUEUE_SHIFT = 100
COMPACT_QUEUE_PORTS = {
    "cc": (90, "s", 88, 130),
    "cr": (127, "r", 88, 143),
    "qr": (160, "r", 144, 200),
    "qs": (170, "s", 131, 200),
}


# Port specs for the integer output room (problems with no display). The
# column reuses the display band, so it is only valid with display=False.
OUTPUT_PORT_DEFAULT = (130, "s", 100, 135)
OUTPUT_PORT_COMPACT = (60, "s", 46, 84)


def _build_queue(p, ports, bottom, code_x, queue_rows, queue_right_off,
                 cell_replicas, shift=0):
    """Bounded FIFO service: short command pipe -> relay man -> long return pipe.

    The return pipe is both transport AND storage; its length caps queue
    occupancy (the BFS frontier of a 16x16 board never exceeds ~19 items,
    measured). ``shift`` translates the whole component ``shift`` columns west
    without changing ANY segment length, so capacity is invariant under it.
    """
    queue_x = code_x + (600 if cell_replicas > 1 else 268 - shift)
    queue_y = bottom + 6
    p.room(queue_x, queue_y, 8, 6)
    p.text(queue_x + 1, queue_y + 1, "@>rsv")
    p.put(queue_x + 5, queue_y + 2, "<")
    p.put(queue_x + 2, queue_y + 2, "^")
    p.pipe([
        ports["qs"],
        (ports["qs"][0], queue_y - 1),
    ])
    # queue_rows=6/right=320 keeps the original ~379-cell shape for legacy builds.
    right = code_x + (652 if cell_replicas > 1 else queue_right_off - shift)
    left = code_x + (612 if cell_replicas > 1 else 280 - shift)
    tail_x = code_x + (598 if cell_replicas > 1 else 266 - shift)
    queue_path = [
        (queue_x + 4, queue_y + 6),
        (queue_x + 4, queue_y + 8),
        (right, queue_y + 8),
    ]
    current_x = right
    for row in range(9, 9 + queue_rows):
        queue_path.append((current_x, queue_y + row))
        current_x = left if current_x == right else right
        queue_path.append((current_x, queue_y + row))
    tail_y = queue_y + 9 + queue_rows
    queue_path.extend([
        (current_x, tail_y),
        (tail_x, tail_y),
        (tail_x, bottom + 3),
        (ports["qr"][0], bottom + 3),
        ports["qr"],
    ])
    p.pipe(queue_path)


def _compact_components(p, ports, bottom, code_x, scalar_size, scalar_belts,
                        cell_belts, cell_size=256, packed_cell=False):
    """Compact floor: components west->east in port order, short straight feeds.

    Matches COMPACT_PORTS. Every pipe descends from its port and jogs only
    inside its own component's horizontal slot, so no two pipes cross.
    """
    b = bottom
    c = code_x

    # Round input (ri): straight drop into the input room.
    p.input_room(ports["ri"][0] - 1, b + 12)
    p.pipe([(ports["ri"][0], b + 11), ports["ri"]])

    # Scratch echo (sp/rp).
    sx, sy = ports["sp"][0] - 3, b + 8
    p.room(sx, sy, 8, 4)
    p.text(sx + 1, sy + 1, "@>rsv")
    p.put(sx + 5, sy + 2, "<")
    p.put(sx + 2, sy + 2, "^")
    p.pipe([ports["sp"], (sx + 3, sy - 1)])
    p.pipe([
        (sx + 4, sy - 1),
        (sx + 4, b + 5),
        (ports["rp"][0], b + 5),
        ports["rp"],
    ])

    # Scalar RAM (sc/rr), banked.
    scalar_x, scalar_y = c + 24, b + 5
    scalar = split_ram.build(p, scalar_x, scalar_y, scalar_size, scalar_belts)
    p.pipe([
        ports["sc"],
        (ports["sc"][0], b + 1),
        (scalar["command"][0], b + 1),
        scalar["command"],
    ])
    p.pipe([
        scalar["reply"],
        scalar["reply_turn"],
        (scalar["reply_turn"][0], b + 3),
        (ports["rr"][0], b + 3),
        ports["rr"],
    ])

    # Display (sa/sd/ss): tucked between scalar and cell RAM. Attachment
    # reading order (sa top, sd west, ss bottom) matches the classic layout.
    # sa's port column IS dx+8, so the address feed drops straight in; sd
    # descends west of the room; ss wraps around the east side to the bottom.
    if "sa" in ports:
        dx, dy = ports["sa"][0] - 8, b + 5
        p.display(dx, dy, 18, 18)
        p.pipe([ports["sa"], (dx + 8, dy - 1)])
        p.pipe([
            ports["sd"],
            (ports["sd"][0], dy + 8),
            (dx - 1, dy + 8),
        ])
        p.pipe([
            ports["ss"],
            (ports["ss"][0], dy + 20),
            (dx + 8, dy + 20),
            (dx + 8, dy + 18),
        ])

    # Output room (so): a straight drop in the band the display vacated.
    if "so" in ports:
        sox = ports["so"][0]
        p.output_room(sox - 1, b + 8)
        p.pipe([ports["so"], (sox, b + 7)])

    # Cell RAM (cc/cr), banked.
    cell_x, cell_y = c + 112, b + 5
    cell = split_ram.build(p, cell_x, cell_y, cell_size, cell_belts)
    if packed_cell:
        # Protocol adapter (read = bare address, write = -(addr+1), value).
        # The controller's macros speak THIS protocol, not raw split-RAM, so
        # it must sit between cc and the cell RAM exactly as in the default
        # floor. Same rows as that floor: command on b+1, expanded on cell_y-3.
        packed = packed_ram_proxy.build(p, cell_x - 20, cell_y)
        p.pipe([
            ports["cc"],
            (ports["cc"][0], b + 1),
            (packed["command"][0], b + 1),
            packed["command"],
        ])
        p.pipe([
            packed["expanded"],
            (cell_x - 3, packed["expanded"][1]),
            (cell_x - 3, cell_y - 3),
            (cell["command"][0], cell_y - 3),
            cell["command"],
        ])
    else:
        p.pipe([
            ports["cc"],
            (ports["cc"][0], b + 2),
            (cell["command"][0], b + 2),
            cell["command"],
        ])
    p.pipe([
        cell["reply"],
        cell["reply_turn"],
        (cell["reply_turn"][0], b + 3),
        (ports["cr"][0], b + 3),
        ports["cr"],
    ])


def build_program(
    flow,
    scalar_size=32,
    code_x=380,
    pooled_edges=True,
    tight_gaps=True,
    dedup_edges=True,
    coalesce_targets=True,
    queue=False,
    fast_cell_ram=False,
    cell_belts=8,
    packed_cell=False,
    fast_scalar_ram=False,
    scalar_belts=4,
    compact=False,
    cell_replicas=1,
    scalar_command_band=1,
    scalar_reply_band=3,
    scalar_display_offset=None,
    lay_fn=None,
    merge_pad=None,
    block_gap=None,
    boustrophedon=False,
    display=True,
    output_port=False,
    cell_size=256,
    queue_rows=6,
    queue_right_off=320,
):
    """Compile *flow* and attach the shared stateful-problem hardware.

    ``lay_fn`` may replace ``flowgrid.lay_cfg_controller`` while preserving
    the component assembly.  It accepts ``(program, flow, port_spec,
    code_x=...)`` and returns the usual layout dictionary.
    """
    if compact and not (fast_cell_ram and fast_scalar_ram):
        raise ValueError("compact mode requires fast_cell_ram and fast_scalar_ram")
    if compact and queue and cell_replicas > 1:
        raise ValueError("compact queue map is single-cell-RAM only")
    if compact and cell_replicas > 1:
        raise ValueError("compact mode does not support replicated cell RAM")
    if output_port and display:
        raise ValueError("output_port reuses the display band; needs display=False")
    if cell_size != 256 and not fast_cell_ram:
        raise ValueError("cell_size != 256 requires fast_cell_ram")
    base_ports = COMPACT_PORTS if compact else DEFAULT_PORTS
    p = lm.Program()
    port_spec = base_ports.copy() if queue else {
        name: spec for name, spec in base_ports.items()
        if name not in ("qs", "qr")
    }
    if compact and queue:
        port_spec.update(COMPACT_QUEUE_PORTS)
    if not display:
        for name in ("sa", "sd", "ss"):
            port_spec.pop(name, None)
    if output_port:
        port_spec["so"] = OUTPUT_PORT_COMPACT if compact else OUTPUT_PORT_DEFAULT
    if cell_replicas > 1:
        port_spec.pop("cc")
        port_spec.pop("cr")
        if queue:
            port_spec["qs"] = (602, "s")
            port_spec["qr"] = (560, "r")
        port_spec["ss"] = (150, "s")
        for replica in range(cell_replicas):
            offset = 160 + 80 * replica
            port_spec[f"c{replica}s"] = (offset, "s")
            port_spec[f"c{replica}r"] = (offset + 25, "r")
    if lay_fn is not None:
        layout = lay_fn(p, flow, port_spec, code_x=code_x)
    else:
        layout = flowgrid.lay_cfg_controller(
            p,
            flow,
            port_spec,
            code_x=code_x,
            pooled_edges=pooled_edges,
            tight_gaps=tight_gaps,
            dedup_edges=dedup_edges,
            coalesce_targets=coalesce_targets,
            local_edges=True,
            merge_pad=merge_pad,
            block_gap=block_gap,
            boustrophedon=boustrophedon,
        )
    ports = layout["ports"]
    bottom = layout["bottom"]

    if compact:
        _compact_components(
            p, ports, bottom, code_x, scalar_size, scalar_belts, cell_belts,
            cell_size=cell_size, packed_cell=packed_cell,
        )
        if queue:
            _build_queue(p, ports, bottom, code_x, queue_rows, queue_right_off,
                         cell_replicas, shift=COMPACT_QUEUE_SHIFT)
        return p

    # Components sit below the controller. All controller ports leave through
    # its bottom wall and route outside the room before entering a component.
    scalar_x, scalar_y = code_x + 48, bottom + 5
    cell_x, cell_y = code_x + (164 if packed_cell else 148), bottom + 5
    scalar = (
        split_ram.build(p, scalar_x, scalar_y, scalar_size, scalar_belts)
        if fast_scalar_ram else belt_ram.build(p, scalar_x, scalar_y, scalar_size)
    )
    if cell_replicas > 1:
        if not (fast_cell_ram and packed_cell):
            raise ValueError("replicated cell RAM requires packed split RAM")
        cell_positions = [
            (code_x + 177 + 80 * replica, cell_y)
            for replica in range(cell_replicas)
        ]
        cells = [
            split_ram.build(p, x, y, 256, cell_belts)
            for x, y in cell_positions
        ]
        packeds = [
            packed_ram_proxy.build(p, x - 20, y)
            for x, y in cell_positions
        ]
        cell = cells[0]
        packed = packeds[0]
    else:
        cell = (
            split_ram.build(p, cell_x, cell_y, cell_size, cell_belts)
            if fast_cell_ram else belt_ram.build(p, cell_x, cell_y, 256)
        )
        packed = (
            packed_ram_proxy.build(p, cell_x - 20, cell_y)
            if packed_cell else None
        )

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
    if fast_scalar_ram:
        p.pipe([
            ports["sc"],
            (ports["sc"][0], bottom + scalar_command_band),
            (command[0], bottom + scalar_command_band),
            command,
        ])
        p.pipe([
            scalar["reply"],
            scalar["reply_turn"],
            (scalar["reply_turn"][0], bottom + scalar_reply_band),
            (ports["rr"][0], bottom + scalar_reply_band),
            ports["rr"],
        ])
    else:
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
    if fast_cell_ram:
        if cell_replicas > 1:
            for replica, ((replica_x, _), replica_cell, replica_packed) in enumerate(
                zip(cell_positions, cells, packeds)
            ):
                p.pipe([
                    ports[f"c{replica}s"],
                    (ports[f"c{replica}s"][0], bottom + 1),
                    (replica_packed["command"][0], bottom + 1),
                    replica_packed["command"],
                ])
                p.pipe([
                    replica_packed["expanded"],
                    (replica_x - 3, replica_packed["expanded"][1]),
                    (replica_x - 3, cell_y - 3),
                    (replica_cell["command"][0], cell_y - 3),
                    replica_cell["command"],
                ])
                p.pipe([
                    replica_cell["reply"],
                    replica_cell["reply_turn"],
                    (replica_cell["reply_turn"][0], bottom + 3),
                    (ports[f"c{replica}r"][0], bottom + 3),
                    ports[f"c{replica}r"],
                ])
        elif packed_cell:
            p.pipe([
                ports["cc"],
                (ports["cc"][0], bottom + 1),
                (packed["command"][0], bottom + 1),
                packed["command"],
            ])
            p.pipe([
                packed["expanded"],
                (cell_x - 3, packed["expanded"][1]),
                (cell_x - 3, cell_y - 3),
                (cell["command"][0], cell_y - 3),
                cell["command"],
            ])
        else:
            p.pipe([
                ports["cc"],
                (ports["cc"][0], bottom + 2),
                (cell["command"][0], bottom + 2),
                cell["command"],
            ])
        if cell_replicas == 1:
            p.pipe([
                cell["reply"],
                cell["reply_turn"],
                (cell["reply_turn"][0], bottom + 3),
                (ports["cr"][0], bottom + 3),
                ports["cr"],
            ])
    else:
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

    # Output room (so): straight drop below the controller in the display band.
    if output_port:
        sox = ports["so"][0]
        p.output_room(sox - 1, bottom + 8)
        p.pipe([ports["so"], (sox, bottom + 7)])
    if not display:
        return p

    # Addressable 16x16 display. With the banked scalar RAM (32x32 instead of
    # the 78x43 belt) the sd feeder clears the scalar block 18 rows sooner.
    display_x = code_x + 110
    display_y = bottom + (
        scalar_display_offset
        if scalar_display_offset is not None
        else (70 if cell_replicas > 1 else (42 if fast_scalar_ram else 60))
    )
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
    swap_band = display_y + (110 if cell_replicas > 1 else 20)
    p.pipe([
        ports["ss"],
        (ports["ss"][0], swap_band),
        (display_x + 8, swap_band),
        (display_x + 8, display_y + 18),
    ])

    # Bounded FIFO service. A short command pipe feeds a relay man; the long
    # return pipe is both transport and storage. Its ~190 cells comfortably
    # exceed the maximum useful 16x16 BFS frontier, while the relay provides
    # FIFO order at pipeline throughput.
    if queue:
        _build_queue(p, ports, bottom, code_x, queue_rows, queue_right_off,
                     cell_replicas)
    return p
