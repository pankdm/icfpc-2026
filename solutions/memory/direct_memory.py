"""Build the synchronized direct-memory layout incrementally."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


HEADER = (
    ">r-v ",
    "M vXv",
    "0 rrr",
    "^<rbr",
    ">^ r ",
    " v < ",
    "  >v<",
    "   >v",
)

PAIR_DECODER = (
    " avv<",
    " sm  ",
    " > >v",
    " vd  ",
    " ms  ",
    "  > v",
)

WORKER_RETURN = "^   <"
DISPATCH_LOOP = ">m aH"

SECOND_OTHER = (
    " -vsW<",
    "vY>WrX",
    ">v^  <",
)

SECOND_FIRST = (
    " +vsW<",
    "vY>WrX",
    ">v^  <",
)

SECOND_LAST = (
    " -vsW<",
    " >>WrX",
    "  ^  <",
)

SECOND_INITIALIZER = (
    "@9M{{v",
    "     M",
    "v`02`<",
    ">W*W1v",
    " v--W<",
)

LEFT_INITIALIZER = (
    "^b~*<",
    "@3M7^",
)

DELAY_DECODER = (
    ">*MR/WbWdsv",
    "^4M5sa m<  ",
    "^Yv  >m asv",
    "^      4M5<",
    " ^>        ",
)

SUBTRACT_READER = (
    ">r-sv      ",
    "^s-r<     <",
    "@9M{{M1W-M^",
)

VALUE_OFFSET = 9 << 18
PACKING_BASE = 20

PARSE_READER = (
    "@3b>  dHv    sWs   <",
    "  v^ mY > 9M{{NMrbrx",
    "        ^    sWsWrW<",
)

ADJUST_READER_CORE = (
    "@9M{{Mv v    s-<",
    "   v  Y>> rsr+X^",
    "   >   ^     s< ",
)

MULTIPLY_READER = (
    "vM`02`@<",
    ">rsr*s v",
    "^ s*rsr<",
)

DECREMENT_READER = (
    "vM1@<   ",
    ">rsr-s v",
    "^ s-rsr<",
)

FANOUT_READER = (
    "3b>m v>r/SWSW r-Sv",
    " Hd  Y^W`02`     <",
)

TOP_HEADER = (
    "+-++---------------------+  +-----------------------+  +--------+          +--------+",
    "|I||>WrWsWs    v        <|  | >s     v   <  v     <<|  |vM`02`@<|>>>>>>>>v |vM1@<   |",
    "+-+|xrbrMN{{M9 < Ym v^  <|>>|vX+rsr <<Y  ^  v  >  ^<|>>|>rsr*s v|     v<<< |>rsr-s v|",
    "  v|>   sWs    ^Hd  <b3@<|  |>-s    ^ ^M{{M9<  ^  @<|  |^ s*rsr<|     >>>>>|^ s-rsr<|",
    "  >+---------------------+  +-----------------------+  +--------+     v<<<<+--------+",
    "+-----------------------------------------------------------------------------------+",
    "|v @  <                                                         >3b>m v>r/SWSW r-Sv |",
    "|>5M4*M                                                         ^ Hd  Y^W`02`     < |",
    "+-----------------------------------------------------------------------------------+",
)

STARTUP_DELAY_PREFIX = (
    "@  v  >",
    "v  <  ^",
    ">     ^",
)

LEFT_ROOM_X = 0
LEFT_ROOM_Y = 0
PIPE_LENGTH = 2
DECREMENT_GAP_WIDTH = 10
DECREMENT_INPUT_PIPE_LENGTH = 17
MULTIPLIER_INPUT_PIPE_LENGTH = PIPE_LENGTH
RIGHT_ROOM_Y = len(HEADER) - len(SECOND_INITIALIZER)
READER_ROOM_Y = 0
FANOUT_ROOM_Y = 5
MEGABLOCK_Y = 9
DECODER_COLUMNS = 6
DECODER_ROWS = 2
DECODER_PREFIX_WIDTH = 9
DECODER_TILE_WIDTH = 11
DECODER_TILE_HEIGHT = 5
DECODER_INTERIOR_WIDTH = 75
FANOUT_INTERIOR_WIDTH = 83
FANOUT_STARTUP_X = 2
FANOUT_STARTUP_TURN_X = 5
FANOUT_TRAILING_WIDTH = 1


@dataclass(frozen=True)
class Config:
    k: int = 20
    l: int = 5
    target_ticks: int = 8

    def validate(self) -> None:
        if self.k <= 0 or self.k % 2:
            raise ValueError("k must be a positive even number")
        if self.l <= 0:
            raise ValueError("l must be positive")
        if self.k * self.l < 100:
            raise ValueError("k*l must be at least 100")
        if self.target_ticks < 8 or self.target_ticks % 2:
            raise ValueError("target_ticks must be an even number at least 8")


@dataclass(frozen=True)
class Trace:
    ticks: int
    reads: int
    sends: int


@dataclass(frozen=True)
class StageTrace:
    ticks: int
    outputs: tuple[int, ...]
    read_ticks: tuple[int, ...]
    send_ticks: tuple[int, ...]


@dataclass
class StartupRunner:
    x: int
    y: int
    direction: tuple[int, int] = (1, 0)
    main: int = 0
    offhand: int = 0
    backpack: int = 0


def decoder_interior(config: Config, block_id: int) -> tuple[str, ...]:
    config.validate()
    if not 0 <= block_id <= 9:
        raise ValueError("block id must fit in one digit")
    header = list(HEADER)
    header[1] = "M" + header[1][1:]
    header[2] = str(block_id) + header[2][1:]
    return tuple(header) + PAIR_DECODER * (config.k // 2)


def unpadded_worker_ticks(config: Config) -> int:
    return 28 + 7 * config.k


def worker_padding_rows(config: Config) -> int:
    base_ticks = unpadded_worker_ticks(config)
    for rows in range(config.target_ticks):
        if (base_ticks + 2 * rows) % config.target_ticks == 0:
            return rows
    raise ValueError("cannot balance the worker loop for target_ticks")


def worker_loop_ticks(config: Config) -> int:
    return unpadded_worker_ticks(config) + 2 * worker_padding_rows(config)


def worker_count(config: Config) -> int:
    return worker_loop_ticks(config) // config.target_ticks


def dispatch_padding_rows(config: Config) -> int:
    return (config.target_ticks - 8) // 2


def dispatch_fork_row(config: Config) -> str:
    return "Y  < "


def normalize_rows(rows: tuple[str, ...]) -> tuple[str, ...]:
    width = max(map(len, rows))
    return tuple(row.ljust(width) for row in rows)


def add_startup_delay(rows: tuple[str, ...]) -> tuple[str, ...]:
    normalized = normalize_rows(rows)
    return tuple(
        prefix + row[1:]
        for prefix, row in zip(STARTUP_DELAY_PREFIX, normalized)
    )


def rotate_reader(rows: tuple[str, ...]) -> tuple[str, ...]:
    translations = str.maketrans("><^vV", "<>v^^")
    return tuple(
        row[::-1].translate(translations) + "<"
        for row in reversed(normalize_rows(rows))
    )


def build_parse_reader() -> tuple[str, ...]:
    return rotate_reader(PARSE_READER)


def build_adjust_reader() -> tuple[str, ...]:
    return rotate_reader(add_startup_delay(ADJUST_READER_CORE))


def build_multiply_reader() -> tuple[str, ...]:
    return normalize_rows(MULTIPLY_READER)


def build_decrement_reader() -> tuple[str, ...]:
    return normalize_rows(DECREMENT_READER)


def build_fanout_reader(width: int) -> tuple[str, ...]:
    reader = normalize_rows(FANOUT_READER)
    if width < len(reader[0]):
        raise ValueError("fanout room is too narrow")
    core_x = width - len(reader[0]) - FANOUT_TRAILING_WIDTH
    if not 0 < FANOUT_STARTUP_X < core_x - 2:
        raise ValueError("fanout room has no space for its startup route")
    rows = [
        list(" " * core_x + row + " " * FANOUT_TRAILING_WIDTH)
        for row in reader
    ]
    rows[0][0] = "v"
    rows[0][FANOUT_STARTUP_X] = "@"
    rows[0][FANOUT_STARTUP_TURN_X] = "<"
    rows[0][core_x - 1] = ">"
    rows[1][0] = ">"
    rows[1][1:6] = "5M4*M"
    rows[1][core_x - 1] = "^"
    return tuple("".join(row) for row in rows)


def build_decoder_interior() -> tuple[str, ...]:
    canvas = [
        [" "] * DECODER_INTERIOR_WIDTH
        for _ in range(DECODER_ROWS * DECODER_TILE_HEIGHT)
    ]
    for tile_row in range(DECODER_ROWS):
        for tile_column in range(DECODER_COLUMNS):
            tile = build_decoder_tile()
            left = DECODER_PREFIX_WIDTH + tile_column * DECODER_TILE_WIDTH
            top = tile_row * DECODER_TILE_HEIGHT
            for row_offset, row in enumerate(tile):
                for column_offset, instruction in enumerate(row):
                    if instruction != " ":
                        canvas[top + row_offset][left + column_offset] = instruction

    initializer_y = DECODER_TILE_HEIGHT + 1
    for x, instruction in enumerate("@4M5  Y"):
        canvas[initializer_y][x] = instruction
    for tile_row in range(DECODER_ROWS):
        entry_y = (tile_row + 1) * DECODER_TILE_HEIGHT - 1
        canvas[entry_y][6] = ">"
        canvas[entry_y][DECODER_INTERIOR_WIDTH - 1] = "H"
    return tuple("".join(row) for row in canvas)


def build_decoder_tile() -> tuple[str, ...]:
    base = normalize_rows(DELAY_DECODER)
    canvas = [[" "] * DECODER_TILE_WIDTH for _ in range(DECODER_TILE_HEIGHT)]
    for row_offset, row in enumerate(base):
        for column_offset, instruction in enumerate(row):
            if instruction != " ":
                canvas[row_offset][column_offset] = instruction
    return tuple("".join(row) for row in canvas)


def build_subtract_reader() -> tuple[str, ...]:
    return normalize_rows(SUBTRACT_READER)


def build_left_interior(config: Config, block_id: int = 0) -> tuple[str, ...]:
    worker_padding = (" " * 5,) * worker_padding_rows(config)
    dispatch_padding = (" " * 5,) * dispatch_padding_rows(config)
    return normalize_rows(
        decoder_interior(config, block_id)
        + worker_padding
        + (WORKER_RETURN, dispatch_fork_row(config))
        + dispatch_padding
        + (DISPATCH_LOOP,)
        + LEFT_INITIALIZER
    )


def build_second_interior(config: Config) -> tuple[str, ...]:
    config.validate()
    return (
        SECOND_INITIALIZER
        + SECOND_FIRST
        + SECOND_OTHER * (config.k - 2)
        + SECOND_LAST
    )


def connection_rows(config: Config) -> tuple[int, ...]:
    left_rows = tuple(
        LEFT_ROOM_Y + 1 + len(HEADER) + 6 * pair + offset
        for pair in range(config.k // 2)
        for offset in (1, 4)
    )
    right_rows = tuple(
        RIGHT_ROOM_Y + len(SECOND_INITIALIZER) + 2 + 3 * worker
        for worker in range(config.k)
    )
    if left_rows != right_rows:
        raise ValueError("left sends and right receives are not aligned")
    return left_rows


def draw_room(
    canvas: list[list[str]], left: int, top: int, interior: tuple[str, ...]
) -> None:
    width = len(interior[0])
    wall = "+" + "-" * width + "+"
    rows = (wall, *(f"|{row}|" for row in interior), wall)
    for row_offset, row in enumerate(rows):
        for column_offset, instruction in enumerate(row):
            canvas[top + row_offset][left + column_offset] = instruction


def render_program(config: Config) -> str:
    left = build_left_interior(config, 0)
    right = build_second_interior(config)
    parse_reader = build_parse_reader()
    adjust_reader = build_adjust_reader()
    multiply_reader = build_multiply_reader()
    decrement_reader = build_decrement_reader()
    subtract_reader = build_subtract_reader()
    left_width = len(left[0])
    local_pipe_x = LEFT_ROOM_X + left_width + 2
    local_right_x = local_pipe_x + PIPE_LENGTH
    megablock_width = local_right_x + len(right[0]) + 2
    megablocks_width = megablock_width * config.l
    decoder = build_decoder_interior()
    pipeline_width = (
        3
        + PIPE_LENGTH
        + len(parse_reader[0]) + 2
        + PIPE_LENGTH
        + len(adjust_reader[0]) + 2
        + PIPE_LENGTH
        + len(multiply_reader[0]) + 2
        + DECREMENT_GAP_WIDTH
        + len(decrement_reader[0]) + 2
        + 2
    )
    width = max(megablocks_width, pipeline_width)
    pipeline_x = width - pipeline_width
    input_x = pipeline_x
    parse_x = input_x + 3 + PIPE_LENGTH
    adjust_x = parse_x + len(parse_reader[0]) + 2 + PIPE_LENGTH
    multiply_x = adjust_x + len(adjust_reader[0]) + 2 + PIPE_LENGTH
    decrement_x = (
        multiply_x + len(multiply_reader[0]) + 2 + DECREMENT_GAP_WIDTH
    )
    megablock_height = max(
        LEFT_ROOM_Y + len(left) + 2,
        RIGHT_ROOM_Y + len(right) + 2,
    )
    storage_bottom = MEGABLOCK_Y + RIGHT_ROOM_Y + len(right) + 1
    decoder_top = MEGABLOCK_Y + megablock_height
    decoder_right = len(decoder[0]) + 1
    subtract_left = decoder_right + PIPE_LENGTH + 1
    subtract_top = decoder_top + (len(decoder) - len(subtract_reader)) // 2
    subtract_right = subtract_left + len(subtract_reader[0]) + 1
    output_left = subtract_right + PIPE_LENGTH + 1
    decoder_pipe_y = subtract_top + 2
    output_top = decoder_pipe_y - 1
    width = max(width, output_left + 3)
    fanout_reader = build_fanout_reader(pipeline_width - 2)
    height = max(
        MEGABLOCK_Y + megablock_height,
        decoder_top + len(decoder) + 2,
        subtract_top + len(subtract_reader) + 2,
        output_top + 3,
    )
    canvas = [[" "] * width for _ in range(height)]

    draw_room(canvas, input_x, READER_ROOM_Y + 1, ("I",))
    draw_room(canvas, parse_x, READER_ROOM_Y, parse_reader)
    draw_room(canvas, adjust_x, READER_ROOM_Y, adjust_reader)
    draw_room(canvas, multiply_x, READER_ROOM_Y, multiply_reader)
    draw_room(canvas, decrement_x, READER_ROOM_Y, decrement_reader)
    reader_pipe_y = READER_ROOM_Y + 2
    for left_wall, right_room in (
        (input_x + 2, parse_x),
        (parse_x + len(parse_reader[0]) + 1, adjust_x),
        (adjust_x + len(adjust_reader[0]) + 1, multiply_x),
    ):
        for x in range(left_wall + 1, right_room):
            canvas[reader_pipe_y][x] = ">"

    draw_room(canvas, 0, FANOUT_ROOM_Y, fanout_reader)
    multiply_right = multiply_x + len(multiply_reader[0]) + 1
    gap_left = multiply_right + 1
    gap_right = decrement_x - 1
    if gap_right - gap_left + 1 != DECREMENT_GAP_WIDTH:
        raise ValueError("unexpected decrement buffer gap width")
    canvas[reader_pipe_y][gap_left] = ">"
    canvas[reader_pipe_y][gap_left + 1] = "^"
    for x in range(gap_left + 1, gap_right):
        canvas[reader_pipe_y - 1][x] = ">"
    canvas[reader_pipe_y - 1][gap_right - 1] = "v"
    canvas[reader_pipe_y][gap_right - 1] = "<"
    canvas[reader_pipe_y][gap_right - 2] = "<"
    canvas[reader_pipe_y][gap_right - 3] = "v"
    canvas[reader_pipe_y + 1][gap_right - 3] = ">"
    canvas[reader_pipe_y + 1][gap_right - 2] = ">"
    canvas[reader_pipe_y + 1][gap_right - 1] = ">"
    canvas[reader_pipe_y + 1][gap_right] = ">"

    decrement_right = decrement_x + len(decrement_reader[0]) + 1
    canvas[reader_pipe_y][decrement_right + 1] = ">"
    canvas[reader_pipe_y][decrement_right + 2] = "v"
    canvas[reader_pipe_y + 1][decrement_right + 2] = "<"
    canvas[reader_pipe_y + 1][decrement_right + 1] = "v"
    canvas[reader_pipe_y + 2][decrement_right + 1] = "v"

    for y, row in enumerate(TOP_HEADER):
        canvas[y] = [" "] * width
        canvas[y][: len(row)] = row

    for megablock in range(config.l):
        offset = megablock * megablock_width
        draw_room(
            canvas,
            offset + LEFT_ROOM_X,
            MEGABLOCK_Y + LEFT_ROOM_Y,
            build_left_interior(config, megablock),
        )
        draw_room(canvas, offset + local_right_x, MEGABLOCK_Y + RIGHT_ROOM_Y, right)
        for row in connection_rows(config):
            for x in range(
                offset + local_pipe_x,
                offset + local_pipe_x + PIPE_LENGTH,
            ):
                canvas[MEGABLOCK_Y + row][x] = ">"
        if megablock == config.l - 1:
            fanout_x = offset - 2
            canvas[MEGABLOCK_Y][fanout_x] = "v"
            canvas[MEGABLOCK_Y + 1][fanout_x] = ">"
            canvas[MEGABLOCK_Y + 1][fanout_x + 1] = ">"
        else:
            fanout_x = offset + left_width + 3
            canvas[MEGABLOCK_Y][fanout_x] = "v"
            canvas[MEGABLOCK_Y + 1][fanout_x] = "<"
            canvas[MEGABLOCK_Y + 1][fanout_x - 1] = "<"

        storage_pipe_x = offset + local_pipe_x
        storage_source_y = storage_bottom - 1
        canvas[storage_source_y][storage_pipe_x + 1] = "<"
        canvas[storage_source_y][storage_pipe_x] = "v"
        for y in range(storage_source_y + 1, decoder_top):
            canvas[y][storage_pipe_x] = "v"
        if storage_pipe_x >= decoder_right:
            turn_y = decoder_top - 1
            target_x = decoder_right - 1
            for x in range(target_x + 1, storage_pipe_x + 1):
                canvas[turn_y][x] = "<"
            canvas[turn_y][target_x] = "v"

    draw_room(canvas, 0, decoder_top, decoder)
    draw_room(canvas, subtract_left, subtract_top, subtract_reader)
    for x in range(decoder_right + 1, subtract_left):
        canvas[decoder_pipe_y][x] = ">"
    draw_room(canvas, output_left, output_top, ("O",))
    for x in range(subtract_right + 1, output_left):
        canvas[decoder_pipe_y][x] = ">"
    return "\n".join("".join(row).rstrip() for row in canvas) + "\n"


def trace_route(
    interior: tuple[str, ...], comparison: int, local_id: int = 0, block_id: int = 0
) -> Trace:
    values = iter((comparison, local_id, 7))
    x = 0
    y = 0
    direction = (1, 0)
    main = 0
    offhand = block_id
    backpack = 0
    ticks = 0
    reads = 0
    sends = 0

    while True:
        if not (0 <= x < len(interior[0]) and 0 <= y < len(interior)):
            raise ValueError(f"worker left the room unexpectedly at {(x, y)}")
        instruction = interior[y][x]
        if instruction in "rR":
            main = next(values)
            reads += 1
        elif instruction == "M":
            offhand = main
        elif instruction.isdigit():
            main = int(instruction)
        elif instruction == "-":
            main -= offhand
        elif instruction == "b":
            backpack = main
        elif instruction == "m":
            backpack -= 1
        elif instruction == "a" and backpack > 0:
            direction = (direction[1], -direction[0])
        elif instruction == "d" and backpack > 0:
            direction = (-direction[1], direction[0])
        elif instruction == "X":
            if main > 0:
                direction = (-direction[1], direction[0])
            elif main < 0:
                direction = (direction[1], -direction[0])
        elif instruction == "s":
            sends += 1
        elif instruction == ">":
            direction = (1, 0)
        elif instruction == "<":
            direction = (-1, 0)
        elif instruction == "^":
            direction = (0, -1)
        elif instruction in "vV":
            direction = (0, 1)

        x += direction[0]
        y += direction[1]
        ticks += 1
        if (x, y) == (0, 0):
            return Trace(ticks=ticks, reads=reads, sends=sends)
        if ticks > 100_000:
            raise ValueError("left-block route did not terminate")


def trace_second_worker(
    message: int, interior: tuple[str, ...] = SECOND_OTHER
) -> tuple[int, int, int, tuple[int, ...]]:
    x = 4
    y = 1
    direction = (1, 0)
    main = 0
    offhand = 7
    ticks = 0
    sends = 0
    outputs: list[int] = []

    while True:
        if not (0 <= x < 6 and 0 <= y < 3):
            raise ValueError(f"second worker left its loop at {(x, y)}")
        instruction = interior[y][x]
        if instruction in "rR":
            main = message
        elif instruction == "W":
            main, offhand = offhand, main
        elif instruction == "+":
            main += offhand
        elif instruction == "-":
            main -= offhand
        elif instruction == "X":
            if main > 0:
                direction = (-direction[1], direction[0])
            elif main < 0:
                direction = (direction[1], -direction[0])
        elif instruction == "s":
            sends += 1
            outputs.append(main)
        elif instruction == ">":
            direction = (1, 0)
        elif instruction == "<":
            direction = (-1, 0)
        elif instruction == "^":
            direction = (0, -1)
        elif instruction in "vV":
            direction = (0, 1)

        x += direction[0]
        y += direction[1]
        ticks += 1
        if (x, y) == (4, 1):
            return ticks, sends, offhand, tuple(outputs)
        if ticks > 100:
            raise ValueError("second worker loop did not terminate")


def trace_stage(
    interior: tuple[str, ...],
    start: tuple[int, int],
    inputs: tuple[int, ...],
    offhand: int,
    literal_content: frozenset[tuple[int, int]] = frozenset(),
    literal_closures: dict[tuple[int, int, tuple[int, int]], int] | None = None,
    start_direction: tuple[int, int] = (1, 0),
    initial_main: int = 0,
) -> StageTrace:
    interior = normalize_rows(interior)
    values = iter(inputs)
    x, y = start
    direction = start_direction
    main = initial_main
    backpack = 0
    ticks = 0
    outputs: list[int] = []
    read_ticks: list[int] = []
    send_ticks: list[int] = []
    literal_closures = literal_closures or {}

    while True:
        if not (0 <= x < len(interior[0]) and 0 <= y < len(interior)):
            raise ValueError(f"reader left its loop at {(x, y)}")
        instruction = interior[y][x]
        if (x, y) in literal_content:
            instruction = " "
        if instruction in "rR":
            main = next(values)
            read_ticks.append(ticks)
        elif instruction in "sS":
            outputs.append(main)
            send_ticks.append(ticks)
        elif instruction == "M":
            offhand = main
        elif instruction == "W":
            main, offhand = offhand, main
        elif instruction == "b":
            backpack = main
        elif instruction == "m":
            backpack -= 1
        elif instruction == "+":
            main += offhand
        elif instruction == "-":
            main -= offhand
        elif instruction == "*":
            main *= offhand
        elif instruction == "N":
            main = -main
        elif instruction == "/":
            main, offhand = divmod(main, offhand)
        elif instruction == "{":
            main <<= offhand
        elif instruction == "X":
            if main > 0:
                direction = (-direction[1], direction[0])
            elif main < 0:
                direction = (direction[1], -direction[0])
        elif instruction == "x":
            if backpack & 1:
                direction = (-direction[1], direction[0])
            else:
                direction = (direction[1], -direction[0])
        elif instruction == "a" and backpack > 0:
            direction = (direction[1], -direction[0])
        elif instruction == "d" and backpack > 0:
            direction = (-direction[1], direction[0])
        elif instruction == ">":
            direction = (1, 0)
        elif instruction == "<":
            direction = (-1, 0)
        elif instruction == "^":
            direction = (0, -1)
        elif instruction in "vV":
            direction = (0, 1)
        elif instruction == "`":
            main = literal_closures.get((x, y, direction), main)
        elif instruction.isdigit():
            main = int(instruction)
        elif instruction == "H":
            return StageTrace(
                ticks=ticks + 1,
                outputs=tuple(outputs),
                read_ticks=tuple(read_ticks),
                send_ticks=tuple(send_ticks),
            )

        x += direction[0]
        y += direction[1]
        ticks += 1
        if (x, y) == start:
            return StageTrace(
                ticks=ticks,
                outputs=tuple(outputs),
                read_ticks=tuple(read_ticks),
                send_ticks=tuple(send_ticks),
            )
        if ticks > 1_000:
            raise ValueError("reader loop did not terminate")


def startup_read_ticks(
    interior: tuple[str, ...], reader_start: tuple[int, int], reader_count: int
) -> tuple[int, ...]:
    interior = normalize_rows(interior)
    starts = [
        (x, y)
        for y, row in enumerate(interior)
        for x, instruction in enumerate(row)
        if instruction == "@"
    ]
    if len(starts) != 1:
        raise ValueError("reader room must contain one starting man")
    runners = [StartupRunner(*starts[0])]
    arrivals: list[int] = []

    for tick in range(200):
        positions = [(runner.x, runner.y) for runner in runners]
        if len(positions) != len(set(positions)):
            raise ValueError(f"reader startup collision at tick {tick}: {positions}")
        next_runners: list[StartupRunner] = []
        for runner in runners:
            if (runner.x, runner.y) == reader_start:
                arrivals.append(tick)
                continue
            instruction = interior[runner.y][runner.x]
            direction = runner.direction
            if instruction == "M":
                runner.offhand = runner.main
            elif instruction == "W":
                runner.main, runner.offhand = runner.offhand, runner.main
            elif instruction == "*":
                runner.main *= runner.offhand
            elif instruction == "-":
                runner.main -= runner.offhand
            elif instruction == "b":
                runner.backpack = runner.main
            elif instruction == "m":
                runner.backpack -= 1
            elif instruction == "N":
                runner.main = -runner.main
            elif instruction == "{":
                runner.main <<= runner.offhand
            elif instruction == "d" and runner.backpack > 0:
                runner.direction = (-direction[1], direction[0])
            elif instruction == ">":
                runner.direction = (1, 0)
            elif instruction == "<":
                runner.direction = (-1, 0)
            elif instruction == "^":
                runner.direction = (0, -1)
            elif instruction in "vV":
                runner.direction = (0, 1)
            elif instruction.isdigit():
                runner.main = int(instruction)
            elif instruction == "H":
                continue
            elif instruction == "Y":
                clockwise = (-direction[1], direction[0])
                counterclockwise = (direction[1], -direction[0])
                next_runners.append(
                    StartupRunner(
                        runner.x + clockwise[0],
                        runner.y + clockwise[1],
                        clockwise,
                        runner.main,
                        runner.offhand,
                        runner.backpack,
                    )
                )
                next_runners.append(
                    StartupRunner(
                        runner.x + counterclockwise[0],
                        runner.y + counterclockwise[1],
                        counterclockwise,
                        runner.main,
                        runner.offhand,
                        runner.backpack,
                    )
                )
                continue

            runner.x += runner.direction[0]
            runner.y += runner.direction[1]
            if not (0 <= runner.x < len(interior[0]) and 0 <= runner.y < len(interior)):
                raise ValueError(f"reader startup left room at {(runner.x, runner.y)}")
            next_runners.append(runner)
        runners = next_runners
        if len(arrivals) == reader_count:
            return tuple(arrivals)
    raise ValueError("reader startup did not create enough workers")


def verify_left_block(config: Config) -> int:
    traces: list[Trace] = []
    for block_id in range(config.l):
        interior = build_left_interior(config, block_id)
        traces.extend(
            trace_route(interior, comparison, block_id=block_id)
            for comparison in (block_id - 1, block_id + 1)
        )
        traces.extend(
            trace_route(interior, block_id, local_id, block_id)
            for local_id in range(config.k)
        )

    expected_ticks = worker_loop_ticks(config)
    if any(trace.ticks != expected_ticks for trace in traces):
        raise ValueError(f"unbalanced decoder routes: {traces}")
    if any(trace.reads != 3 for trace in traces):
        raise ValueError(f"decoder routes consume different frame sizes: {traces}")
    block_trace_count = config.k + 2
    for block_id in range(config.l):
        block_traces = traces[block_id * block_trace_count : (block_id + 1) * block_trace_count]
        if any(trace.sends != 0 for trace in block_traces[:2]):
            raise ValueError("non-matching header branch sent a payload")
        if any(trace.sends != 1 for trace in block_traces[2:]):
            raise ValueError("matching header branch did not send exactly one payload")
    if 8 + 2 * dispatch_padding_rows(config) != config.target_ticks:
        raise ValueError("dispatcher loop does not match target_ticks")
    return expected_ticks


def verify_second_block(config: Config) -> int:
    connection_rows(config)
    zero_write_trace = trace_second_worker(1)
    zero_read_trace = trace_second_worker(-1)
    regular_write_trace = trace_second_worker(1, SECOND_OTHER)
    regular_read_trace = trace_second_worker(-1, SECOND_OTHER)
    if zero_write_trace != (8, 0, 1, ()):
        raise ValueError(f"unexpected zero-worker write route: {zero_write_trace}")
    if zero_read_trace != (8, 1, 7, (7,)):
        raise ValueError(f"unexpected zero-worker read route: {zero_read_trace}")
    if regular_write_trace != (8, 0, 1, ()):
        raise ValueError(f"unexpected second-block write route: {regular_write_trace}")
    if regular_read_trace != (8, 1, 7, (7,)):
        raise ValueError(f"unexpected second-block read route: {regular_read_trace}")
    return 8


def verify_reader_pipeline(config: Config) -> tuple[int, ...]:
    if config.target_ticks != 8:
        raise ValueError("reader pipeline currently requires target_ticks=8")

    parse_read = trace_stage(
        build_parse_reader(), (3, 1), (0, 37), -VALUE_OFFSET,
        start_direction=(-1, 0),
    )
    parse_write = trace_stage(
        build_parse_reader(), (3, 1), (1, 37, -123), -VALUE_OFFSET,
        start_direction=(-1, 0),
    )
    adjust_read = trace_stage(
        build_adjust_reader(), (5, 1), (37, -VALUE_OFFSET), VALUE_OFFSET,
        start_direction=(-1, 0),
    )
    adjust_write = trace_stage(
        build_adjust_reader(), (5, 1), (37, -123), VALUE_OFFSET,
        start_direction=(-1, 0),
    )
    multiply = trace_stage(
        MULTIPLY_READER,
        (1, 1),
        (37, VALUE_OFFSET - 123, 38, VALUE_OFFSET + 456),
        PACKING_BASE,
        literal_content=frozenset(((2, 0), (3, 0))),
        literal_closures={(1, 0, (-1, 0)): PACKING_BASE},
    )
    decrement = trace_stage(
        DECREMENT_READER,
        (1, 1),
        (
            37,
            (VALUE_OFFSET - 123) * PACKING_BASE,
            38,
            (VALUE_OFFSET + 456) * PACKING_BASE,
        ),
        1,
    )
    fanout = trace_stage(
        FANOUT_READER,
        (7, 0),
        (37, (VALUE_OFFSET - 123) * PACKING_BASE - 1),
        20,
        literal_content=frozenset(((9, 1), (10, 1))),
        literal_closures={(8, 1, (-1, 0)): 20},
    )

    expected = (
        (parse_read, 24, (37, -VALUE_OFFSET)),
        (parse_write, 24, (37, -123)),
        (adjust_read, 16, (37, -VALUE_OFFSET)),
        (adjust_write, 16, (37, VALUE_OFFSET - 123)),
        (
            fanout,
            24,
            (1, 17, (VALUE_OFFSET - 123) * PACKING_BASE - 18),
        ),
    )
    for trace, ticks, outputs in expected:
        if trace.ticks != ticks or trace.outputs != outputs:
            raise ValueError(f"unexpected reader trace: {trace}")
        if trace.read_ticks[-1] - trace.read_ticks[0] >= config.target_ticks:
            raise ValueError(f"reader input window is too wide: {trace}")
        if trace.send_ticks[-1] - trace.send_ticks[0] >= config.target_ticks:
            raise ValueError(f"reader output window is too wide: {trace}")

    if multiply != StageTrace(
        ticks=16,
        outputs=(
            37,
            (VALUE_OFFSET - 123) * PACKING_BASE,
            38,
            (VALUE_OFFSET + 456) * PACKING_BASE,
        ),
        read_ticks=(0, 2, 8, 10),
        send_ticks=(1, 4, 9, 12),
    ):
        raise ValueError(f"unexpected multiply trace: {multiply}")

    if decrement != StageTrace(
        ticks=16,
        outputs=(
            37,
            (VALUE_OFFSET - 123) * PACKING_BASE - 1,
            38,
            (VALUE_OFFSET + 456) * PACKING_BASE - 1,
        ),
        read_ticks=(0, 2, 8, 10),
        send_ticks=(1, 4, 9, 12),
    ):
        raise ValueError(f"unexpected decrement trace: {decrement}")

    cycles = (
        parse_read.ticks,
        adjust_read.ticks,
        multiply.ticks,
        decrement.ticks,
        fanout.ticks,
    )
    operation_slots = (3, 2, 2, 2, 3)
    if any(cycle // count != config.target_ticks for cycle, count in zip(cycles, operation_slots)):
        raise ValueError("reader count does not cover its processing loop")
    startup_times = (
        startup_read_ticks(build_parse_reader(), (3, 1), 3),
        startup_read_ticks(build_adjust_reader(), (5, 1), 2),
        startup_read_ticks(build_multiply_reader(), (1, 1), 1),
        startup_read_ticks(build_decrement_reader(), (1, 1), 1),
        startup_read_ticks(
            build_fanout_reader(FANOUT_INTERIOR_WIDTH),
            (
                FANOUT_INTERIOR_WIDTH
                - len(FANOUT_READER[0])
                - FANOUT_TRAILING_WIDTH
                + 7,
                0,
            ),
            3,
        ),
    )
    expected_startup_times = (
        (19, 27, 35),
        (29, 37),
        (10,),
        (7,),
        (83, 91, 99),
    )
    if startup_times != expected_startup_times:
        raise ValueError(f"unexpected reader startup schedule: {startup_times}")
    if config.k != 20 or worker_count(config) != 21:
        raise ValueError("current megablock initializers require k=20 and 21 left workers")
    return cycles


def verify_decoder() -> tuple[int, int, tuple[int, ...]]:
    tile = build_decoder_tile()
    traces: list[tuple[int, int, StageTrace]] = []
    for local_id in range(20):
        for value in (-1_000_000, 0, 1_000_000):
            encoded = (value + VALUE_OFFSET) * PACKING_BASE - local_id - 1
            trace = trace_stage(
                tile,
                (3, 0),
                (encoded,),
                PACKING_BASE,
            )
            if trace.outputs != (value + VALUE_OFFSET - 1,):
                raise ValueError(
                    f"decoder produced {trace.outputs} for id={local_id}, value={value}"
                )
            traces.append((local_id, value, trace))

    synchronized_ticks = {
        trace.send_ticks[0] + 4 * local_id
        for local_id, _, trace in traces
    }
    if synchronized_ticks != {82}:
        raise ValueError("decoder outputs are not synchronized by local id")

    cycle_ticks = tuple(sorted({trace.ticks for _, _, trace in traces}))
    subtract = trace_stage(
        build_subtract_reader(),
        (1, 0),
        (VALUE_OFFSET - 1, VALUE_OFFSET + 122),
        VALUE_OFFSET - 1,
    )
    if subtract != StageTrace(
        ticks=10,
        outputs=(0, 123),
        read_ticks=(0, 5),
        send_ticks=(2, 7),
    ):
        raise ValueError(f"unexpected subtractor trace: {subtract}")
    return max(cycle_ticks), max(synchronized_ticks), cycle_ticks


def verify_decoder_startup() -> tuple[int, ...]:
    interior = build_decoder_interior()
    starts = [
        (x, y)
        for y, row in enumerate(interior)
        for x, instruction in enumerate(row)
        if instruction == "@"
    ]
    if len(starts) != 1:
        raise ValueError("decoder room must contain one starting man")

    runners = [StartupRunner(*starts[0])]
    expected = {
        (
            DECODER_PREFIX_WIDTH + tile_column * DECODER_TILE_WIDTH + 3,
            tile_row * DECODER_TILE_HEIGHT,
        )
        for tile_row in range(DECODER_ROWS)
        for tile_column in range(DECODER_COLUMNS)
    }
    arrivals: dict[tuple[int, int], tuple[int, int, tuple[int, int]]] = {}
    for tick in range(200):
        positions = [(runner.x, runner.y) for runner in runners]
        if len(positions) != len(set(positions)):
            raise ValueError(f"decoder startup collision at tick {tick}: {positions}")

        next_runners: list[StartupRunner] = []
        moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for runner in runners:
            start = (runner.x, runner.y)
            if start in expected:
                arrivals[start] = (tick, runner.offhand, runner.direction)
                continue
            instruction = interior[runner.y][runner.x]
            if instruction == "H":
                continue
            if instruction == "M":
                runner.offhand = runner.main
            elif instruction == "*":
                runner.main *= runner.offhand
            elif instruction.isdigit():
                runner.main = int(instruction)
            if instruction == "Y":
                direction_x, direction_y = runner.direction
                directions = (
                    (-direction_y, direction_x),
                    (direction_y, -direction_x),
                )
                for next_direction_x, next_direction_y in directions:
                    next_x = runner.x + next_direction_x
                    next_y = runner.y + next_direction_y
                    next_runners.append(
                        StartupRunner(
                            runner.x + next_direction_x,
                            runner.y + next_direction_y,
                            (next_direction_x, next_direction_y),
                            runner.main,
                            runner.offhand,
                            runner.backpack,
                        )
                    )
                continue
            if instruction == ">":
                runner.direction = (1, 0)
            elif instruction == "<":
                runner.direction = (-1, 0)
            elif instruction == "^":
                runner.direction = (0, -1)
            elif instruction == "v":
                runner.direction = (0, 1)
            next_x = runner.x + runner.direction[0]
            next_y = runner.y + runner.direction[1]
            if not (
                0 <= next_x < len(interior[0])
                and 0 <= next_y < len(interior)
            ):
                raise ValueError(
                    f"decoder startup left room at {(next_x, next_y)} on tick {tick}"
                )
            runner.x = next_x
            runner.y = next_y
            next_runners.append(runner)
            moves.append((start, (next_x, next_y)))

        next_positions = [(runner.x, runner.y) for runner in next_runners]
        if len(next_positions) != len(set(next_positions)):
            raise ValueError(
                f"decoder startup destination collision at tick {tick}: {next_positions}"
            )
        if any(
            first_start == second_end and first_end == second_start
            for move_index, (first_start, first_end) in enumerate(moves)
            for second_start, second_end in moves[move_index + 1 :]
        ):
            raise ValueError(f"decoder startup swap collision at tick {tick}")
        runners = next_runners
        if len(arrivals) == DECODER_COLUMNS * DECODER_ROWS:
            if set(arrivals) != expected:
                raise ValueError(f"decoder workers reached wrong cells: {arrivals}")
            if any(
                offhand != PACKING_BASE or direction != (1, 0)
                for _, offhand, direction in arrivals.values()
            ):
                raise ValueError(f"decoder workers have wrong offhand: {arrivals}")
            subtract_startup = startup_read_ticks(
                build_subtract_reader(), (3, 1), 1
            )
            if subtract_startup != (18,):
                raise ValueError(
                    f"unexpected subtractor startup: {subtract_startup}"
                )
            return tuple(sorted(tick for tick, _, _ in arrivals.values()))
    raise ValueError("decoder startup did not create all workers")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--l", type=int, default=5)
    parser.add_argument("--target-ticks", type=int, default=8)
    parser.add_argument("-o", "--output", type=Path)
    arguments = parser.parse_args()

    config = Config(arguments.k, arguments.l, arguments.target_ticks)
    route_ticks = verify_left_block(config)
    second_ticks = verify_second_block(config)
    reader_cycles = verify_reader_pipeline(config)
    decoder_ticks, decoder_send_tick, decoder_cycles = verify_decoder()
    decoder_startup = verify_decoder_startup()
    workers = worker_count(config)
    output = arguments.output or Path(__file__).with_name(
        f"direct-memory-shifted-k{config.k}.man"
    )
    output.write_text(render_program(config), encoding="ascii")
    print(
        f"wrote {output} (k={config.k}, l={config.l}, target={config.target_ticks}, "
        f"worker loop={route_ticks}, workers={workers}, "
        f"worker padding rows={worker_padding_rows(config)}, "
        f"dispatcher loop={config.target_ticks}, second worker={second_ticks}, "
        f"reader cycles={reader_cycles}, megablocks={config.l}, "
        f"decoder max loop={decoder_ticks}, decoder sync={decoder_send_tick}, "
        f"decoder cycles={decoder_cycles}, decoder=persistent-reset, "
        f"decoder startup={decoder_startup[0]}..{decoder_startup[-1]}, "
        f"worker pipes={config.k * config.l}x{PIPE_LENGTH}, "
        f"decrement buffer={DECREMENT_INPUT_PIPE_LENGTH}, "
        f"fanout pipes={config.l}x3)"
    )


if __name__ == "__main__":
    main()
