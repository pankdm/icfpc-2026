"""Generate compact multi-belt solutions based on the hand-optimized N=2 layout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import littleman as lm


CELL_COUNT = 100


def put_non_spaces(program: lm.Program, x: int, y: int, rows: tuple[str, ...]) -> None:
    for row_offset, row in enumerate(rows):
        for column_offset, character in enumerate(row):
            if character != " ":
                program.put(x + column_offset, y + row_offset, character)


def add_input_proxy(program: lm.Program) -> None:
    program.room(0, 0, 6, 10)
    put_non_spaces(
        program,
        1,
        1,
        ("@9Mv", ">>v*", " +sW", "0r *", "ss *", "rr *", "X^ W", "^r<<"),
    )


def add_output_proxy(program: lm.Program) -> None:
    program.room(9, 0, 7, 8)
    put_non_spaces(
        program,
        10,
        1,
        ("@9M*v", ">rXvW", "  - *", "  s *", "^ <<*", "^  W<"),
    )


def add_io(program: lm.Program) -> None:
    program.input_room(6, 0)
    program.output_room(6, 5)
    program.put(6, 3, "v")
    program.put(6, 4, "<")
    program.put(7, 4, "v")
    program.put(8, 4, "<")
    program.put(6, 9, ">")
    program.text(7, 9, "------")
    program.put(13, 9, "v")
    program.put(14, 8, "^")
    program.put(14, 9, "^")


def add_relay(program: lm.Program, left: int) -> None:
    program.room(left, 0, 4, 6)
    put_non_spaces(program, left + 1, 1, ("@v", ">v", "sr", "^<"))


def add_controller(program: lm.Program, belt_count: int, block_size: int) -> None:
    bottom = 15 + 4 * belt_count
    program.room(0, 10, 15, bottom - 9)

    program.text(1, 11, f"vrbW/rW{belt_count}<S<")
    put_non_spaces(program, 1, 12, ("W > Ws  ^ 0",))

    worker = (
        "> b> rdWXvdv<",
        "   ^ms< sWmsW",
        "    >sv 0s^<b",
        "  ^sXr<W<<>W^",
    )
    for belt in range(belt_count):
        top = 13 + 4 * belt
        put_non_spaces(program, 1, top, worker)
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


def expanded_cells(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    cells = []
    for start, end in zip(points, points[1:]):
        delta_x = (end[0] > start[0]) - (end[0] < start[0])
        delta_y = (end[1] > start[1]) - (end[1] < start[1])
        length = abs(end[0] - start[0]) + abs(end[1] - start[1])
        cells.extend(
            (start[0] + offset * delta_x, start[1] + offset * delta_y)
            for offset in range(length)
        )
    cells.append(points[-1])
    return cells


def incoming_pipe(start: tuple[int, int], left: int, end: tuple[int, int]) -> list[tuple[int, int]]:
    points = [start]
    current_x, current_y = start
    alternate_x = left
    while current_y < end[1]:
        current_y += 1
        points.append((current_x, current_y))
        if current_y < end[1]:
            current_x = alternate_x if current_x != alternate_x else left + 1
            points.append((current_x, current_y))
    if current_x != end[0]:
        points.append((end[0], current_y))
    return points


def return_pipe(start: tuple[int, int], left: int) -> list[tuple[int, int]]:
    near = left + 2
    far = left + 3
    return [
        start,
        (near, start[1]),
        (near, start[1] + 1),
        (far, start[1] + 1),
        (far, start[1]),
        (far, 9),
        (near, 9),
        (near, 8),
        (far, 8),
        (far, 7),
        (near, 7),
        (near, 6),
    ]


def verify_belt_routing(belt_count: int) -> None:
    incoming = {belt: (15, 14 + 4 * belt) for belt in range(belt_count)}
    outgoing = {belt: (15, 15 + 4 * belt) for belt in range(belt_count)}
    incoming[-1] = (13, 9)
    outgoing[-1] = (14, 9)

    def nearest(operation: tuple[int, int], attachments: dict[int, tuple[int, int]]) -> int:
        return min(
            attachments,
            key=lambda belt: (
                abs(operation[0] - attachments[belt][0])
                + abs(operation[1] - attachments[belt][1]),
                attachments[belt][1],
                attachments[belt][0],
            ),
        )

    for belt in range(belt_count):
        top = 13 + 4 * belt
        for operation in ((6, top), (6, top + 3)):
            assert nearest(operation, incoming) == belt
        for operation in ((5, top + 1), (9, top + 1), (5, top + 2), (10, top + 2), (4, top + 3)):
            assert nearest(operation, outgoing) == belt


def add_belt_pipes(program: lm.Program, belt: int) -> None:
    relay_left = 16 + 4 * belt
    incoming_y = 14 + 4 * belt
    outgoing_y = incoming_y + 1

    incoming = incoming_pipe((relay_left + 1, 6), relay_left, (15, incoming_y))
    outgoing = return_pipe((15, outgoing_y), relay_left)
    assert len(expanded_cells(incoming)) == len(set(expanded_cells(incoming)))
    assert len(expanded_cells(outgoing)) == len(set(expanded_cells(outgoing)))
    program.pipe(incoming)
    program.pipe(outgoing)


def build(belt_count: int) -> lm.Program:
    if belt_count not in (3, 4):
        raise ValueError("this compact layout currently supports N=3 or N=4")
    verify_belt_routing(belt_count)
    block_size = (CELL_COUNT + belt_count - 1) // belt_count
    program = lm.Program()
    add_input_proxy(program)
    add_output_proxy(program)
    add_io(program)
    add_controller(program, belt_count, block_size)
    for belt in range(belt_count):
        add_relay(program, 16 + 4 * belt)
    for belt in range(belt_count):
        add_belt_pipes(program, belt)
    return program


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("n", type=int, choices=(3, 4))
    parser.add_argument("-o", "--output", type=Path)
    arguments = parser.parse_args()

    output = arguments.output or Path(__file__).with_name(f"split-belts-n{arguments.n}.man")
    program = build(arguments.n)
    program.save(output)
    width, height, footprint = program.footprint()
    print(f"wrote {output} ({width}x{height}, footprint {footprint})")


if __name__ == "__main__":
    main()
