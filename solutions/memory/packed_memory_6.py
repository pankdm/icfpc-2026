"""Generate a large proof-of-concept six-tick packed memory pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .direct_memory import draw_room, normalize_rows
except ImportError:
    from direct_memory import draw_room, normalize_rows


BLOCKS = 4
LOCAL_WORKERS = 32
VALID_LOCAL_WORKERS = 25
VALUE_OFFSET = 9 << 18
PACKING_BASE = 100
PIPE_LENGTH = 2

PARSER_LEFT = 5
PARSER_TOP = 0
MEGABLOCK_LEFT = 5
MEGABLOCK_STRIDE = 80
MEGABLOCK_TOP = 23
DISPATCH_WIDTH = 61
TRIMMED_DISPATCH_WIDTH = 46
DISPATCH_HEIGHT = 84
MEMORY_LEFT_IN_BLOCK = 65

FOLDED_HEADER = (
    "  @4Mv",
    "vYrvr<",
    "/^ <  ",
    ">Wb  v",
)

FOLDED_CHECKS = (
    (
        "v   a<",
        "    H ",
        "      ",
        "v     ",
    ),
    (
        "v  amd",
        "   H H",
        "      ",
        "v     ",
    ),
    (
        "  Hamd",
        "   m H",
        "  Hd  ",
        "v  <  ",
    ),
    (
        "  Hamd",
        "   m H",
        "v  d  ",
        "v  H  ",
    ),
)

FOLDED_ACCEPT = ("`", "2", "5", "`", "W", "/", "W", "b", "W")


def blank_interior(width: int, height: int) -> list[list[str]]:
    return [[" "] * width for _ in range(height)]


def put(canvas: list[list[str]], x: int, y: int, instruction: str) -> None:
    current = canvas[y][x]
    if current != " " and current != instruction:
        raise ValueError(
            f"instruction collision at {(x, y)}: {current!r} versus {instruction!r}"
        )
    canvas[y][x] = instruction


def put_text(canvas: list[list[str]], x: int, y: int, text: str) -> None:
    for offset, instruction in enumerate(text):
        if instruction != " ":
            put(canvas, x + offset, y, instruction)


def finish_interior(canvas: list[list[str]]) -> tuple[str, ...]:
    return tuple("".join(row) for row in canvas)


def build_parser(direct_fanout: bool = False) -> tuple[str, ...]:
    canvas = blank_interior(141, 11)
    send = "S" if direct_fanout else "s"

    put(canvas, 4, 2, "Y")
    put(canvas, 3, 2, "v")
    put(canvas, 3, 3, "v")
    put(canvas, 3, 4, ">")
    put(canvas, 4, 4, "^")
    put(canvas, 4, 3, "r")

    put_text(canvas, 0, 10, "@1NM^")
    for y in range(5, 10):
        put(canvas, 4, y, "^")

    put(canvas, 5, 2, "X")

    put(canvas, 6, 2, "r")
    put(canvas, 7, 2, "W")
    put(canvas, 8, 2, "v")
    put(canvas, 8, 10, ">")
    put(canvas, 20, 10, "W")
    for x in range(21, 121):
        put(canvas, x, 10, "+")
    put(canvas, 135, 10, send)
    put(canvas, 136, 10, "H")

    put(canvas, 5, 3, "r")
    put(canvas, 5, 4, "M")
    put(canvas, 5, 5, "r")
    put(canvas, 5, 6, ">")
    put(canvas, 24, 6, "W")
    for x in range(25, 125):
        put(canvas, x, 6, "+")
    put(canvas, 125, 6, "W")
    put_text(canvas, 126, 6, f"`{PACKING_BASE * VALUE_OFFSET}`")
    put(canvas, 137, 6, "W")
    put(canvas, 138, 6, "+")
    put(canvas, 139, 6, send)
    put(canvas, 140, 6, "H")

    return finish_interior(canvas)


def build_sync_parser() -> tuple[str, ...]:
    canvas = blank_interior(69, 5)

    put_text(canvas, 3, 0, "vYXrW")
    put(canvas, 17, 0, "W")
    for x in range(18, 68):
        put(canvas, x, 0, "+")
    put(canvas, 68, 0, "v")

    put_text(canvas, 3, 1, "vrr")
    put_text(canvas, 7, 1, "HS")
    for x in range(18, 68):
        put(canvas, x, 1, "+")
    put(canvas, 68, 1, "<")

    put_text(canvas, 3, 2, ">^M>W")
    put_text(canvas, 8, 2, f"`{PACKING_BASE * VALUE_OFFSET}`W+SH")

    put_text(canvas, 4, 3, "^r^")
    for x in range(7, 57):
        put(canvas, x, 3, "+")
    put(canvas, 57, 3, "<")

    put_text(canvas, 0, 4, "@1NM^>W")
    for x in range(7, 57):
        put(canvas, x, 4, "+")
    put(canvas, 57, 4, "^")
    return finish_interior(canvas)


def build_fanout(width: int) -> tuple[str, ...]:
    canvas = blank_interior(width, 4)
    put_text(canvas, 0, 1, "@rvrYSH")
    put(canvas, 2, 2, ">")
    put(canvas, 4, 2, "^")
    return finish_interior(canvas)


def draw_filter(
    canvas: list[list[str]], block_id: int, start_x: int, start_y: int
) -> tuple[int, int]:
    x = start_x
    y = start_y
    for _ in range(block_id):
        put(canvas, x, y, "d")
        put(canvas, x + 1, y, "H")
        put(canvas, x, y + 1, "m")
        put(canvas, x, y + 2, ">")
        x += 1
        y += 2

    put(canvas, x, y, "d")
    put(canvas, x, y + 1, "H")
    return x, y


def draw_routing_tree(
    canvas: list[list[str]], root_x: int, root_y: int, horizontal_step: int = 2
) -> tuple[int, tuple[int, ...]]:
    nodes = [(root_x, root_y)]
    offsets = (16, 8, 4, 2)
    for offset in offsets:
        next_nodes: list[tuple[int, int]] = []
        for x, y in nodes:
            put(canvas, x, y, "x")
            for direction in (-1, 1):
                child_y = y + direction * offset
                put(canvas, x, y + direction, "]")
                put(canvas, x, child_y, ">")
                next_nodes.append((x + horizontal_step, child_y))
        nodes = next_nodes

    leaves: list[int] = []
    for x, y in nodes:
        put(canvas, x, y, "x")
        for direction in (-1, 1):
            leaf_y = y + direction
            put(canvas, x, leaf_y, "s")
            put(canvas, x, leaf_y + direction, "H")
            leaves.append(leaf_y)
    return nodes[0][0], tuple(sorted(leaves))


def build_dispatcher(
    block_id: int, width: int = DISPATCH_WIDTH, packed_tree: bool = False
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    canvas = blank_interior(width, DISPATCH_HEIGHT)

    put_text(canvas, 0, 10, "@4MrvrY/WbW")
    put(canvas, 4, 11, ">")
    put(canvas, 6, 11, "^")

    final_x, final_y = draw_filter(canvas, block_id, 20, 10)
    accepted = "W`25`W/WbW"
    put_text(canvas, final_x + 1, final_y, accepted)
    sequence_end_x = final_x + len(accepted)

    turn_x = 40
    put(canvas, turn_x, final_y, "v")
    root_y = 50
    put(canvas, turn_x, root_y, ">")
    horizontal_step = 1 if packed_tree else 2
    root_x = turn_x + horizontal_step
    _, leaves = draw_routing_tree(
        canvas,
        root_x,
        root_y,
        horizontal_step=horizontal_step,
    )

    expected_leaves = tuple(range(19, 83, 2))
    if leaves != expected_leaves:
        raise ValueError(f"unexpected routing leaves: {leaves}")
    if sequence_end_x >= turn_x:
        raise ValueError("filter sequence overlaps its route")
    return finish_interior(canvas), leaves


def build_folded_dispatcher(
    block_id: int,
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    canvas = blank_interior(6, DISPATCH_HEIGHT)
    header_top = 13
    for y, row in enumerate(FOLDED_HEADER):
        put_text(canvas, 0, header_top + y, row)
    check_top = header_top + len(FOLDED_HEADER)
    for offset, row in enumerate(FOLDED_CHECKS[block_id]):
        put_text(canvas, 0, check_top + offset, row)
    accept_top = check_top + len(FOLDED_CHECKS[block_id])
    for offset, instruction in enumerate(FOLDED_ACCEPT):
        put(canvas, 0, accept_top + offset, instruction)

    root_y = 50
    put(canvas, 0, root_y, ">")
    _, leaves = draw_routing_tree(
        canvas,
        1,
        root_y,
        horizontal_step=1,
    )
    expected_leaves = tuple(range(19, 83, 2))
    if leaves != expected_leaves:
        raise ValueError(f"unexpected folded routing leaves: {leaves}")
    return finish_interior(canvas)[header_top:-1], tuple(
        leaf - header_top for leaf in leaves
    )


MEMORY_WORKER_TOP = ">rvrYWsH"
MEMORY_WORKER_BOTTOM = "^WX ^   "


def build_memory() -> tuple[str, ...]:
    canvas = blank_interior(11, DISPATCH_HEIGHT)
    put_text(canvas, 0, 0, "@9M{{Mv")
    put(canvas, 6, 1, "<")
    put(canvas, 2, 1, "v")
    for y in range(2, 19):
        put(canvas, 2, y, "v")

    for worker in range(LOCAL_WORKERS):
        top = 19 + 2 * worker
        put(canvas, 2, top, "Y")
        put(canvas, 1, top, "H" if worker + 1 == LOCAL_WORKERS else "v")
        put_text(canvas, 3, top, MEMORY_WORKER_TOP)
        if worker + 1 < LOCAL_WORKERS:
            put(canvas, 1, top + 1, ">")
            put(canvas, 2, top + 1, "v")
        put_text(canvas, 3, top + 1, MEMORY_WORKER_BOTTOM)
    return finish_interior(canvas)


def build_zero_memory() -> tuple[str, ...]:
    canvas = blank_interior(10, 1 + 2 * LOCAL_WORKERS)
    put_text(canvas, 0, 0, "@v")

    for worker in range(LOCAL_WORKERS):
        top = 1 + 2 * worker
        put(canvas, 1, top, "Y")
        put(canvas, 0, top, "H" if worker + 1 == LOCAL_WORKERS else "v")
        put_text(canvas, 2, top, MEMORY_WORKER_TOP)
        if worker + 1 < LOCAL_WORKERS:
            put(canvas, 0, top + 1, ">")
            put(canvas, 1, top + 1, "v")
        put_text(canvas, 2, top + 1, MEMORY_WORKER_BOTTOM)
    return finish_interior(canvas)


def build_collector(width: int) -> tuple[str, ...]:
    canvas = blank_interior(width, 4)
    put_text(canvas, 0, 1, "@9M{{MRvRY-sH")
    put(canvas, 7, 2, ">")
    put(canvas, 9, 2, "^")
    return finish_interior(canvas)


def build_zero_collector(width: int) -> tuple[str, ...]:
    canvas = blank_interior(width, 2)
    put_text(canvas, 0, 0, "@9M{{MRvRYX  sH")
    put_text(canvas, 7, 1, "> ^>-sH")
    return finish_interior(canvas)


def draw_vertical_pipe(
    canvas: list[list[str]], source_bottom: int, destination_top: int, x: int
) -> None:
    if destination_top - source_bottom - 1 < PIPE_LENGTH:
        raise ValueError("vertical pipe is too short")
    for y in range(source_bottom + 1, destination_top):
        canvas[y][x] = "v"


def draw_horizontal_pipe(
    canvas: list[list[str]], source_right: int, destination_left: int, y: int
) -> None:
    if destination_left - source_right - 1 < PIPE_LENGTH:
        raise ValueError("horizontal pipe is too short")
    for x in range(source_right + 1, destination_left):
        canvas[y][x] = ">"


def render(compact_right: bool = False, direct_fanout: bool = False) -> str:
    folded_dispatchers = compact_right and direct_fanout
    dispatcher_width = 6 if folded_dispatchers else DISPATCH_WIDTH
    built_dispatchers = (
        [build_folded_dispatcher(block) for block in range(BLOCKS)]
        if folded_dispatchers
        else [build_dispatcher(block) for block in range(BLOCKS)]
    )
    dispatchers = [dispatcher for dispatcher, _leaves in built_dispatchers]
    dispatcher_leaves = built_dispatchers[0][1]
    if any(leaves != dispatcher_leaves for _dispatcher, leaves in built_dispatchers):
        raise ValueError("dispatcher leaf rows are not aligned")
    memory = build_zero_memory() if compact_right else build_memory()
    if folded_dispatchers:
        memory_left_in_block = dispatcher_width + 2 + PIPE_LENGTH
        megablock_stride = memory_left_in_block + len(memory[0]) + 2
    else:
        memory_left_in_block = MEMORY_LEFT_IN_BLOCK
        megablock_stride = MEGABLOCK_STRIDE
    total_megablock_width = megablock_stride * BLOCKS
    parser = normalize_rows(
        build_sync_parser()
        if folded_dispatchers
        else build_parser(direct_fanout=direct_fanout)
    )
    if direct_fanout:
        parser = tuple(row.ljust(total_megablock_width - 2) for row in parser)
    fanout = None if direct_fanout else build_fanout(total_megablock_width - 2)
    collector_width = (
        (BLOCKS - 1) * megablock_stride + memory_left_in_block - 3
        if folded_dispatchers
        else total_megablock_width - 2
    )
    collector = (
        build_zero_collector(collector_width)
        if compact_right
        else build_collector(collector_width)
    )

    parser_bottom = PARSER_TOP + len(parser) + 1
    if direct_fanout:
        fanout_top = None
        fanout_bottom = parser_bottom
        megablock_top = parser_bottom + (1 if folded_dispatchers else 3)
    else:
        fanout_top = parser_bottom + 3
        fanout_bottom = fanout_top + len(fanout) + 1
        megablock_top = fanout_bottom + 3
    megablock_bottom = megablock_top + len(dispatchers[0]) + 1
    collector_top = megablock_bottom + (1 if folded_dispatchers else 3)
    collector_bottom = collector_top + len(collector) + 1
    if folded_dispatchers:
        collector_right = MEGABLOCK_LEFT + collector_width + 1
        output_left = collector_right + 3
        output_top = collector_top
    else:
        collector_output_x = MEGABLOCK_LEFT + 1 + 11
        output_left = collector_output_x - 1
        output_top = collector_bottom + 3

    width = max(
        MEGABLOCK_LEFT + total_megablock_width,
        PARSER_LEFT + len(parser[0]) + 2,
        output_left + 3,
    )
    height = max(collector_bottom + 1, output_top + 3)
    canvas = [[" "] * width for _ in range(height)]

    draw_room(canvas, PARSER_LEFT, PARSER_TOP, parser)
    if folded_dispatchers:
        input_left = MEGABLOCK_LEFT + 13
        draw_room(canvas, input_left, megablock_top, ("I",))
        canvas[megablock_top][input_left + 3] = ">"
        canvas[megablock_top][input_left + 4] = "^"
    else:
        input_y = PARSER_TOP + 1 + 3
        draw_room(canvas, 0, input_y - 1, ("I",))
        draw_horizontal_pipe(canvas, 2, PARSER_LEFT, input_y)

    if fanout is not None and fanout_top is not None:
        draw_room(canvas, MEGABLOCK_LEFT, fanout_top, fanout)
        parser_output_x = PARSER_LEFT + 1 + 135
        draw_vertical_pipe(canvas, parser_bottom, fanout_top, parser_output_x)

    memory_rooms: list[tuple[int, int, int]] = []
    for block in range(BLOCKS):
        left = MEGABLOCK_LEFT + block * megablock_stride
        draw_room(canvas, left, megablock_top, dispatchers[block])
        memory_left = left + memory_left_in_block
        memory_top = (
            megablock_top + dispatcher_leaves[0] - 1
            if compact_right
            else megablock_top
        )
        draw_room(canvas, memory_left, memory_top, memory)
        memory_bottom = memory_top + len(memory) + 1
        memory_rooms.append((memory_left, memory_top, memory_bottom))

        if folded_dispatchers:
            command_x = left + dispatcher_width + 2
            canvas[megablock_top][command_x] = "v"
            canvas[megablock_top + 1][command_x] = "<"
        else:
            command_x = left + 1 + 5
            draw_vertical_pipe(canvas, fanout_bottom, megablock_top, command_x)

        dispatcher_right = left + len(dispatchers[block][0]) + 1
        for leaf_y in dispatcher_leaves:
            pipe_y = megablock_top + 1 + leaf_y
            draw_horizontal_pipe(canvas, dispatcher_right, memory_left, pipe_y)

    draw_room(canvas, MEGABLOCK_LEFT, collector_top, collector)
    for memory_left, _memory_top, memory_bottom in memory_rooms:
        if folded_dispatchers:
            canvas[memory_bottom][memory_left - 2] = "v"
            canvas[memory_bottom][memory_left - 1] = "<"
        else:
            result_offset = 8 if compact_right else 9
            result_x = memory_left + 1 + result_offset
            draw_vertical_pipe(canvas, memory_bottom, collector_top, result_x)

    if folded_dispatchers:
        draw_room(canvas, output_left, output_top, ("O",))
        for x in range(collector_right + 1, output_left):
            canvas[collector_top + 1][x] = ">"
    else:
        draw_vertical_pipe(canvas, collector_bottom, output_top, collector_output_x)
        draw_room(canvas, output_left, output_top, ("O",))

    left_crop = MEGABLOCK_LEFT if folded_dispatchers else 0
    return "\n".join(
        "".join(row[left_crop:]).rstrip()
        for row in canvas
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact-right", action="store_true")
    parser.add_argument("--direct-fanout", action="store_true")
    parser.add_argument("-o", "--output", type=Path)
    arguments = parser.parse_args()
    if arguments.compact_right and arguments.direct_fanout:
        default_name = "memory-6tick-sync.man"
    elif arguments.compact_right:
        default_name = "packed-memory-6-right-zero.man"
    elif arguments.direct_fanout:
        default_name = "packed-memory-6-direct.man"
    else:
        default_name = "packed-memory-6.man"
    output = arguments.output or Path(__file__).with_name(default_name)
    program = render(
        compact_right=arguments.compact_right,
        direct_fanout=arguments.direct_fanout,
    )
    output.write_text(program, encoding="ascii")
    rows = program.splitlines()
    print(f"wrote {output} ({max(map(len, rows))}x{len(rows)})")


if __name__ == "__main__":
    main()
