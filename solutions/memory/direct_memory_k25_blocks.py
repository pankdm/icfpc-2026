"""Generate the compact k=25 memory pipeline under development."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .direct_memory import draw_room, normalize_rows
except ImportError:
    from direct_memory import draw_room, normalize_rows


LEFT_PAIR = (
    ">dsH",
    " >mv",
    "Hsa<",
    "vm< ",
)

PARSE_READER_CORE = (
    "       v  YrbrsdWsH",
    "@9M{{NM>  ^Hs-r<   ",
)

PACK_READER = (
    "Hs-W1W*rsrY  v",
    "     @5M*M^  <",
)

FANOUT_READER = (
    "HS-rWSWS/rY  v",
    "     @5M*M^  <",
)

DECODER_INTERIOR = (
    " vY/WbW  dsHvY/WbW  dsHvY/WbW  dsHvY/WbW  dsHvY/WbW  dsHvY/WbW  dsH  ",
    "  RHsam  <   RHsam  <   RHsam  <   RHsam  <   RHsam  <   RHsam  <    ",
    " >^Yv>  masH>^Yv>  masH>^Yv>  masH>^Yv>  masH>^Yv>  masH>^Yv>  masH  ",
    ">  Y>         Y>         Y>         Y>         Y>         YH         ",
    "W@vvY/WbW  dsHvY/WbW  dsHvY/WbW  dsHvY/WbW  dsHvY/WbW  dsHvY/WbW  dsH",
    "* 5 RHsam  <   RHsam  <   RHsam  <   RHsam  <   RHsam  <   RHsam  <  ",
    "^M<>^  >  masH>^  >  masH>^  >  masH>^  >  masH>^  >  masH>^  >  masH",
)

SUBTRACT_READER = (
    ">r-sv      ",
    "^s-r<     <",
    "@9M{{M1W-M^",
)

RIGHT_HEADER = (
    "@9M{{M5Wv",
    " v-W1W**<",
    " >    v  ",
)

RIGHT_CELL = (
    ">rvrW<Y-v",
    "^WXWs^v <",
)

RIGHT_LAST = (
    ">rvrW<YHv",
    "^WXWs^v <",
)

K = 25
L = 4
PIPE_LENGTH = 2
LEFT_FIRST_SEND_ROW = 10
RIGHT_TOP = LEFT_FIRST_SEND_ROW - len(RIGHT_HEADER)
READER_TOP = 0
INPUT_LEFT = 0
PARSE_LEFT = 34
PACK_LEFT = 57
FANOUT_TOP = 4
MEGABLOCK_TOP = 8
DECODER_ROOM_WIDTH = 69


def build_left_header(block_id: int) -> tuple[str, ...]:
    if not 0 <= block_id <= 9:
        raise ValueError("block id must fit in one digit")
    return (
        ">  v",
        "Y  <",
        ">v W",
        f" r {block_id}",
        " -@^",
        "vXv ",
        "rrr ",
        "rbr ",
        "HrH ",
        "v<  ",
        *LEFT_PAIR,
    )


def build_left_block(k: int, block_id: int) -> tuple[str, ...]:
    if k < 2:
        raise ValueError("compact header requires at least two workers")
    pairs, remainder = divmod(k - 2, 2)
    return normalize_rows(
        build_left_header(block_id)
        + LEFT_PAIR * pairs
        + LEFT_PAIR[:remainder]
    )


def build_right_block(k: int) -> tuple[str, ...]:
    return normalize_rows(RIGHT_HEADER + RIGHT_CELL * (k - 1) + RIGHT_LAST)


def build_parse_reader() -> tuple[str, ...]:
    return normalize_rows(PARSE_READER_CORE)


def build_fanout_reader(width: int) -> tuple[str, ...]:
    core = normalize_rows(FANOUT_READER)
    if width < len(core[0]):
        raise ValueError("fanout room is too narrow")
    prefix = " " * (width - len(core[0]))
    return tuple(prefix + row for row in core)


def build_decoder_interior(width: int) -> tuple[str, ...]:
    decoder = normalize_rows(DECODER_INTERIOR)
    if width < len(decoder[0]):
        raise ValueError("decoder room is too narrow")
    padding = " " * (width - len(decoder[0]))
    return tuple(row + padding for row in decoder)


def build_subtract_reader() -> tuple[str, ...]:
    return normalize_rows(SUBTRACT_READER)


def draw_horizontal_pipe(
    canvas: list[list[str]], source_right: int, destination_left: int, row: int
) -> None:
    if destination_left - source_right - 1 < 2:
        raise ValueError("horizontal pipe must contain at least two cells")
    for x in range(source_right + 1, destination_left):
        canvas[row][x] = ">"


def draw_vertical_pipe(
    canvas: list[list[str]], source_bottom: int, destination_top: int, column: int
) -> None:
    if destination_top - source_bottom - 1 < 2:
        raise ValueError("vertical pipe must contain at least two cells")
    for y in range(source_bottom + 1, destination_top):
        canvas[y][column] = "v"


def draw_input_delay_pipe(canvas: list[list[str]]) -> None:
    path = (
        (3, 2, ">"),
        (4, 2, "^"),
        (4, 1, "^"),
        (4, 0, ">"),
        *((x, 0, "-") for x in range(5, 19)),
        (19, 0, "v"),
        (19, 1, "<"),
        *((x, 1, "-") for x in range(18, 10, -1)),
        (10, 1, "v"),
        (10, 2, ">"),
        *((x, 2, "-") for x in range(11, 33)),
        (33, 2, ">"),
    )
    for x, y, instruction in path:
        canvas[y][x] = instruction


def render(k: int, l: int) -> str:
    left = build_left_block(k, 0)
    right = build_right_block(k)
    left_room_width = len(left[0]) + 2
    local_right_x = left_room_width + PIPE_LENGTH
    megablock_width = local_right_x + len(right[0]) + 2
    megablocks_width = megablock_width * l
    megablock_height = max(len(left) + 2, RIGHT_TOP + len(right) + 2)
    decoder = build_decoder_interior(DECODER_ROOM_WIDTH)
    subtract_reader = build_subtract_reader()
    storage_source_y = MEGABLOCK_TOP + RIGHT_TOP + len(right) + 1
    decoder_top = storage_source_y + 1
    decoder_right = len(decoder[0]) + 1
    subtract_left = decoder_right + PIPE_LENGTH + 1
    subtract_top = decoder_top + (len(decoder) - len(subtract_reader)) // 2
    subtract_right = subtract_left + len(subtract_reader[0]) + 1
    subtract_bottom = subtract_top + len(subtract_reader) + 1
    output_left = subtract_left + (len(subtract_reader[0]) - 1) // 2
    output_top = subtract_bottom + 3
    width = max(megablocks_width, subtract_right + 1, output_left + 3)
    height = max(
        decoder_top + len(decoder) + 2,
        subtract_top + len(subtract_reader) + 2,
        output_top + 3,
    )
    canvas = [[" "] * width for _ in range(height)]

    parse_reader = build_parse_reader()
    pack_reader = normalize_rows(PACK_READER)
    fanout_reader = build_fanout_reader(megablocks_width - 2)
    draw_room(canvas, INPUT_LEFT, READER_TOP + 1, ("I",))
    draw_room(canvas, PARSE_LEFT, READER_TOP, parse_reader)
    draw_room(canvas, PACK_LEFT, READER_TOP, pack_reader)
    input_pipe_y = READER_TOP + 2
    draw_input_delay_pipe(canvas)
    draw_horizontal_pipe(
        canvas,
        PARSE_LEFT + len(parse_reader[0]) + 1,
        PACK_LEFT,
        READER_TOP + 2,
    )
    draw_room(canvas, 0, FANOUT_TOP, fanout_reader)
    pack_right = PACK_LEFT + len(pack_reader[0]) + 1
    canvas[input_pipe_y][pack_right + 1] = ">"
    canvas[input_pipe_y][pack_right + 2] = "v"
    canvas[input_pipe_y + 1][pack_right + 2] = "v"

    for block_id in range(l):
        offset = block_id * megablock_width
        draw_room(
            canvas,
            offset,
            MEGABLOCK_TOP,
            build_left_block(k, block_id),
        )
        draw_room(
            canvas,
            offset + local_right_x,
            MEGABLOCK_TOP + RIGHT_TOP,
            right,
        )
        fanout_pipe_x = offset + left_room_width
        canvas[MEGABLOCK_TOP][fanout_pipe_x] = "v"
        canvas[MEGABLOCK_TOP + 1][fanout_pipe_x] = "<"
        for worker in range(k):
            row = MEGABLOCK_TOP + 1 + LEFT_FIRST_SEND_ROW + 2 * worker
            for x in range(
                offset + left_room_width,
                offset + local_right_x,
            ):
                canvas[row][x] = ">"

        canvas[storage_source_y][offset + local_right_x - 1] = "<"
        canvas[storage_source_y][offset + local_right_x - 2] = "v"

    draw_room(canvas, 0, decoder_top, decoder)
    draw_room(canvas, subtract_left, subtract_top, subtract_reader)
    draw_horizontal_pipe(canvas, decoder_right, subtract_left, subtract_top + 2)
    draw_room(canvas, output_left, output_top, ("O",))
    canvas[subtract_bottom + 1][output_left + 1] = "v"
    canvas[subtract_bottom + 2][output_left + 1] = "v"

    return "\n".join("".join(row).rstrip() for row in canvas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--l", type=int, default=L)
    parser.add_argument("-o", "--output", type=Path)
    arguments = parser.parse_args()
    if arguments.k <= 0:
        raise ValueError("k must be positive")
    if arguments.l <= 0 or arguments.l > 10:
        raise ValueError("l must be between 1 and 10")

    output = arguments.output or Path(__file__).with_name(
        f"direct-memory-k{arguments.k}-blocks.man"
    )
    program = render(arguments.k, arguments.l)
    output.write_text(program, encoding="ascii")
    print(
        f"wrote {output} (k={arguments.k}, spawner=8 ticks, "
        f"blocks={arguments.l}, workers={arguments.k * arguments.l}, "
        f"width={max(map(len, program.splitlines()))})"
    )


if __name__ == "__main__":
    main()
