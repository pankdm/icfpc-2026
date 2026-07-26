"""Drop-in multi-belt RAM server adapted from solutions/memory/split_belts.py."""

import importlib.util
import os


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO, "solutions", "memory", "split_belts.py")


def _load_source():
    spec = importlib.util.spec_from_file_location("_littleman_split_belts", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _add_controller(source, program, belt_count, block_size):
    """Variant of split_belts.add_controller with synthesized bank counts."""
    bottom = 15 + 4 * belt_count
    program.room(0, 10, 15, bottom - 9)
    count_ops = str(belt_count) if belt_count < 10 else (
        "8M+" if belt_count == 16 else None
    )
    if count_ops is None:
        raise ValueError(f"no compact count synthesis for {belt_count} belts")
    program.text(1, 11, f"vrbW/rW{count_ops}<S<")
    source.put_non_spaces(program, 1, 12, ("W > Ws  ^ 0",))
    worker = (
        "> b> rdWXvdv<",
        "   ^ms< sWmsW",
        "    >sv 0s^<b",
        "  ^sXr<W<<>W^",
    )
    for belt in range(belt_count):
        top = 13 + 4 * belt
        source.put_non_spaces(program, 1, top, worker)
        if belt + 1 < belt_count:
            program.put(2, top, "d")
            program.put(2, top + 1, "m")
            program.put(1, top + 3, "v")
            program.put(2, top + 3, "<")
    init_y = 13 + 4 * belt_count
    program.put(4, init_y, ">")
    program.text(6, init_y, f"`{block_size}`")
    program.put(10, init_y, "W")
    program.put(11, init_y, "^")
    program.put(12, init_y, "@")
    program.put(13, init_y, "v")
    program.text(4, init_y + 1, "^W***W*M9<")


def build(program, ox, oy, size=256, belt_count=8):
    """Stamp a multi-belt RAM and return external command/reply endpoints.

    Protocol is identical to ``belt_ram``: ``[0,address]`` reads and
    ``[1,address,value]`` writes. The original problem I/O rooms are removed;
    the input/output proxy rooms become pipe-facing server ports.
    """
    source = _load_source()
    source.CELL_COUNT = size
    block_size = (size + belt_count - 1) // belt_count
    component = source.lm.Program()
    source.add_input_proxy(component)
    source.add_output_proxy(component)
    source.add_io(component)
    _add_controller(source, component, belt_count, block_size)
    for belt in range(belt_count):
        source.add_relay(component, 16 + 4 * belt)
    source.verify_belt_routing(belt_count)
    for belt in range(belt_count):
        source.add_belt_pipes(component, belt)

    # Remove the original 3x3 I and O rooms plus their two-cell pipes.
    for x in range(6, 9):
        for y in range(0, 3):
            component.put(x, y, " ")
        for y in range(5, 8):
            component.put(x, y, " ")
    for point in ((6, 3), (6, 4), (7, 4), (8, 4)):
        component.put(*point, " ")

    for (x, y), glyph in component.cells.items():
        if glyph != " ":
            cur = program.get(ox + x, oy + y)
            if cur not in (" ", glyph):
                raise ValueError(
                    f"split RAM collision at {(ox + x, oy + y)}: "
                    f"{cur!r} vs {glyph!r}"
                )
            program.put(ox + x, oy + y, glyph)

    # Command enters the top of the input-proxy room. Reply starts by leaving
    # the output-proxy room westward, then may turn north at x=7.
    return {
        "command": (ox + 3, oy - 1),
        "reply": (ox + 8, oy + 4),
        "reply_turn": (ox + 7, oy + 4),
    }
