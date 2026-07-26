"""Build the synchronized direct-memory layout incrementally."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


HEADER = (
    ">r-v ",
    "  vXv",
    "  rrr",
    "  rbr",
    "   r ",
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
    "  > V",
)

WORKER_RETURN = "^   <"
DISPATCH_LOOP = ">m aH"

SECOND_FIRST = (
    "  vsW<",
    " >>WrX",
    " +^  <",
)

SECOND_OTHER = (
    ">^vsW<",
    "^Y>WrX",
    " +^  <",
)

SECOND_INITIALIZER = (
    " ^ W1<",
    ">W*-W^",
    "^`02`<",
    "     M",
    "@9M{{^",
)

LEFT_INITIALIZER = (
    "^b~*<",
    "@3M7^",
)

DECODER_BASE = (
    "> `2359295`W-v    ",
    "^bW/RW*4M5<sa<m<  ",
    "            >m asv",
    "          ^      <",
)

DECODER_SPLIT = DECODER_BASE[:3] + (
    "        vY^      <",
    "        <^        ",
)

DECODER_STEAL = DECODER_BASE + (
    "          ^       ",
)

VALUE_OFFSET = 9 << 18

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
    ">rsr*s v",
    "^ s*rsr<",
    " @`20`M^",
)

FANOUT_READER = (
    "         @3b>  dH",
    ">r/SWSW r-Sv^ mYv",
    "^W`02`     <    <",
)

STARTUP_DELAY_PREFIX = (
    "@  v  >",
    "v  <  ^",
    ">     ^",
)

LEFT_ROOM_X = 0
LEFT_ROOM_Y = 0
PIPE_LENGTH = 2
MULTIPLIER_INPUT_PIPE_LENGTH = 16
MULTIPLIER_OUTPUT_PIPE_LENGTH = 16
RIGHT_ROOM_Y = len(HEADER)
READER_ROOM_Y = 0
FANOUT_ROOM_Y = 5
MEGABLOCK_Y = 10
DECODER_COLUMNS = 4
DECODER_ROWS = 4
DECODER_BASE_WIDTH = 18
DECODER_PREFIX_WIDTH = 12
DECODER_TILE_WIDTH = DECODER_PREFIX_WIDTH + DECODER_BASE_WIDTH
DECODER_TILE_HEIGHT = 5
DECODER_ROW_SHIFTS = (0, 1, 2, 6)
DECODER_INTERIOR_WIDTH = 132
FANOUT_STARTUP_DELAY = 56


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
    return 26 + 7 * config.k


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


def build_parse_reader() -> tuple[str, ...]:
    return normalize_rows(PARSE_READER)


def build_adjust_reader() -> tuple[str, ...]:
    return add_startup_delay(ADJUST_READER_CORE)


def build_multiply_reader() -> tuple[str, ...]:
    return normalize_rows(MULTIPLY_READER)


def build_fanout_reader(width: int) -> tuple[str, ...]:
    reader = normalize_rows(FANOUT_READER)
    if width < len(reader[0]):
        raise ValueError("fanout room is too narrow")
    padding = " " * (width - len(reader[0]))
    rows = [list(padding + row) for row in reader]
    old_start = rows[0].index("@")
    new_start = old_start - FANOUT_STARTUP_DELAY
    if new_start < 0 or any(rows[0][x] != " " for x in range(new_start, old_start)):
        raise ValueError("fanout room has no space for its startup delay")
    rows[0][old_start] = " "
    rows[0][new_start] = "@"
    return tuple("".join(row) for row in rows)


def build_decoder_interior() -> tuple[str, ...]:
    canvas = [
        [" "] * DECODER_INTERIOR_WIDTH
        for _ in range(DECODER_ROWS * DECODER_TILE_HEIGHT)
    ]
    for tile_row in range(DECODER_ROWS):
        for tile_column in range(DECODER_COLUMNS):
            tile = build_decoder_tile(split=tile_column != 0)
            left = tile_column * DECODER_TILE_WIDTH + DECODER_ROW_SHIFTS[tile_row]
            top = tile_row * DECODER_TILE_HEIGHT
            for row_offset, row in enumerate(tile):
                for column_offset, instruction in enumerate(row):
                    if instruction != " ":
                        canvas[top + row_offset][left + column_offset] = instruction

    spine_x = DECODER_COLUMNS * DECODER_TILE_WIDTH + max(DECODER_ROW_SHIFTS) + 2
    detour_x = spine_x + 1
    canvas[0][spine_x] = "@"
    canvas[0][detour_x] = "v"
    for lane in range(DECODER_ROWS):
        lane_y = lane * DECODER_TILE_HEIGHT + DECODER_TILE_HEIGHT - 1
        canvas[lane_y][spine_x] = "Y"
        canvas[lane_y][detour_x] = "H" if lane == DECODER_ROWS - 1 else "v"
        if lane == 0:
            canvas[lane_y - 1][spine_x] = "v"
            canvas[lane_y - 1][detour_x] = "<"
        if lane < DECODER_ROWS - 1:
            next_turn_y = lane_y + DECODER_TILE_HEIGHT - 1
            canvas[next_turn_y][spine_x] = "v"
            canvas[next_turn_y][detour_x] = "<"
    return tuple("".join(row) for row in canvas)


def build_decoder_tile(split: bool) -> tuple[str, ...]:
    base = DECODER_SPLIT if split else DECODER_STEAL
    canvas = [[" "] * DECODER_TILE_WIDTH for _ in range(DECODER_TILE_HEIGHT)]
    for row_offset, row in enumerate(base):
        for column_offset, instruction in enumerate(row):
            if instruction != " ":
                canvas[row_offset][DECODER_PREFIX_WIDTH + column_offset] = instruction

    canvas[1][DECODER_PREFIX_WIDTH] = "X"
    canvas[0][1] = ">"
    prefix = " ^b`31`W+WN1"
    for column, instruction in enumerate(prefix):
        if instruction != " ":
            canvas[1][column] = instruction
    return tuple("".join(row) for row in canvas)


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
    return SECOND_FIRST + SECOND_OTHER * (config.k - 1) + SECOND_INITIALIZER


def connection_rows(config: Config) -> tuple[int, ...]:
    left_rows = tuple(
        LEFT_ROOM_Y + 1 + len(HEADER) + 6 * pair + offset
        for pair in range(config.k // 2)
        for offset in (1, 4)
    )
    right_rows = tuple(RIGHT_ROOM_Y + 2 + 3 * worker for worker in range(config.k))
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
    left_width = len(left[0])
    local_pipe_x = LEFT_ROOM_X + left_width + 2
    local_right_x = local_pipe_x + PIPE_LENGTH
    megablock_width = local_right_x + len(right[0]) + 2
    width = megablock_width * config.l
    fanout_reader = build_fanout_reader(width - 2)
    decoder = build_decoder_interior()
    pipeline_width = sum(
        len(room[0]) + 2 for room in (multiply_reader, adjust_reader, parse_reader)
    ) + MULTIPLIER_INPUT_PIPE_LENGTH + 2 * PIPE_LENGTH + 3
    if pipeline_width > width:
        raise ValueError("reader pipeline is wider than the megablocks")
    pipeline_x = width - pipeline_width
    multiply_x = pipeline_x
    adjust_x = (
        multiply_x + len(multiply_reader[0]) + 2 + MULTIPLIER_INPUT_PIPE_LENGTH
    )
    parse_x = adjust_x + len(adjust_reader[0]) + 2 + PIPE_LENGTH
    input_x = parse_x + len(parse_reader[0]) + 2 + PIPE_LENGTH
    megablock_height = max(
        LEFT_ROOM_Y + len(left) + 2,
        RIGHT_ROOM_Y + len(right) + 2,
    )
    storage_bottom = MEGABLOCK_Y + RIGHT_ROOM_Y + len(right) + 1
    decoder_top = storage_bottom + 2
    decoder_right = len(decoder[0]) + 1
    output_left = decoder_right + PIPE_LENGTH + 1
    output_top = decoder_top + 1
    width = max(width, output_left + 3)
    height = max(
        MEGABLOCK_Y + megablock_height,
        decoder_top + len(decoder) + 2,
        output_top + 3,
    )
    canvas = [[" "] * width for _ in range(height)]

    draw_room(canvas, multiply_x, READER_ROOM_Y, multiply_reader)
    draw_room(canvas, adjust_x, READER_ROOM_Y, adjust_reader)
    draw_room(canvas, parse_x, READER_ROOM_Y, parse_reader)
    draw_room(canvas, input_x, READER_ROOM_Y + 1, ("I",))
    for left_room, right_room in (
        (multiply_x, adjust_x),
        (adjust_x, parse_x),
        (parse_x, input_x),
    ):
        left_wall = next(
            room_x + len(room[0]) + 1
            for room_x, room in (
                (multiply_x, multiply_reader),
                (adjust_x, adjust_reader),
                (parse_x, parse_reader),
            )
            if room_x == left_room
        )
        for x in range(left_wall + 1, right_room):
            canvas[2][x] = "<"

    draw_room(canvas, 0, FANOUT_ROOM_Y, fanout_reader)
    multiplier_right = multiply_x + len(multiply_reader[0]) + 1
    multiplier_output_end = multiplier_right + MULTIPLIER_OUTPUT_PIPE_LENGTH - 1
    for x in range(multiplier_right + 1, multiplier_output_end):
        canvas[3][x] = ">"
    canvas[3][multiplier_output_end] = "v"
    canvas[4][multiplier_output_end] = "v"

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
            for x in range(offset + local_pipe_x, offset + local_pipe_x + PIPE_LENGTH):
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

    draw_room(canvas, 0, decoder_top, decoder)
    draw_room(canvas, output_left, output_top, ("O",))
    output_y = output_top + 1
    for x in range(decoder_right + 1, output_left):
        canvas[output_y][x] = ">"
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
    message: int, interior: tuple[str, ...] = SECOND_FIRST
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
) -> StageTrace:
    interior = normalize_rows(interior)
    values = iter(inputs)
    x, y = start
    direction = start_direction
    main = 0
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


def verify_reader_pipeline(config: Config) -> tuple[int, int, int, int]:
    if config.target_ticks != 8:
        raise ValueError("reader pipeline currently requires target_ticks=8")

    parse_read = trace_stage(PARSE_READER, (16, 1), (0, 37), -VALUE_OFFSET)
    parse_write = trace_stage(PARSE_READER, (16, 1), (1, 37, -123), -VALUE_OFFSET)
    adjust_read = trace_stage(ADJUST_READER_CORE, (10, 1), (37, -VALUE_OFFSET), VALUE_OFFSET)
    adjust_write = trace_stage(ADJUST_READER_CORE, (10, 1), (37, -123), VALUE_OFFSET)
    multiply = trace_stage(
        MULTIPLY_READER,
        (1, 0),
        (37, VALUE_OFFSET - 123, 38, VALUE_OFFSET + 456),
        20,
        literal_content=frozenset(((3, 2), (4, 2))),
        literal_closures={(2, 2, (-1, 0)): 20},
    )
    fanout = trace_stage(
        FANOUT_READER,
        (1, 1),
        (37, (VALUE_OFFSET - 123) * 20),
        20,
        literal_content=frozenset(((3, 2), (4, 2))),
        literal_closures={(2, 2, (-1, 0)): 20},
    )

    expected = (
        (parse_read, 24, (37, -VALUE_OFFSET)),
        (parse_write, 24, (37, -123)),
        (adjust_read, 16, (37, -VALUE_OFFSET)),
        (adjust_write, 16, (37, VALUE_OFFSET - 123)),
        (fanout, 24, (1, 17, (VALUE_OFFSET - 123) * 20 - 17)),
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
        outputs=(37, (VALUE_OFFSET - 123) * 20, 38, (VALUE_OFFSET + 456) * 20),
        read_ticks=(0, 2, 8, 10),
        send_ticks=(1, 4, 9, 12),
    ):
        raise ValueError(f"unexpected multiply trace: {multiply}")

    cycles = (parse_read.ticks, adjust_read.ticks, multiply.ticks, fanout.ticks)
    operation_slots = (3, 2, 2, 3)
    if any(cycle // count != config.target_ticks for cycle, count in zip(cycles, operation_slots)):
        raise ValueError("reader count does not cover its processing loop")
    startup_times = (
        startup_read_ticks(build_parse_reader(), (16, 1), 3),
        startup_read_ticks(build_adjust_reader(), (16, 1), 2),
        startup_read_ticks(build_multiply_reader(), (6, 1), 1),
        startup_read_ticks(
            build_fanout_reader(DECODER_INTERIOR_WIDTH),
            (DECODER_INTERIOR_WIDTH - len(FANOUT_READER[0]) + 1, 1),
            3,
        ),
    )
    expected_startup_times = ((17, 25, 33), (27, 35), (8,), (83, 91, 99))
    if startup_times != expected_startup_times:
        raise ValueError(f"unexpected reader startup schedule: {startup_times}")
    if config.k != 20 or worker_count(config) != 21:
        raise ValueError("current megablock initializers require k=20 and 21 left workers")
    return cycles


def verify_decoder() -> tuple[int, int, tuple[int, ...]]:
    tile = build_decoder_tile(split=False)
    literal_content = frozenset(
        (DECODER_PREFIX_WIDTH + x, 0) for x in range(3, 10)
    ) | frozenset(((4, 1), (5, 1)))
    literal_closures = {
        (DECODER_PREFIX_WIDTH + 10, 0, (1, 0)): VALUE_OFFSET - 1,
        (3, 1, (-1, 0)): 13,
    }
    traces: list[tuple[int, int, StageTrace]] = []
    for local_id in range(1, 20):
        for value in (-1_000_000, 0, 1_000_000):
            encoded = (value + VALUE_OFFSET) * 20 - local_id
            trace = trace_stage(
                tile,
                (DECODER_PREFIX_WIDTH + 4, 1),
                (encoded,),
                20,
                literal_content,
                literal_closures,
                (-1, 0),
            )
            if trace.outputs != (value,):
                raise ValueError(
                    f"decoder produced {trace.outputs} for id={local_id}, value={value}"
                )
            traces.append((local_id, value, trace))

    synchronized_send_tick = traces[0][2].send_ticks[0] + 4 * traces[0][0]
    if any(
        trace.send_ticks[0] + 4 * local_id != synchronized_send_tick
        for local_id, _, trace in traces
    ):
        raise ValueError("decoder outputs are not synchronized by local id")

    id_zero = trace_stage(
        tile,
        (DECODER_PREFIX_WIDTH + 4, 1),
        (VALUE_OFFSET * 20,),
        20,
        literal_content,
        literal_closures,
        (-1, 0),
    )
    if id_zero.outputs != (0,) or not (
        synchronized_send_tick - 8 < id_zero.send_ticks[0] < synchronized_send_tick + 8
    ):
        raise ValueError(f"unexpected local-id-zero behavior: {id_zero}")

    cycle_ticks = tuple(sorted({trace.ticks for _, _, trace in traces} | {id_zero.ticks}))
    if max(cycle_ticks) > DECODER_COLUMNS * DECODER_ROWS * 8:
        raise ValueError("decoder grid does not have enough workers for 8-tick input")
    return max(cycle_ticks), synchronized_send_tick, cycle_ticks


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

    runners = [(*starts[0], 1, 0)]
    arrivals: dict[tuple[int, int], int] = {}
    for tick in range(200):
        positions = [(x, y) for x, y, _, _ in runners]
        if len(positions) != len(set(positions)):
            raise ValueError(f"decoder startup collision at tick {tick}: {positions}")

        next_runners: list[tuple[int, int, int, int]] = []
        moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for x, y, direction_x, direction_y in runners:
            instruction = interior[y][x]
            if instruction == "R":
                arrivals[(x, y)] = tick
                continue
            if instruction == "H":
                continue
            if instruction == "Y":
                directions = (
                    (-direction_y, direction_x),
                    (direction_y, -direction_x),
                )
                for next_direction_x, next_direction_y in directions:
                    next_x = x + next_direction_x
                    next_y = y + next_direction_y
                    next_runners.append(
                        (next_x, next_y, next_direction_x, next_direction_y)
                    )
                continue
            if instruction == ">":
                direction_x, direction_y = 1, 0
            elif instruction == "<":
                direction_x, direction_y = -1, 0
            elif instruction == "^":
                direction_x, direction_y = 0, -1
            elif instruction in "vV":
                direction_x, direction_y = 0, 1
            next_x = x + direction_x
            next_y = y + direction_y
            if not (
                0 <= next_x < len(interior[0])
                and 0 <= next_y < len(interior)
            ):
                raise ValueError(
                    f"decoder startup left room at {(next_x, next_y)} on tick {tick}"
                )
            next_runners.append((next_x, next_y, direction_x, direction_y))
            moves.append(((x, y), (next_x, next_y)))

        next_positions = [(x, y) for x, y, _, _ in next_runners]
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
            expected = {
                (tile_column * DECODER_TILE_WIDTH
                 + DECODER_ROW_SHIFTS[tile_row]
                 + DECODER_PREFIX_WIDTH
                 + 4,
                 tile_row * DECODER_TILE_HEIGHT + 1)
                for tile_row in range(DECODER_ROWS)
                for tile_column in range(DECODER_COLUMNS)
            }
            if set(arrivals) != expected:
                raise ValueError(f"decoder workers reached wrong cells: {arrivals}")
            return tuple(sorted(arrivals.values()))
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
    output = arguments.output or Path(__file__).with_name(f"direct-memory-left-k{config.k}.man")
    output.write_text(render_program(config), encoding="ascii")
    print(
        f"wrote {output} (k={config.k}, l={config.l}, target={config.target_ticks}, "
        f"worker loop={route_ticks}, workers={workers}, "
        f"worker padding rows={worker_padding_rows(config)}, "
        f"dispatcher loop={config.target_ticks}, second worker={second_ticks}, "
        f"reader cycles={reader_cycles}, megablocks={config.l}, "
        f"decoder max loop={decoder_ticks}, decoder sync={decoder_send_tick}, "
        f"decoder cycles={decoder_cycles}, decoder id0=private-detour, "
        f"decoder startup={decoder_startup[0]}..{decoder_startup[-1]}, "
        f"worker pipes={config.k * config.l}x{PIPE_LENGTH}, "
        f"multiplier buffers={MULTIPLIER_INPUT_PIPE_LENGTH}/"
        f"{MULTIPLIER_OUTPUT_PIPE_LENGTH}, fanout pipes={config.l}x3)"
    )


if __name__ == "__main__":
    main()
