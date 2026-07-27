#!/usr/bin/env python3
"""Derive a two-tick worker-dispatch proof of concept from manual_1.man.

The existing six-tick dispatcher is replaced by four robots on one eight-tick
loop.  Their first masks are max..max-3 and each loop subtracts four, so the
single worker lane still receives masks in strict descending order every two
ticks.  The shared mask-return FIFO stays lane-safe only while its transport
delay is shorter than the worker loop, so the generated queue is kept
between the in-flight worker count and loop latency.  manual_1.man is read-only
input and is never overwritten.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import littleman as lm

from interpreter.parser import load_program


SOURCE = Path(__file__).with_name("manual_1.man")
OUTPUT = Path(__file__).with_name("dispatch2-no-cache.man")
SEARCH_LEFT = 32
SEARCH_TOP = -3
SEARCH_RIGHT = 72
SEARCH_BOTTOM = 89


def load_cells(path: Path) -> dict[tuple[int, int], str]:
    rows = path.read_text(encoding="ascii").splitlines()
    return {
        (x, y): character
        for y, row in enumerate(rows)
        for x, character in enumerate(row)
        if character != " "
    }


def draw_room(
    cells: dict[tuple[int, int], str], left: int, top: int, width: int, height: int
) -> None:
    right = left + width - 1
    bottom = top + height - 1
    for x in range(left, right + 1):
        cells[x, top] = "-"
        cells[x, bottom] = "-"
    for y in range(top, bottom + 1):
        cells[left, y] = "|"
        cells[right, y] = "|"
    for point in ((left, top), (right, top), (left, bottom), (right, bottom)):
        cells[point] = "+"


def put(cells: dict[tuple[int, int], str], x: int, y: int, character: str) -> None:
    if character == " ":
        cells.pop((x, y), None)
    else:
        cells[x, y] = character


def text(cells: dict[tuple[int, int], str], x: int, y: int, source: str) -> None:
    for offset, character in enumerate(source):
        put(cells, x + offset, y, character)


def overlay_pipe(
    cells: dict[tuple[int, int], str],
    points: list[tuple[int, int]],
    *,
    end_direction: str | None = None,
) -> None:
    pipe = lm.Program()
    pipe.pipe(points, end_direction=end_direction)
    for point, character in pipe.cells.items():
        old = cells.get(point, " ")
        if old != " " and old != character:
            raise ValueError(f"pipe collision at {point}: {old!r} versus {character!r}")
        cells[point] = character


def clear_original_rooms_and_pipes(
    cells: dict[tuple[int, int], str],
) -> tuple[list[str], list[str]]:
    program = load_program(SOURCE)
    input_room = program.rooms[1]
    relay_room = program.rooms[4]
    relay_rows = [
        "".join(program.grid[y][relay_room.left : relay_room.right + 1])
        for y in range(relay_room.top, relay_room.bottom + 1)
    ]
    input_rows = [
        "".join(program.grid[y][input_room.left : input_room.right + 1])
        for y in range(input_room.top, input_room.bottom + 1)
    ]

    for room in (input_room, relay_room):
        for y in range(room.top, room.bottom + 1):
            for x in range(room.left, room.right + 1):
                cells.pop((x, y), None)
    for pipe_id in (0, 8, 13):
        for point in program.pipes[pipe_id].cells:
            cells.pop(point, None)
    return input_rows, relay_rows


def widen_search_room(cells: dict[tuple[int, int], str]) -> None:
    for x in range(SEARCH_LEFT, 45):
        cells.pop((x, 1), None)
    for y in range(SEARCH_TOP, SEARCH_BOTTOM + 1):
        for x in range(44, SEARCH_RIGHT + 1):
            cells.pop((x, y), None)
    draw_room(
        cells,
        SEARCH_LEFT,
        SEARCH_TOP,
        SEARCH_RIGHT - SEARCH_LEFT + 1,
        SEARCH_BOTTOM - SEARCH_TOP + 1,
    )


def move_auxiliary_rooms(
    cells: dict[tuple[int, int], str], input_rows: list[str], relay_rows: list[str]
) -> None:
    for y, row in enumerate(relay_rows):
        text(cells, 75, y, row)
    for y, row in enumerate(input_rows):
        text(cells, 96, y, row)

    # I -> compact input memory, routed above the rooms.
    overlay_pipe(
        cells,
        [(97, -1), (97, -7), (25, -7), (25, -1)],
        end_direction="S",
    )

    # Search-room mask sends -> FIFO relay.  Adjacent side walls keep this leg
    # minimal and leave the queue capacity in the return belt.
    overlay_pipe(cells, [(73, 4), (74, 4)], end_direction="E")

    # FIFO relay -> search-room restore input.  The belt lives entirely in the
    # unused right-side space except for its final approach above the search
    # room.  Its length remains below the worker s-to-r loop latency.
    overlay_pipe(
        cells,
        [
            (83, 3),
            (84, 3),
            (84, 80),
            (95, 80),
            (95, -5),
            (39, -5),
            (39, -4),
        ],
        end_direction="S",
    )


def clear_dispatch_area(cells: dict[tuple[int, int], str]) -> None:
    # Preserve the original initializer and worker lane, but remove the old
    # six-tick return path and all newly-created upper-room cells.
    for y in range(SEARCH_TOP + 1, 3):
        for x in range(41, SEARCH_RIGHT):
            cells.pop((x, y), None)
    for x in range(33, SEARCH_RIGHT):
        for y in range(SEARCH_TOP + 1, 2):
            cells.pop((x, y), None)
    for x in range(35, SEARCH_RIGHT):
        cells.pop((x, 2), None)


def build_dispatch_convoy(cells: dict[tuple[int, int], str]) -> None:
    # Keep the original Y at (34,2): it emits mask 2^20-1.  Its continuing
    # child leaves east and initializes the four phased carousel robots.
    put(cells, 34, 2, "Y")
    put(cells, 45, 2, "v")
    # Carousel workers inherit B=4.  Normalize it back to the worker contract
    # B=1 after the mask has been sent and saved in the backpack.
    put(cells, 33, 6, "M")
    put(cells, 33, 7, "1")
    put(cells, 33, 8, "W")
    put(cells, 45, 60, ">")
    put(cells, 60, 60, "^")
    put(cells, 60, 5, "Y")
    put(cells, 58, 5, "Y")
    put(cells, 62, 5, "Y")

    # Separate eight-tick carousel.  Each robot subtracts four immediately
    # before its next Y.  A zero mask goes west and joins the worker lane,
    # providing the original no-solution sentinel.
    put(cells, 34, -2, "Y")
    put(cells, 33, -2, "v")
    put(cells, 33, 0, "v")
    put(cells, 35, -2, ">")
    put(cells, 36, -2, "v")
    put(cells, 36, 0, "<")
    put(cells, 35, 0, "<")
    put(cells, 34, 0, "X")
    put(cells, 34, -1, "-")

    # Restore the original zero-mask escape above HXH.  It rejoins the existing
    # x=43 vertical output path without sharing the startup corridor on y=2.
    put(cells, 41, 0, ">")
    put(cells, 43, 0, "v")

    # Left/top branch: max+3, first carousel result max-1.
    put(cells, 58, 4, "<")
    text(cells, 52, 4, "W4M+++")
    put(cells, 50, 4, "v")
    put(cells, 50, 12, "<")
    put(cells, 49, 12, "^")
    put(cells, 49, 1, "<")

    # Left/bottom branch: max+2, two ticks behind left/top.
    put(cells, 58, 6, "<")
    text(cells, 53, 6, "W4M++")
    put(cells, 52, 6, "v")
    put(cells, 52, 14, "<")
    put(cells, 51, 14, "^")
    put(cells, 51, 1, "<")

    # Right/top branch: max+1, another two ticks behind.
    put(cells, 62, 4, ">")
    text(cells, 63, 4, "+M4W")
    put(cells, 70, 4, "^")
    put(cells, 70, 1, "<")

    # Right/bottom branch: max, with a two-tick bump before its ascent.
    put(cells, 62, 6, ">")
    text(cells, 63, 6, "M4W")
    put(cells, 66, 6, "v")
    put(cells, 66, 7, ">")
    put(cells, 67, 7, "^")
    put(cells, 67, 6, ">")
    put(cells, 69, 6, "^")
    put(cells, 69, 1, "<")

    # All setup branches merge below the carousel, then join after its only
    # vertical crossing so later setup robots cannot collide with it.
    put(cells, 36, 1, "^")


def render(cells: dict[tuple[int, int], str]) -> str:
    points = [point for point, character in cells.items() if character != " "]
    min_x = min(x for x, _ in points)
    max_x = max(x for x, _ in points)
    min_y = min(y for _, y in points)
    max_y = max(y for _, y in points)
    rows = []
    for y in range(min_y, max_y + 1):
        rows.append(
            "".join(cells.get((x, y), " ") for x in range(min_x, max_x + 1)).rstrip()
        )
    return "\n".join(rows) + "\n"


def build() -> str:
    cells = load_cells(SOURCE)
    input_rows, relay_rows = clear_original_rooms_and_pipes(cells)
    widen_search_room(cells)
    move_auxiliary_rooms(cells, input_rows, relay_rows)
    clear_dispatch_area(cells)
    build_dispatch_convoy(cells)
    return render(cells)


def main() -> None:
    program = build()
    OUTPUT.write_text(program, encoding="ascii")
    parsed = load_program(OUTPUT)
    footprint = max(parsed.width, parsed.height) ** 2
    print(f"wrote {OUTPUT}")
    print(f"dimensions {parsed.width}x{parsed.height}, footprint {footprint}")


if __name__ == "__main__":
    main()
