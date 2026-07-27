from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

Point = tuple[int, int]

DIRECTIONS: dict[str, Point] = {
    ">": (1, 0),
    "<": (-1, 0),
    "^": (0, -1),
    "v": (0, 1),
    "V": (0, 1),
}


class LoadError(ValueError):
    pass


@dataclass
class Room:
    id: int
    kind: str
    left: int
    top: int
    right: int
    bottom: int
    man_start: Point | None = None
    incoming: list[int] = field(default_factory=list)
    outgoing: list[int] = field(default_factory=list)
    display_inputs: dict[str, int] = field(default_factory=dict)

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    @property
    def interior_width(self) -> int:
        return self.width - 2


@dataclass
class Pipe:
    id: int
    source_room: int
    destination_room: int
    cells: list[Point]
    source_attachment: Point
    destination_attachment: Point


@dataclass
class Program:
    grid: tuple[str, ...]
    width: int
    height: int
    rooms: list[Room]
    pipes: list[Pipe]
    literals: dict[tuple[Point, Point], int]
    input_room: int | None
    output_room: int | None
    display_room: int | None

    def cell(self, point: Point) -> str:
        x, y = point
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            raise IndexError(point)
        return self.grid[y][x]


@dataclass(frozen=True)
class _RoomCandidate:
    kind: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def cells(self) -> set[Point]:
        return {
            (x, y)
            for y in range(self.top, self.bottom + 1)
            for x in range(self.left, self.right + 1)
        }


def load_program(path: str | Path) -> Program:
    return parse_program(Path(path).read_text(encoding="ascii"))


def parse_program(source: str) -> Program:
    grid = _normalize_grid(source)
    height = len(grid)
    width = len(grid[0])
    candidates = _find_room_candidates(grid)
    rooms = _select_rooms(grid, candidates)
    room_cells, border_rooms = _index_rooms(rooms)
    pipes = _parse_pipes(grid, rooms, room_cells, border_rooms)
    _connect_and_validate(rooms, pipes)
    _validate_outside_cells(grid, room_cells, pipes)
    literals = _parse_literals(grid, rooms)

    input_rooms = [room.id for room in rooms if room.kind == "input"]
    output_rooms = [room.id for room in rooms if room.kind == "output"]
    display_rooms = [room.id for room in rooms if room.kind == "display"]
    if len(input_rooms) > 1:
        raise LoadError("program contains more than one input room")
    if len(output_rooms) > 1:
        raise LoadError("program contains more than one output room")
    if len(display_rooms) > 1:
        raise LoadError("program contains more than one display")

    return Program(
        grid=tuple(grid),
        width=width,
        height=height,
        rooms=rooms,
        pipes=pipes,
        literals=literals,
        input_room=input_rooms[0] if input_rooms else None,
        output_room=output_rooms[0] if output_rooms else None,
        display_room=display_rooms[0] if display_rooms else None,
    )


def _normalize_grid(source: str) -> list[str]:
    try:
        source.encode("ascii")
    except UnicodeEncodeError as error:
        raise LoadError("program must contain only ASCII characters") from error

    lines = source.splitlines()
    while lines and not lines[0].strip(" "):
        lines.pop(0)
    while lines and not lines[-1].strip(" "):
        lines.pop()
    if not lines:
        raise LoadError("program is empty")

    non_space_columns = [
        index
        for line in lines
        for index, character in enumerate(line)
        if character != " "
    ]
    if not non_space_columns:
        raise LoadError("program is empty")
    left = min(non_space_columns)
    right = max(non_space_columns)
    width = right - left + 1
    return [line.ljust(right + 1)[left : left + width] for line in lines]


def _find_room_candidates(grid: list[str]) -> list[_RoomCandidate]:
    height = len(grid)
    width = len(grid[0])
    candidates: list[_RoomCandidate] = []
    for top in range(height):
        for left in range(width):
            if grid[top][left] != "+":
                continue
            for right in range(left + 2, width):
                if grid[top][right] != "+":
                    continue
                horizontal = grid[top][left + 1 : right]
                if not horizontal or len(set(horizontal)) != 1:
                    continue
                horizontal_character = horizontal[0]
                if horizontal_character not in "-=":
                    continue
                side_character = "|" if horizontal_character == "-" else ":"
                kind = "ordinary" if horizontal_character == "-" else "display"
                for bottom in range(top + 2, height):
                    if grid[bottom][left] != "+" or grid[bottom][right] != "+":
                        continue
                    if any(grid[bottom][x] != horizontal_character for x in range(left + 1, right)):
                        continue
                    if any(
                        grid[y][left] != side_character or grid[y][right] != side_character
                        for y in range(top + 1, bottom)
                    ):
                        continue
                    candidates.append(_RoomCandidate(kind, left, top, right, bottom))
    return candidates


