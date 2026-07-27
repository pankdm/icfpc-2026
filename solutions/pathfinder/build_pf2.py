#!/usr/bin/env python3
"""Complete MEM16 Pathfinder lowered through the compact-zone CFG compiler.

This is the correctness-first integration of the oracle-proven MEM16 device.
It deliberately keeps the controller generated; once it passes end to end,
the same block streams can be folded further by ``build_micro.py``.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

import flowgrid
import littleman as lm
import boustro
from layout import Layout, pipelen
from build_micro import mem16


SENTINEL = 272
DELTAS = (-16, 1, 16, -1)


class Flow(flowgrid.Flow):
    def c16(self):
        return self.e("8", "M", "+", "M")

    def next_tag(self):
        return self.e("M", "3", "W", "%", "M", "1", "+")

    def prev_tag(self):
        return self.e("M", "1", "+", "M", "3", "W", "%", "M", "1", "+")

    def delta(self, value):
        if value == 1:
            return self.e("M", "1", "+")
        if value == -1:
            return self.e("M", "1", "N", "+")
        self.e("Ns").c16().e("Nr")
        return self.e("+" if value == 16 else "-")

    def txn(self):
        """NB ring holds index; return shifted field in A and shift in B."""
        return (
            self.c16().e("Nr", "Ns", "/", "Hs", "W", "M", "4", "*", "M", "7", "{")
            .e("Hs", "Cr")
        )

    def input_index(self):
        """Read x,y and leave 16*y+x in A, using NB for x."""
        return self.e("Ir", "Ns", "Ir", "M", "4", "W", "{", "M", "Nr", "+")

    def compare_sentinel(self):
        return self.e("Ns").const(SENTINEL).e("M", "Nr", "-")


def build_flow():
    f = Flow()

    # Setup ring contains only the current raster index.
    f.at("START").const(0).e("Ss").go("SETUP")
    f.at("SETUP")
    f.e("Sr", "Ds", "Ns", "Ir", "Ns", "M", "7", "*", "Ds")
    f.txn()
    # NB is [wall,index]. Write payload = (4*wall)<<shift.
    f.e("Nr", "{", "M", "4", "*", "Hs")
    f.e("Nr", "M", "1", "+", "Ss", "Ns").const(256).e("M", "Nr", "-")
    f.br("SETUP", "SETUP_DONE", "SETUP")

    f.at("SETUP_DONE").e("Sr").input_index()
    # State = [robot].
    f.e("Ss", "Ds").const(10).e("Ds").const(1).e("N", "Ds").go("ROUND")

    # State [robot] -> [robot,flag]. A negative command resets every non-wall
    # nibble in MEM16; the embedded hub expands it to -0x4444... itself.
    f.at("ROUND").input_index().e("Ns", "Ss")
    f.const(1).e("N", "Hs")
    # tag[flag] = 1
    f.txn().const(1).e("{", "Hs")
    # Draw and seed reverse BFS with (flag,tag=1).
    f.e("Nr", "Ds", "Ns").const(9).e("Ds")
    f.e("Nr", "Fs").const(1).e("Fs").go("BFS_POP")

    # Frontier stores cell/tag pairs. State [robot,flag] becomes
    # [cur,next_tag,robot,flag].
    f.at("BFS_POP").e("Fr", "Ss", "Fr").next_tag().e("Ss")
    f.e("Sr", "Ss", "Sr", "Ss")
    # Compare cur with robot while restoring the canonical state order.
    f.e("Sr", "Ss", "Ns", "Sr", "Ss", "Sr", "Ss", "M", "Nr", "-")
    f.e("Ns", "Sr", "Ss", "Nr")
    f.br("BFS_U", "BFS_FOUND", "BFS_U")

    for index, (name, delta) in enumerate(zip(("U", "R", "D", "L"), DELTAS)):
        busy = f"BFS_BUSY_{name}"
        free = f"BFS_FREE_{name}"
        nxt = "BFS_NEXT" if index == 3 else f"BFS_{'URDL'[index + 1]}"

        # Rotate CUR to the tail, probe NB, and leave state
        # [next_tag,robot,flag,cur].
        f.at(f"BFS_{name}").e("Sr", "Ss").delta(delta).e("Ns").txn()
        f.br(busy, free, busy)

        # Occupied: release the hub with payload zero, rotate three state
        # values, discard NB, and restore [cur,next_tag,robot,flag].
        f.at(busy).const(0).e("Hs")
        f.e("Sr", "Ss", "Sr", "Ss", "Sr", "Ss", "Nr").go(nxt)

        # Free: write the child tag, enqueue (NB,tag), then rotate robot+flag.
        f.at(free).e("Sr", "Ss", "{", "Hs", "}", "M", "Nr")
        f.e("Fs", "W", "Fs")
        f.e("Sr", "Ss", "Sr", "Ss").go(nxt)

    # The expanded cell and its child tag are per-pop temporaries. Keep only
    # the persistent [robot,flag] pair before appending the next queue item.
    f.at("BFS_NEXT").e("Sr", "Sr").go("BFS_POP")

    # [cur,tag,robot,flag] -> [robot,want,flag]. A marker is appended after
    # every older frontier value so it can be drained before the next round.
    f.at("BFS_FOUND").e("Sr")
    # The state carries the tag to assign to CUR's children, i.e. one step
    # *after* tag[CUR]. Two predecessor steps therefore produce the tag wanted
    # by the first downhill move.
    f.e("Sr").prev_tag().prev_tag().e("Ns")
    f.e("Sr", "Ss", "Sr", "Ns", "Nr", "Ss", "Nr", "Ss")
    f.const(SENTINEL).e("Fs").go("WALK_U")

    for index, (name, delta) in enumerate(zip(("U", "R", "D", "L"), DELTAS)):
        next_probe = "NO_PARENT" if index == 3 else f"WALK_{'URDL'[index + 1]}"
        mismatch = f"WALK_MISS_{name}"
        match = f"MOVE_{name}"

        # State [robot,want,flag]. Rotate robot, probe NB, save the returned
        # field behind NB, rotate want+flag, then compare shifted tag values.
        f.at(f"WALK_{name}").e("Sr", "Ss").delta(delta).e("Ns").txn().e("Ns")
        f.e("Sr", "Ss", "{", "M", "Sr", "Ss")
        f.e("Nr", "Ns", "Nr", "~", "M").const(0).e("Hs", "W")
        f.br(mismatch, match, mismatch)

        # Mismatch only needs to discard the staged NB.
        f.at(mismatch).e("Nr").go(next_probe)

        # Move one step. NB survives display writes; rebuild state as
        # [new_robot,new_want,flag], then test whether the flag was reached.
        f.at(match).e("Sr", "Ds").const(0).e("Ds")
        f.e("Nr", "Ns", "Ds").const(10).e("Ds").const(1).e("N", "Ds")
        f.e("Sr").prev_tag().e("Ns", "Sr", "Ns")
        f.e("Nr", "M", "Ss", "Nr", "Ss", "Nr", "Ss", "-")
        f.br("WALK_U", "ROUND_FINISH", "WALK_U")

    # All real tags have a predecessor; reaching this block means corruption.
    f.at("NO_PARENT").e("H")

    # State [robot,want,old_flag] -> [robot]. Drain every stale frontier value
    # through the unique marker, then consume the next round.
    f.at("ROUND_FINISH").e("Sr", "Ss", "Sr", "Sr").go("DRAIN_FRONTIER")
    f.at("DRAIN_FRONTIER").e("Fr").compare_sentinel().br(
        "DRAIN_FRONTIER", "ROUND", "DRAIN_FRONTIER"
    )
    return f


class OneRingFlow(Flow):
    """Lower STATE and NB onto one FIFO with explicit cyclic rotations."""

    def rotate(self, count):
        for _ in range(count):
            self.e("Sr", "Ss")
        return self

    def delta1(self, value, state_count):
        if abs(value) == 1:
            return self.e(*(
                ("M", "1", "N", "+") if value < 0 else ("M", "1", "+")
            ))
        # Park the base behind the persistent state, build 16, rotate the
        # state once, then recover the base with B still equal to 16.
        self.e("Ss").c16().rotate(state_count).e("Sr")
        return self.e("+" if value == 16 else "-")

    def txn1(self, state_count, keep_index):
        """Probe A, optionally leaving the index behind persistent state."""
        return self.txn1_start(state_count, keep_index).e("Cr")

    def txn1_start(self, state_count, keep_index):
        """Send q/mask, leaving B=shift before payload and reply."""
        self.e("Ss").c16().rotate(state_count).e("Sr")
        if keep_index:
            self.e("Ss")
        return self.e("/", "Hs", "W", "M", "4", "*", "M", "7", "{", "Hs")


def build_flow_one_ring(eager_payload=False):
    f = OneRingFlow()

    f.at("START").const(0).e("Ss").go("SETUP")
    f.at("SETUP")
    # STATE [i] -> [i,wall], then probe i while retaining both values.
    f.e("Sr", "Ds", "Ss", "Ir", "Ss", "M", "7", "*", "Ds")
    f.e("Sr")
    (f.txn1_start(1, True) if eager_payload else f.txn1(1, True))
    # STATE [wall,i].  Write (4*wall)<<shift, advance i, and compare 256.
    f.e("Sr", "{", "M", "4", "*", "Hs")
    if eager_payload:
        f.e("Cr")
    f.e("Sr", "M", "1", "+", "Ss")
    f.const(256).e("M", "Sr", "Ss", "-")
    f.br("SETUP", "SETUP_DONE", "SETUP")

    f.at("SETUP_DONE").e("Sr")
    # Empty STATE: read x,y and leave robot in the ring.
    f.e("Ir", "Ss", "Ir", "M", "4", "W", "{", "M", "Sr", "+", "Ss", "Ds")
    f.const(10).e("Ds").const(1).e("N", "Ds").go("ROUND")

    # STATE [robot] -> [robot,flag].
    f.at("ROUND").e("Ir", "Ss", "Ir", "M", "4", "W", "{", "M")
    f.e("Sr", "Ss", "Sr", "+", "Ss")
    f.const(1).e("N", "Hs")
    # Probe/write the flag without retaining a second scratch copy.
    f.rotate(1).e("Sr", "Ss")
    if eager_payload:
        f.txn1_start(2, False).const(1).e("{", "Hs", "Cr")
    else:
        f.txn1(2, False).const(1).e("{", "Hs")
    # Rotate robot, take/reappend flag, draw it, and seed (flag,tag=1).
    f.rotate(1).e("Sr", "Ss", "Ds").const(9).e("Ds")
    f.rotate(1).e("Sr", "Ss", "Fs").const(1).e("Fs").go("BFS_POP")

    # STATE [robot,flag] -> [cur,next_tag,robot,flag].
    f.at("BFS_POP").e("Fr", "Ss", "Fr").next_tag().e("Ss")
    f.rotate(2)
    # Compare CUR with robot.  Reappend both values before branching; the
    # resulting [flag,cur,next_tag,robot] is one rotation from canonical.
    f.e("Sr", "Ss", "M", "Sr", "Ss", "Sr", "Ss", "-")
    f.br("BFS_NOT_FOUND", "BFS_FOUND_ENTRY", "BFS_NOT_FOUND")
    f.at("BFS_NOT_FOUND").rotate(1).go("BFS_U")
    f.at("BFS_FOUND_ENTRY").rotate(1).go("BFS_FOUND")

    for index, (name, delta) in enumerate(zip(("U", "R", "D", "L"), DELTAS)):
        busy = f"BFS_BUSY_{name}"
        free = f"BFS_FREE_{name}"
        nxt = "BFS_NEXT" if index == 3 else f"BFS_{'URDL'[index + 1]}"

        # Rotate CUR to the tail. txn1 leaves NB after the four persistent
        # values: [next_tag,robot,flag,cur,nb].
        f.at(f"BFS_{name}").e("Sr", "Ss").delta1(delta, 4)
        if eager_payload:
            # Rotate NEXT_TAG once while materializing the eager payload.
            # B retains the unshifted tag across Cr for the free path.
            f.txn1_start(4, True).e("Sr", "Ss", "{", "Hs", "}", "M", "Cr")
        else:
            f.txn1(4, True)
        f.br(busy, free, busy)

        # Drop the tail scratch, then rotate next_tag/robot/flag to restore
        # [cur,next_tag,robot,flag].
        f.at(busy)
        if eager_payload:
            f.rotate(3).e("Sr").rotate(3)
        else:
            f.const(0).e("Hs").rotate(4).e("Sr").rotate(3)
        f.go(nxt)

        # Consume next_tag for the payload.  The resulting order places NB
        # after robot/flag/cur, so three rotations recover it directly.
        f.at(free)
        if not eager_payload:
            f.e("Sr", "Ss", "{", "Hs", "}", "M")
        f.rotate(3).e("Sr", "Fs", "W", "Fs").rotate(3).go(nxt)

    f.at("BFS_NEXT").e("Sr", "Sr").go("BFS_POP")

    # [cur,next_tag,robot,flag] -> [robot,want,flag], using B as the only
    # temporary needed to swap want ahead of flag.
    f.at("BFS_FOUND").e("Sr", "Sr").prev_tag().prev_tag().e("M")
    f.e("Sr", "Ss", "Sr", "W", "Ss", "W", "Ss")
    f.const(SENTINEL).e("Fs").go("WALK_U")

    for index, (name, delta) in enumerate(zip(("U", "R", "D", "L"), DELTAS)):
        next_probe = "NO_PARENT" if index == 3 else f"WALK_{'URDL'[index + 1]}"
        mismatch = f"WALK_MISS_{name}"
        match = f"MOVE_{name}"

        # [robot,want,flag] -> [want,flag,robot,nb].  Decode the shifted
        # field in-place and compare it with want.
        f.at(f"WALK_{name}").e("Sr", "Ss").delta1(delta, 3)
        if eager_payload:
            f.txn1_start(3, True).const(0).e("Hs", "Cr")
        else:
            f.txn1(3, True)
        f.e("}", "M", "Sr", "Ss", "~", "M")
        if not eager_payload:
            f.const(0).e("Hs")
        f.e("W").br(mismatch, match, mismatch)

        # Drop NB and restore [robot,want,flag].
        f.at(mismatch).rotate(2).e("Sr").rotate(2).go(next_probe)

        # Recover NB, park it behind want/flag while drawing, then rebuild
        # [nb,new_want,flag].  The comparison rotates that to
        # [new_want,flag,nb], which each successor handles explicitly.
        f.at(match).rotate(2).e("Sr", "M").rotate(2).e("Sr", "Ds")
        f.const(0).e("Ds")
        f.e("W", "Ss", "Ds").const(10).e("Ds").const(1).e("N", "Ds")
        f.e("Sr").prev_tag().e("M", "Sr", "W", "Ss", "W", "Ss")
        f.e("M", "Sr", "Ss", "-")
        f.br("MOVE_CONTINUE", "ROUND_FINISH", "MOVE_CONTINUE")

    f.at("MOVE_CONTINUE").rotate(2).go("WALK_U")
    f.at("NO_PARENT").e("H")

    # Zero branch arrives as [new_want,flag,robot]; retain only robot.
    f.at("ROUND_FINISH").e("Sr", "Sr").go("DRAIN_FRONTIER")
    f.at("DRAIN_FRONTIER").e("Fr", "Ss").const(SENTINEL).e("M")
    f.rotate(1).e("Sr", "-")
    f.br("DRAIN_FRONTIER", "ROUND", "DRAIN_FRONTIER")
    return f


PORTS = {
    # Zone edges are the exact Manhattan Voronoi boundaries of the pipe
    # terminals. Incoming and outgoing bindings are independent.
    "Hs": (10, "s", 1, 25), "Cr": (5, "r", 1, 30),
    "Ss": (40, "s", 26, 55), "Sr": (45, "r", 31, 60),
    "Fs": (70, "s", 56, 82), "Fr": (75, "r", 61, 87),
    "Ns": (95, "s", 83, 120), "Nr": (100, "r", 88, 112),
    "Ir": (125, "r", 113, 155), "Ds": (15, "s", 13, 27),
}


def _relay(program, x, y):
    program.room(x, y, 8, 6)
    program.text(x + 1, y + 1, "@>Rsv")
    program.put(x + 5, y + 2, "<")
    program.put(x + 2, y + 2, "^")


def _short_ring(program, send, recv, x, y, depth=5):
    _relay(program, x, y)
    program.pipe([send, (send[0], y - 2), (x + 3, y - 2), (x + 3, y - 1)])
    low = y + 6 + depth
    # Return outside the relay's right wall; a direct U at recv.x would cut
    # back through the room whenever recv.x lies over its top wall.
    program.pipe([
        (x + 4, y + 6), (x + 4, low), (x + 9, low),
        (x + 9, y - 3), (recv[0], y - 3), recv,
    ])


def _side_ring(
    program,
    send,
    recv,
    x,
    y,
    bottom,
    feed_lane,
    return_lane,
    send_drop,
    return_drop,
):
    """Relay ring folded into the free right apron of the controller."""
    _relay(program, x, y)
    program.pipe([
        send,
        (send[0], bottom + send_drop),
        (feed_lane, bottom + send_drop),
        (feed_lane, y - 3),
        (x + 3, y - 3),
        (x + 3, y - 1),
    ])
    points = [
        (x + 4, y + 6),
        (x + 4, y + 8),
        (return_lane, y + 8),
        (return_lane, bottom + return_drop),
        (recv[0], bottom + return_drop),
        recv,
    ]
    program.pipe(points)
    return pipelen(points)


def _tight_state_ring(program, send, recv, drop=3, lift=2):
    """Minimal STATE ring hung directly under the controller's own port columns.

    `_short_ring` pays ~30 cells of lap because its relay sits five rows down and
    its return detours around the relay's right wall.  The state ring's columns
    (Ss..Sr) lie strictly between the memory trunks (which end at Hs) and the
    input/display trunks (which start at Ir), so both legs can run straight down
    and straight back up with nothing in the way.

    Ring capacity = entry pipe + exit pipe cells; the one-ring protocol holds at
    most five values, so `drop` must stay >= 3.
    """
    ss, bottom = send
    sr = recv[0]
    assert sr > ss + 1, (ss, sr)
    y0 = bottom + drop                      # relay room top wall
    assert drop >= lift + 2, (drop, lift)
    # entry: straight down from the controller's bottom wall into the relay's.
    program.pipe([send, (ss, y0 - 1)])
    # relay: '@ > R s v' on the first interior row, '<'/'^' returning below it.
    x0 = ss - 3
    width = (sr - ss) + 6
    program.room(x0, y0, width, 4)
    program.text(x0 + 1, y0 + 1, "@>Rsv")
    program.put(x0 + 5, y0 + 2, "<")
    program.put(x0 + 2, y0 + 2, "^")
    # exit: leaves beside the entry (so `s` binds to it, not to the incoming
    # pipe), climbs to a free row and steps across to the recv column.
    out_x = x0 + 5                          # = ss + 2
    lane = bottom + lift
    program.pipe([
        (out_x, y0 - 1), (out_x, lane), (sr, lane), recv,
    ])


def _frontier_ring(
    program, send, recv, x, y, rows=15, left_span=2, right_span=8
):
    """A narrow folded return pipe; depth is paid vertically, not in lanes."""
    assert rows >= 1 and rows % 2 == 1
    _relay(program, x, y)
    program.pipe([send, (send[0], y - 2), (x + 3, y - 2), (x + 3, y - 1)])
    left, right = x - left_span, x + right_span
    points = [(x + 4, y + 6), (x + 4, y + 8), (left, y + 8)]
    at = left
    last_y = y + 8 + rows
    for row in range(y + 9, last_y + 1):
        points.append((at, row))
        far = right if at == left else left
        points.append((far, row))
        at = far
    exit_x = right + 2
    points.extend([
        (exit_x, last_y),
        (exit_x, y - 3),
        (recv[0], y - 3),
        recv,
    ])
    program.pipe(points)
    return pipelen(points)


def _add_driver(program, controller_port, x, y, controller_pipe=None):
    """Snake's proven one-pipe address/data/commit display driver."""
    display_x = x + 11
    program.room(x, y, 9, 22)
    program.display(display_x, y + 2, 18, 18)
    dx, dy = x - 38, y - 10
    for px, py, ch in [
        (43, 29, "@"), (39, 12, ">"), (40, 12, "r"), (42, 12, "v"),
        (42, 13, "X"), (41, 13, "^"), (42, 14, "<"), (41, 14, "^"),
        (41, 11, ">"), (44, 11, "s"), (45, 11, "v"), (45, 19, "r"),
        (45, 20, "s"), (45, 29, "<"), (39, 29, "^"), (43, 13, "1"),
        (44, 13, "v"), (44, 30, "<"), (41, 30, "s"), (39, 30, "^"),
    ]:
        program.put(px + dx, py + dy, ch)
    # When the driver is to the right of its controller port, turn immediately
    # in the empty apron. This keeps the display pipe from crossing the
    # left-going MEM16 command pipe.
    if controller_pipe is None:
        turn_y = y - 19 if x - 2 > controller_port[0] else y - 6
        controller_pipe = [
            controller_port,
            (controller_port[0], turn_y),
            (x - 2, turn_y),
            (x - 2, y + 2),
            (x - 1, y + 2),
        ]
    program.pipe(controller_pipe)
    program.pipe([
        (47 + dx, 11 + dy), (48 + dx, 11 + dy), (48 + dx, 10 + dy),
        (display_x + 3, 10 + dy), (display_x + 3, 11 + dy),
    ])
    program.pipe([(47 + dx, 20 + dy), (display_x - 1, 20 + dy)])
    program.pipe([
        (41 + dx, 32 + dy), (41 + dx, 33 + dy),
        (display_x + 4, 33 + dy), (display_x + 4, 30 + dy),
    ])


