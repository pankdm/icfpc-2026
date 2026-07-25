from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

from .parser import DIRECTIONS, Pipe, Point, Program

MIN_INT64 = -(1 << 63)
MAX_INT64 = (1 << 63) - 1
MASK64 = (1 << 64) - 1
MAX_LIVE_MEN = 65_536


@dataclass
class LittleMan:
    room_id: int
    position: Point
    direction: Point = (1, 0)
    main: int = 0
    off: int = 0
    backpack: int = 0
    stopped: bool = False
    born_this_tick: bool = False


@dataclass
class PipeState:
    pipe: Pipe
    values: list[int | None]


@dataclass
class DisplayState:
    room_id: int
    width: int
    height: int
    current: list[int]
    next_buffer: list[int]
    cursor: int = 0
    frames: list[tuple[int, ...]] = field(default_factory=list)


@dataclass
class ExecutionResult:
    status: str
    ticks: int
    output: list[int]
    error: str | None
    expected_output: list[int] | None
    display_frames: list[tuple[int, ...]]

    @property
    def passed(self) -> bool:
        return self.status == "passed"


class RuntimeFailure(RuntimeError):
    pass


class LittlemanMachine:
    def __init__(
        self,
        program: Program,
        input_rounds: list[list[int]] | None = None,
        expected_rounds: list[list[int]] | None = None,
        tick_limit: int = 5_000_000,
    ) -> None:
        if tick_limit < 0:
            raise ValueError("tick limit must be non-negative")
        self.program = program
        self.tick_limit = tick_limit
        self.ticks = 0
        self.error: str | None = None
        self.output: list[int] = []
        self.men = [
            LittleMan(room.id, room.man_start)
            for room in program.rooms
            if room.man_start is not None
        ]
        self.pipes = [PipeState(pipe, [None] * len(pipe.cells)) for pipe in program.pipes]
        self.display = self._create_display()
        self.input_rounds = input_rounds or [[]]
        self.expected_rounds = expected_rounds
        self.expected_output = (
            [value for round_values in expected_rounds for value in round_values]
            if expected_rounds is not None
            else None
        )
        self.available_input: deque[int] = deque()
        self.unlocked_input_round = -1
        self.completed_expected_round = -1
        if expected_rounds is not None and len(self.input_rounds) != len(expected_rounds):
            raise ValueError("input and expected output must contain the same number of rounds")
        if expected_rounds is None:
            self.available_input.extend(value for values in self.input_rounds for value in values)
            self.unlocked_input_round = len(self.input_rounds) - 1
        else:
            self._unlock_input_round(0)
            self._advance_completed_rounds()

    @property
    def footprint(self) -> int:
        return max(self.program.width, self.program.height) ** 2

    def run(self) -> ExecutionResult:
        if self._expected_complete():
            return self._result("passed")
        while self.ticks < self.tick_limit:
            if self._all_men_stopped() and not self._output_in_flight():
                status = "halted" if self.expected_output is None else "failed"
                return self._result(status, "program ended before producing the expected output" if status == "failed" else None)
            self.ticks += 1
            try:
                self._tick()
            except RuntimeFailure as error:
                self.error = str(error)
                return self._result("failed" if self.expected_output is not None else "error", self.error)
            if self._expected_complete():
                return self._result("passed")
        return self._result(
            "failed" if self.expected_output is not None else "step-cap",
            f"step cap of {self.tick_limit} ticks reached",
        )

    def _tick(self) -> None:
        for man in self.men:
            man.born_this_tick = False
        self._shift_pipes()
        self._process_output()
        if self._expected_complete():
            return
        self._process_input()
        blocked = self._execute_men()
        self._execute_display()
        self._move_men(blocked)

    def _shift_pipes(self) -> None:
        for pipe_state in self.pipes:
            for index in range(len(pipe_state.values) - 2, -1, -1):
                if pipe_state.values[index] is not None and pipe_state.values[index + 1] is None:
                    pipe_state.values[index + 1] = pipe_state.values[index]
                    pipe_state.values[index] = None

    def _process_output(self) -> None:
        if self.program.output_room is None:
            return
        room = self.program.rooms[self.program.output_room]
        if not room.incoming:
            return
        pipe_state = self.pipes[room.incoming[0]]
        value = pipe_state.values[-1]
        if value is None:
            return
        pipe_state.values[-1] = None
        self.output.append(value)
        if self.expected_output is not None:
            output_index = len(self.output) - 1
            if output_index >= len(self.expected_output) or value != self.expected_output[output_index]:
                expected = self.expected_output[output_index] if output_index < len(self.expected_output) else None
                raise RuntimeFailure(
                    f"incorrect output at index {output_index}: expected {expected!r}, received {value}"
                )
            self._advance_completed_rounds()

    def _process_input(self) -> None:
        if self.program.input_room is None or not self.available_input:
            return
        room = self.program.rooms[self.program.input_room]
        if not room.outgoing:
            return
        pipe_state = self.pipes[room.outgoing[0]]
        if pipe_state.values[0] is None:
            pipe_state.values[0] = self.available_input.popleft()

    def _execute_men(self) -> set[int]:
        blocked: set[int] = set()
        execution_count = len(self.men)
        for man_index in range(execution_count):
            man = self.men[man_index]
            if man.stopped:
                continue
            character = self.program.cell(man.position)
            if character == "@" or character == "." or character == " ":
                continue
            if character.isdigit():
                man.main = int(character)
                continue
            if character == "`":
                literal = self.program.literals.get((man.position, man.direction))
                if literal is not None:
                    man.main = literal
                continue
            if character == "M":
                man.off = man.main
            elif character == "W":
                man.main, man.off = man.off, man.main
            elif character == "+":
                man.main = wrap_int64(man.main + man.off)
            elif character == "-":
                man.main = wrap_int64(man.main - man.off)
            elif character == "*":
                man.main = wrap_int64(man.main * man.off)
            elif character == "%":
                man.main = 0 if man.off == 0 else wrap_int64(man.main % man.off)
            elif character == "/":
                dividend = man.main
                divisor = man.off
                if divisor == 0:
                    man.main = 0
                    man.off = dividend
                else:
                    man.main = wrap_int64(dividend // divisor)
                    man.off = wrap_int64(dividend % divisor)
            elif character == "N":
                man.main = wrap_int64(-man.main)
            elif character == "&":
                man.main = wrap_int64((man.main & MASK64) & (man.off & MASK64))
            elif character == "|":
                man.main = wrap_int64((man.main & MASK64) | (man.off & MASK64))
            elif character == "~":
                man.main = wrap_int64((man.main & MASK64) ^ (man.off & MASK64))
            elif character == "{":
                man.main = 0 if man.off < 0 or man.off > 63 else wrap_int64(man.main << man.off)
            elif character == "}":
                if man.off < 0:
                    man.main = 0
                elif man.off > 63:
                    man.main = -1 if man.main < 0 else 0
                else:
                    man.main = wrap_int64(man.main >> man.off)
            elif character in DIRECTIONS:
                man.direction = DIRECTIONS[character]
            elif character == "X":
                if man.main > 0:
                    man.direction = turn_clockwise(man.direction)
                elif man.main < 0:
                    man.direction = turn_counterclockwise(man.direction)
            elif character == "H":
                man.stopped = True
            elif character == "b":
                man.backpack = man.main
            elif character == "m":
                man.backpack = wrap_int64(man.backpack - 1)
            elif character == "d":
                if man.backpack > 0:
                    man.direction = turn_clockwise(man.direction)
            elif character == "a":
                if man.backpack > 0:
                    man.direction = turn_counterclockwise(man.direction)
            elif character == "]":
                man.backpack = wrap_int64(man.backpack >> 1)
            elif character == "x":
                man.direction = turn_clockwise(man.direction) if man.backpack & 1 else turn_counterclockwise(man.direction)
            elif character == "Y":
                self._execute_split(man_index)
            elif character == "q":
                incoming = self.program.rooms[man.room_id].incoming
                if not incoming:
                    raise RuntimeFailure("no-pipe: q executed in a room with no incoming pipe")
                pipe_id = self._nearest_pipe(man, incoming, incoming=True)
                man.backpack = sum(value is not None for value in self.pipes[pipe_id].values)
            elif character in "sSrRU":
                if not self._execute_pipe_instruction(man, character):
                    blocked.add(man_index)
            else:
                raise RuntimeFailure(f"bad-op: invalid instruction {character!r} at {man.position}")
        return blocked

    def _execute_split(self, man_index: int) -> None:
        splitter = self.men[man_index]
        live_count = sum(not man.stopped for man in self.men)
        if live_count >= MAX_LIVE_MEN:
            raise RuntimeFailure(f"man-limit: split would exceed {MAX_LIVE_MEN} live little men")

        right_direction = turn_clockwise(splitter.direction)
        left_direction = turn_counterclockwise(splitter.direction)
        right = LittleMan(
            room_id=splitter.room_id,
            position=add_points(splitter.position, right_direction),
            direction=right_direction,
            main=splitter.main,
            off=splitter.off,
            backpack=splitter.backpack,
            born_this_tick=True,
        )
        left = LittleMan(
            room_id=splitter.room_id,
            position=add_points(splitter.position, left_direction),
            direction=left_direction,
            main=splitter.main,
            off=splitter.off,
            backpack=splitter.backpack,
            born_this_tick=True,
        )

        self.men[man_index] = right
        self.men.append(left)
        birth_indices = (man_index, len(self.men) - 1)

        room = self.program.rooms[splitter.room_id]
        for birth_index in birth_indices:
            position = self.men[birth_index].position
            if position[0] in (room.left, room.right) or position[1] in (room.top, room.bottom):
                raise RuntimeFailure(f"wall: split birthed a little man in wall cell {position}")

        birth_positions = {self.men[birth_index].position for birth_index in birth_indices}
        for position in birth_positions:
            occupants = [
                index
                for index, man in enumerate(self.men)
                if not man.stopped and man.position == position
            ]
            if len(occupants) > 1:
                for occupant in occupants:
                    self.men[occupant].stopped = True

    def _execute_pipe_instruction(self, man: LittleMan, character: str) -> bool:
        room = self.program.rooms[man.room_id]
        if character in "sS":
            if not room.outgoing:
                raise RuntimeFailure(f"no-pipe: {character} executed in a room with no outgoing pipe")
            pipe_ids = room.outgoing if character == "S" else [self._nearest_pipe(man, room.outgoing, incoming=False)]
            if any(self.pipes[pipe_id].values[0] is not None for pipe_id in pipe_ids):
                return False
            for pipe_id in pipe_ids:
                self.pipes[pipe_id].values[0] = man.main
            return True

        if not room.incoming:
            raise RuntimeFailure(f"no-pipe: {character} executed in a room with no incoming pipe")
        if character == "r":
            pipe_ids = [self._nearest_pipe(man, room.incoming, incoming=True)]
        else:
            pipe_ids = sorted(
                room.incoming,
                key=lambda pipe_id: reading_order(self.program.pipes[pipe_id].cells[-1]),
            )
        ready_pipe = next((pipe_id for pipe_id in pipe_ids if self.pipes[pipe_id].values[-1] is not None), None)
        if ready_pipe is None:
            return False
        man.main = self.pipes[ready_pipe].values[-1]
        self.pipes[ready_pipe].values[-1] = None
        if character == "U":
            attachment = self.program.pipes[ready_pipe].destination_attachment
            if attachment[0] == room.left:
                man.direction = (1, 0)
            elif attachment[0] == room.right:
                man.direction = (-1, 0)
            elif attachment[1] == room.top:
                man.direction = (0, 1)
            else:
                man.direction = (0, -1)
        return True

    def _nearest_pipe(self, man: LittleMan, pipe_ids: Iterable[int], incoming: bool) -> int:
        def key(pipe_id: int) -> tuple[int, int, int]:
            pipe = self.program.pipes[pipe_id]
            segment = pipe.cells[-1] if incoming else pipe.cells[0]
            distance = abs(segment[0] - man.position[0]) + abs(segment[1] - man.position[1])
            return distance, segment[1], segment[0]

        return min(pipe_ids, key=key)

    def _execute_display(self) -> None:
        if self.display is None:
            return
        room = self.program.rooms[self.display.room_id]
        for function in ("addr", "data", "swap"):
            pipe_id = room.display_inputs.get(function)
            if pipe_id is None:
                continue
            pipe_state = self.pipes[pipe_id]
            value = pipe_state.values[-1]
            if value is None:
                continue
            pipe_state.values[-1] = None
            if function == "addr":
                if value < 0 or value >= self.display.width * self.display.height:
                    raise RuntimeFailure(f"display address {value} is out of bounds")
                self.display.cursor = value
            elif function == "data":
                if value < 0 or value > 15:
                    raise RuntimeFailure(f"display color {value} is outside 0..15")
                self.display.next_buffer[self.display.cursor] = value
                self.display.cursor = (self.display.cursor + 1) % len(self.display.next_buffer)
            else:
                if value not in (0, 1):
                    raise RuntimeFailure(f"display swap value {value} is not 0 or 1")
                self.display.current = self.display.next_buffer.copy()
                self.display.frames.append(tuple(self.display.current))
                if value == 0:
                    self.display.next_buffer = [0] * len(self.display.next_buffer)
                    self.display.cursor = 0

    def _move_men(self, blocked: set[int]) -> None:
        moving: dict[int, Point] = {}
        for man_index, man in enumerate(self.men):
            if man.stopped or man.born_this_tick or man_index in blocked:
                continue
            target = (man.position[0] + man.direction[0], man.position[1] + man.direction[1])
            room = self.program.rooms[man.room_id]
            if target[0] in (room.left, room.right) or target[1] in (room.top, room.bottom):
                raise RuntimeFailure(f"wall: little man at {man.position} entered wall cell {target}")
            moving[man_index] = target

        colliding: set[int] = set()
        targets: dict[Point, list[int]] = {}
        for man_index, target in moving.items():
            targets.setdefault(target, []).append(man_index)
        for indices in targets.values():
            if len(indices) > 1:
                colliding.update(indices)

        stationary: dict[Point, list[int]] = {}
        for man_index, man in enumerate(self.men):
            if not man.stopped and man_index not in moving:
                stationary.setdefault(man.position, []).append(man_index)
        for man_index, target in moving.items():
            occupants = stationary.get(target, [])
            if occupants:
                colliding.add(man_index)
                colliding.update(occupants)

        origins = {man.position: man_index for man_index, man in enumerate(self.men) if man_index in moving}
        for man_index, target in moving.items():
            other_index = origins.get(target)
            if other_index is not None and moving.get(other_index) == self.men[man_index].position:
                colliding.add(man_index)
                colliding.add(other_index)

        for man_index, target in moving.items():
            if man_index not in colliding:
                self.men[man_index].position = target
        for man_index in colliding:
            self.men[man_index].stopped = True

    def _advance_completed_rounds(self) -> None:
        if self.expected_rounds is None:
            return
        while self.completed_expected_round + 1 < len(self.expected_rounds):
            next_round = self.completed_expected_round + 1
            required_count = sum(len(values) for values in self.expected_rounds[: next_round + 1])
            if len(self.output) < required_count:
                break
            self.completed_expected_round = next_round
            self._unlock_input_round(next_round + 1)

    def _unlock_input_round(self, round_index: int) -> None:
        if round_index >= len(self.input_rounds) or round_index <= self.unlocked_input_round:
            return
        self.available_input.extend(self.input_rounds[round_index])
        self.unlocked_input_round = round_index

    def _expected_complete(self) -> bool:
        return self.expected_rounds is not None and self.completed_expected_round == len(self.expected_rounds) - 1

    def _all_men_stopped(self) -> bool:
        return all(man.stopped for man in self.men)

    def _output_in_flight(self) -> bool:
        if self.program.output_room is None:
            return False
        room = self.program.rooms[self.program.output_room]
        return bool(room.incoming and any(value is not None for value in self.pipes[room.incoming[0]].values))

    def _create_display(self) -> DisplayState | None:
        if self.program.display_room is None:
            return None
        room = self.program.rooms[self.program.display_room]
        size = (room.width - 2) * (room.height - 2)
        return DisplayState(
            room_id=room.id,
            width=room.width - 2,
            height=room.height - 2,
            current=[0] * size,
            next_buffer=[0] * size,
        )

    def _result(self, status: str, error: str | None = None) -> ExecutionResult:
        return ExecutionResult(
            status=status,
            ticks=self.ticks,
            output=self.output.copy(),
            error=error,
            expected_output=self.expected_output.copy() if self.expected_output is not None else None,
            display_frames=self.display.frames.copy() if self.display is not None else [],
        )


def wrap_int64(value: int) -> int:
    value &= MASK64
    return value if value <= MAX_INT64 else value - (1 << 64)


def turn_clockwise(direction: Point) -> Point:
    return -direction[1], direction[0]


def turn_counterclockwise(direction: Point) -> Point:
    return direction[1], -direction[0]


def reading_order(point: Point) -> tuple[int, int]:
    return point[1], point[0]


def add_points(left: Point, right: Point) -> Point:
    return left[0] + right[0], left[1] + right[1]