def _select_rooms(grid: list[str], candidates: list[_RoomCandidate]) -> list[Room]:
    by_corner: dict[Point, list[_RoomCandidate]] = {}
    for candidate in candidates:
        by_corner.setdefault((candidate.left, candidate.top), []).append(candidate)
    selected: list[_RoomCandidate] = []
    occupied: set[Point] = set()
    for corner in sorted(by_corner, key=lambda point: (point[1], point[0])):
        choices = by_corner[corner]
        if len(choices) != 1:
            raise LoadError(f"ambiguous room beginning at {corner}")
        candidate = choices[0]
        if candidate.cells & occupied:
            raise LoadError("rooms may not overlap or nest")
        selected.append(candidate)
        occupied.update(candidate.cells)

    rooms: list[Room] = []
    for room_id, candidate in enumerate(selected):
        interior = [
            (x, y)
            for y in range(candidate.top + 1, candidate.bottom)
            for x in range(candidate.left + 1, candidate.right)
        ]
        kind = candidate.kind
        man_positions = [point for point in interior if grid[point[1]][point[0]] == "@"]
        if kind == "ordinary" and candidate.right - candidate.left == 2 and candidate.bottom - candidate.top == 2:
            center = grid[candidate.top + 1][candidate.left + 1]
            if center == "I":
                kind = "input"
            elif center == "O":
                kind = "output"
        if kind == "ordinary" and len(man_positions) > 1:
            raise LoadError("an ordinary room may contain at most one little man")
        if kind != "ordinary" and man_positions:
            raise LoadError(f"{kind} rooms may not contain a little man")
        if kind == "display" and (candidate.right - candidate.left - 1 > 64 or candidate.bottom - candidate.top - 1 > 64):
            raise LoadError("display interior may not exceed 64x64")
        rooms.append(
            Room(
                id=room_id,
                kind=kind,
                left=candidate.left,
                top=candidate.top,
                right=candidate.right,
                bottom=candidate.bottom,
                man_start=man_positions[0] if man_positions else None,
            )
        )
    if not rooms:
        raise LoadError("program contains no rooms")
    return rooms


def _index_rooms(rooms: list[Room]) -> tuple[dict[Point, int], dict[Point, int]]:
    room_cells: dict[Point, int] = {}
    border_rooms: dict[Point, int] = {}
    for room in rooms:
        for y in range(room.top, room.bottom + 1):
            for x in range(room.left, room.right + 1):
                point = (x, y)
                room_cells[point] = room.id
                if x in (room.left, room.right) or y in (room.top, room.bottom):
                    border_rooms[point] = room.id
    return room_cells, border_rooms


def _parse_pipes(
    grid: list[str],
    rooms: list[Room],
    room_cells: dict[Point, int],
    border_rooms: dict[Point, int],
) -> list[Pipe]:
    height = len(grid)
    width = len(grid[0])
    starts: list[tuple[Point, int]] = []
    for y, line in enumerate(grid):
        for x, character in enumerate(line):
            if character not in DIRECTIONS or (x, y) in room_cells:
                continue
            direction = DIRECTIONS[character]
            backward = (x - direction[0], y - direction[1])
            if backward in border_rooms:
                starts.append(((x, y), border_rooms[backward]))

    pipes: list[Pipe] = []
    used_cells: set[Point] = set()
    for start, source_room in sorted(starts, key=lambda item: (item[0][1], item[0][0])):
        if start in used_cells:
            # A bend/end arrow may itself look like another source arrow beside a
            # room.  The reference loader assigns it to the first pipe traced in
            # reading order and does not start a second, overlapping pipe there.
            continue
        cells = [start]
        direction = DIRECTIONS[grid[start[1]][start[0]]]
        current = start
        seen = {start}
        destination_room: int | None = None
        destination_attachment: Point | None = None
        false_self_loop = False
        while destination_room is None:
            next_point = (current[0] + direction[0], current[1] + direction[1])
            if not (0 <= next_point[0] < width and 0 <= next_point[1] < height):
                raise LoadError(f"pipe beginning at {start} leaves the program grid")
            if next_point in seen:
                raise LoadError(f"pipe beginning at {start} loops")
            if next_point in room_cells:
                raise LoadError(f"pipe beginning at {start} enters a room without a terminal arrow")
            character = grid[next_point[1]][next_point[0]]
            if character in DIRECTIONS:
                next_direction = DIRECTIONS[character]
                if next_direction == (-direction[0], -direction[1]):
                    raise LoadError(f"pipe beginning at {start} has a backward arrow")
                cells.append(next_point)
                seen.add(next_point)
                forward = (next_point[0] + next_direction[0], next_point[1] + next_direction[1])
                candidate_room = border_rooms.get(forward)
                if candidate_room is not None:
                    if candidate_room == source_room:
                        # An in-path arrow beside a room wall may look like a
                        # second pipe start. The oracle discards that candidate
                        # when it leads back to the same room.
                        false_self_loop = True
                        break
                    destination_room = candidate_room
                    destination_attachment = forward
                    break
                direction = next_direction
                current = next_point
                continue
            expected = "-" if direction[0] else "|"
            if character != expected:
                raise LoadError(f"invalid pipe cell {character!r} at {next_point}")
            cells.append(next_point)
            seen.add(next_point)
            current = next_point

        if false_self_loop:
            continue
        if len(cells) < 2:
            raise LoadError("pipes must contain at least two cells")
        overlap = used_cells.intersection(cells)
        if overlap:
            raise LoadError(f"pipes overlap at {min(overlap)}")
        used_cells.update(cells)
        pipes.append(
            Pipe(
                id=len(pipes),
                source_room=source_room,
                destination_room=destination_room,
                cells=cells,
                source_attachment=(start[0] - DIRECTIONS[grid[start[1]][start[0]]][0], start[1] - DIRECTIONS[grid[start[1]][start[0]]][1]),
                destination_attachment=destination_attachment,
            )
        )
    return pipes