def build(
    code_x=65,
    boustrophedon=True,
    dense=True,
    frontier_rows=1,
    display_col=None,
    memory_send_col=None,
    driver_x=0,
    ring_shift=0,
    op_slack=6,
    port_base=15,
    port_percent=39,
    side_apron=False,
    tight_apron=True,
    merge_nb=False,
    centered_hub=False,
    memory_y=20,
    eager_payload=False,
    port_cols=None,
    tight_state_ring=0,
):
    p = lm.Program()
    flow = build_flow_one_ring(eager_payload) if merge_nb else build_flow()
    port_spec = {}
    for name, spec in PORTS.items():
        if merge_nb and name in ("Ns", "Nr"):
            continue
        if port_cols and name in port_cols:
            col = port_cols[name]
        else:
            old_col = code_x + spec[0]
            col = port_base + round((old_col - 70) * port_percent / 100)
        port_spec[name] = (col - code_x, spec[1], 1, 10**9)
    if display_col is not None:
        port_spec["Ds"] = (display_col - code_x, "s", 1, 10**9)
    if memory_send_col is not None:
        port_spec["Hs"] = (memory_send_col - code_x, "s", 1, 10**9)
    if side_apron:
        # Keep the input return outside every side-apron trunk.  Input is cold,
        # so its wider binding lane costs almost no controller time.
        port_spec["Ir"] = (125 - code_x, "r", 1, 10**9)
        # The display trunk sits to the right of every ring return.  Keeping its
        # controller port there makes the exterior matching planar.
        port_spec["Ds"] = (75 - code_x, "s", 1, 10**9)
    if tight_apron:
        tight_display_col = 77 if display_col is None else display_col
        port_spec["Ds"] = (tight_display_col - code_x, "s", 1, 10**9)
    # Explicit columns win over every heuristic override above.
    for name, col in (port_cols or {}).items():
        if name in port_spec:
            port_spec[name] = (col - code_x, port_spec[name][1], 1, 10**9)
    if dense:
        layout = boustro.lay_cfg_boustrophedon(
            p,
            flow,
            port_spec,
            code_x=code_x,
            op_slack=op_slack,
            tight_width=True,
        )
    else:
        layout = flowgrid.lay_cfg_controller(
            p,
            flow,
            port_spec,
            code_x=code_x,
            pooled_edges=True,
            tight_gaps=True,
            dedup_edges=True,
            coalesce_targets=True,
            local_edges=True,
            boustrophedon=boustrophedon,
        )
    ports, bottom = layout["ports"], layout["bottom"]

    # MEM16 sits beside the controller. Its 106-row height is thereby paid in
    # parallel with controller code instead of being added below it.
    L = Layout(p)
    memory_x = -58
    memory_wrow = 7 if eager_payload else 6
    memory = mem16(
        L,
        memory_x,
        memory_y,
        WROW=memory_wrow,
        centered=centered_hub,
        eager_payload=eager_payload,
    )
    # The hub accepts its sole command pipe through the bottom wall. The
    # collector similarly sends through its bottom wall.
    hub_end = (memory_x + 20, memory["bottom"] + 1)
    collector_bottom = memory_y + 6 + memory_wrow * 16 - 1
    coll_start = (memory_x + 53, collector_bottom + 1)
    p.pipe([
        ports["Hs"], (ports["Hs"][0], bottom + 3),
        (hub_end[0], bottom + 3), hub_end,
    ])
    p.pipe([
        coll_start, (coll_start[0], bottom + 2),
        (ports["Cr"][0], bottom + 2), ports["Cr"],
    ])

    if side_apron:
        # Ordered top-to-bottom like the controller's S/F/N ports.  Feed lanes
        # run in reverse x order and return lanes likewise, which keeps every
        # horizontal turn clear of the other vertical trunks.
        _side_ring(
            p, ports["Ss"], ports["Sr"], 100, 110, bottom,
            114, 120, 3, 8,
        )
        _side_ring(
            p, ports["Fs"], ports["Fr"], 100, 140, bottom,
            112, 118, 2, 7,
        )
        _side_ring(
            p, ports["Ns"], ports["Nr"], 100, 170, bottom,
            110, 116, 1, 6,
        )

        p.input_room(ports["Ir"][0] - 1, bottom + 12)
        p.pipe([(ports["Ir"][0], bottom + 11), ports["Ir"]])
        driver_x, driver_y = 135, 20
        _add_driver(
            p,
            ports["Ds"],
            driver_x,
            driver_y,
            [
                ports["Ds"],
                (ports["Ds"][0], bottom + 4),
                (driver_x - 2, bottom + 4),
                (driver_x - 2, driver_y + 2),
                (driver_x - 1, driver_y + 2),
            ],
        )
    elif tight_apron:
        apron_y = bottom + 5
        state_x = ports["Ss"][0] - 5 + ring_shift
        frontier_x = ports["Fs"][0] - 5 + ring_shift
        nb_x = ports["Ns"][0] - 3 + ring_shift if not merge_nb else None
        if tight_state_ring:
            _tight_state_ring(p, ports["Ss"], ports["Sr"],
                              drop=tight_state_ring, lift=2)
        else:
            _short_ring(p, ports["Ss"], ports["Sr"], state_x, apron_y, 1)
        _frontier_ring(
            p,
            ports["Fs"],
            ports["Fr"],
            frontier_x,
            apron_y,
            frontier_rows,
            left_span=50,
        )
        if not merge_nb:
            _short_ring(p, ports["Ns"], ports["Nr"], nb_x, apron_y, 1)

        p.input_room(ports["Ir"][0] - 1, bottom + 4)
        p.pipe([(ports["Ir"][0], bottom + 3), ports["Ir"]])
        # Keep the driver's left-side trunk strictly beyond the controller's
        # right wall. Wider four-lane layouts otherwise overwrite the bottom
        # wall where that trunk used to cross at x=86.
        driver_x, driver_y = max(88, layout["width"] + 4), 20
        _add_driver(
            p,
            ports["Ds"],
            driver_x,
            driver_y,
            [
                ports["Ds"],
                (ports["Ds"][0], bottom + 1),
                (driver_x - 2, bottom + 1),
                (driver_x - 2, driver_y + 2),
                (driver_x - 1, driver_y + 2),
            ],
        )
    else:
        state_x = ports["Ss"][0] - 5 + ring_shift
        frontier_x = ports["Fs"][0] - 5 + ring_shift
        nb_x = ports["Ns"][0] - 5 + ring_shift
        _short_ring(p, ports["Ss"], ports["Sr"], state_x, bottom + 20, 5)
        _frontier_ring(
            p,
            ports["Fs"],
            ports["Fr"],
            frontier_x,
            bottom + 20,
            frontier_rows,
        )
        _short_ring(p, ports["Ns"], ports["Nr"], nb_x, bottom + 20, 3)

        p.input_room(ports["Ir"][0] - 1, bottom + 12)
        p.pipe([(ports["Ir"][0], bottom + 11), ports["Ir"]])
        _add_driver(p, ports["Ds"], driver_x, bottom + 20)
    return p


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-x", type=int, default=65)
    parser.add_argument("--no-boustrophedon", action="store_true")
    parser.add_argument("--no-dense", action="store_true")
    parser.add_argument("--frontier-rows", type=int, default=1)
    parser.add_argument("--display-col", type=int)
    parser.add_argument("--memory-send-col", type=int)
    parser.add_argument("--driver-x", type=int, default=0)
    parser.add_argument("--ring-shift", type=int, default=0)
    parser.add_argument("--op-slack", type=int, default=6)
    parser.add_argument("--port-base", type=int, default=15)
    parser.add_argument("--port-percent", type=int, default=39)
    parser.add_argument("--side-apron", action="store_true")
    parser.add_argument("--tight-apron", dest="tight_apron", action="store_true")
    parser.add_argument("--no-tight-apron", dest="tight_apron", action="store_false")
    parser.add_argument("--merge-nb", action="store_true")
    parser.add_argument("--centered-hub", action="store_true")
    parser.add_argument("--memory-y", type=int, default=20)
    parser.add_argument("--eager-payload", action="store_true")
    parser.add_argument(
        "--tight-state-ring", type=int, default=0,
        help="drop (rows below the controller) for the minimal STATE relay; "
             "0 keeps the original _short_ring")
    parser.add_argument(
        "--port-cols", default=None,
        help="explicit absolute controller port columns, e.g. "
             "'Cr=12,Hs=15,Ss=32,Sr=35,Fs=49,Fr=52,Ir=80,Ds=81'")
    parser.set_defaults(tight_apron=True)
    parser.add_argument(
        "--output", default=os.path.join(HERE, "mem16-flow-v1.man")
    )
    args = parser.parse_args()
    pcols = None
    if args.port_cols:
        pcols = {}
        for part in args.port_cols.split(","):
            k, v = part.split("=")
            pcols[k.strip()] = int(v)
    program = build(
        args.code_x,
        not args.no_boustrophedon,
        not args.no_dense,
        args.frontier_rows,
        args.display_col,
        args.memory_send_col,
        args.driver_x,
        args.ring_shift,
        args.op_slack,
        args.port_base,
        args.port_percent,
        args.side_apron,
        args.tight_apron,
        args.merge_nb,
        args.centered_hub,
        args.memory_y,
        args.eager_payload,
        pcols,
        args.tight_state_ring,
    )
    program.save(args.output)
    print("saved", args.output, "footprint", program.footprint())