def _connect_and_validate(rooms: list[Room], pipes: list[Pipe]) -> None:
    for pipe in pipes:
        rooms[pipe.source_room].outgoing.append(pipe.id)
        rooms[pipe.destination_room].incoming.append(pipe.id)

    for room in rooms:
        if room.kind == "input":
            if room.incoming or len(room.outgoing) > 1:
                raise LoadError("input room must have at most one outgoing pipe and no incoming pipes")
        elif room.kind == "output":
            if room.outgoing or len(room.incoming) > 1:
                raise LoadError("output room must have at most one incoming pipe and no outgoing pipes")
        elif room.kind == "display":
            if room.outgoing:
                raise LoadError("display pipes must flow into the display")
            for pipe_id in room.incoming:
                attachment = pipes[pipe_id].destination_attachment
                x, y = attachment
                if x in (room.left, room.right) and y in (room.top, room.bottom):
                    raise LoadError("display pipes may not attach to corners")
                if y == room.top:
                    function = "addr"
                elif x == room.left:
                    function = "data"
                elif y == room.bottom:
                    function = "swap"
                else:
                    raise LoadError("display pipes may not attach to the right side")
                if function in room.display_inputs:
                    raise LoadError(f"display has multiple {function} pipes")
                room.display_inputs[function] = pipe_id


def _validate_outside_cells(grid: list[str], room_cells: dict[Point, int], pipes: list[Pipe]) -> None:
    pipe_cells = {point for pipe in pipes for point in pipe.cells}
    for y, line in enumerate(grid):
        for x, character in enumerate(line):
            point = (x, y)
            if point in room_cells or point in pipe_cells or character == " ":
                continue
            raise LoadError(f"unrecognized character outside a room or pipe at {point}")


def _parse_literals(grid: list[str], rooms: list[Room]) -> dict[tuple[Point, Point], int]:
    literals: dict[tuple[Point, Point], int] = {}
    for room in rooms:
        if room.kind != "ordinary":
            continue
        for y in range(room.top + 1, room.bottom):
            ticks = [x for x in range(room.left + 1, room.right) if grid[y][x] == "`"]
            for left, right in zip(ticks[0::2], ticks[1::2]):
                content = grid[y][left + 1 : right]
                _add_literal_pair(literals, content, (left, y), (right, y), (1, 0))
        for x in range(room.left + 1, room.right):
            ticks = [y for y in range(room.top + 1, room.bottom) if grid[y][x] == "`"]
            for top, bottom in zip(ticks[0::2], ticks[1::2]):
                content = "".join(grid[y][x] for y in range(top + 1, bottom))
                _add_literal_pair(literals, content, (x, top), (x, bottom), (0, 1))
    return literals


def _add_literal_pair(
    literals: dict[tuple[Point, Point], int],
    content: str,
    opening: Point,
    closing: Point,
    direction: Point,
) -> None:
    if any(character not in " 0123456789" for character in content):
        raise LoadError(f"invalid character inside numeric literal from {opening} to {closing}")
    digits = content.replace(" ", "")
    if not digits:
        return
    forward = int(digits)
    backward = int(digits[::-1])
    maximum = (1 << 63) - 1
    if forward > maximum or backward > maximum:
        raise LoadError(f"numeric literal from {opening} to {closing} exceeds signed 64-bit range")
    literals[(closing, direction)] = forward
    reverse_direction = (-direction[0], -direction[1])
    literals[(opening, reverse_direction)] = backward
