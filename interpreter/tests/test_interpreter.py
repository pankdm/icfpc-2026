from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interpreter.machine import LittleMan, LittlemanMachine, RuntimeFailure
from interpreter.parser import LoadError, parse_program


CONSTANT_OUTPUT = """\
+----+  +-+
|@3s<|>>|O|
+----+  +-+
"""

ROUND_ECHO = """\
+-+  +-----+  +-+
|I|>>|>@rsv|>>|O|
+-+  |^    |  +-+
     |^<<<<|
     +-----+
"""

LITERAL_OUTPUT = """\
+-------+  +-+
|@`12`s<|>>|O|
+-------+  +-+
"""

SPLIT_ROOM = """\
+-----+
|  H  |
| @Y  |
|  H  |
+-----+
"""

SPLIT_WALL = """\
+---+
|@Y |
+---+
"""

MULTI_SPLIT_ROOM = """\
+-------+
|  Y    |
| Y     |
|@      |
+-------+
"""


class ParserTests(unittest.TestCase):
    def test_parses_rooms_and_pipe(self) -> None:
        program = parse_program(CONSTANT_OUTPUT)
        self.assertEqual((program.width, program.height), (11, 3))
        self.assertEqual([room.kind for room in program.rooms], ["ordinary", "output"])
        self.assertEqual(len(program.pipes), 1)
        self.assertEqual(program.pipes[0].cells, [(6, 1), (7, 1)])

    def test_rejects_single_cell_pipe(self) -> None:
        source = """\
+----+ +-+
|@3s<|>|O|
+----+ +-+
"""
        with self.assertRaises(LoadError):
            parse_program(source)

    def test_parses_numeric_literal(self) -> None:
        program = parse_program(LITERAL_OUTPUT)
        result = LittlemanMachine(program, expected_rounds=[[12]], tick_limit=20).run()
        self.assertTrue(result.passed)
        self.assertEqual(result.output, [12])


class RuntimeTests(unittest.TestCase):
    def test_outputs_constant_and_scores_ticks(self) -> None:
        program = parse_program(CONSTANT_OUTPUT)
        machine = LittlemanMachine(program, expected_rounds=[[3]], tick_limit=20)
        result = machine.run()
        self.assertTrue(result.passed)
        self.assertEqual(result.ticks, 4)
        self.assertEqual(result.output, [3])
        self.assertEqual(machine.footprint, 121)

    def test_fails_on_wrong_output(self) -> None:
        program = parse_program(CONSTANT_OUTPUT)
        result = LittlemanMachine(program, expected_rounds=[[4]], tick_limit=20).run()
        self.assertEqual(result.status, "failed")
        self.assertIn("incorrect output", result.error or "")

    def test_rounds_share_one_run_and_gate_input(self) -> None:
        program = parse_program(ROUND_ECHO)
        result = LittlemanMachine(
            program,
            input_rounds=[[11], [22]],
            expected_rounds=[[11], [22]],
            tick_limit=100,
        ).run()
        self.assertTrue(result.passed)
        self.assertEqual(result.output, [11, 22])
        self.assertEqual(result.ticks, 16)

    def test_empty_expected_output_passes_at_tick_zero(self) -> None:
        program = parse_program(CONSTANT_OUTPUT)
        result = LittlemanMachine(program, expected_rounds=[[]], tick_limit=20).run()
        self.assertTrue(result.passed)
        self.assertEqual(result.ticks, 0)

    def test_split_birth_order_registers_and_delayed_execution(self) -> None:
        machine = LittlemanMachine(parse_program(SPLIT_ROOM), tick_limit=20)
        machine.men[0].position = (3, 2)
        machine.men[0].main = 11
        machine.men[0].off = 22
        machine.men[0].backpack = 33

        machine._tick()

        self.assertEqual(len(machine.men), 2)
        right, left = machine.men
        self.assertEqual((right.position, right.direction), ((3, 3), (0, 1)))
        self.assertEqual((left.position, left.direction), ((3, 1), (0, -1)))
        self.assertEqual((right.main, right.off, right.backpack), (11, 22, 33))
        self.assertEqual((left.main, left.off, left.backpack), (11, 22, 33))
        self.assertFalse(right.stopped)
        self.assertFalse(left.stopped)

        machine._tick()

        self.assertTrue(right.stopped)
        self.assertTrue(left.stopped)

    def test_split_birth_in_wall_is_an_error(self) -> None:
        result = LittlemanMachine(parse_program(SPLIT_WALL), tick_limit=20).run()
        self.assertEqual(result.status, "error")
        self.assertEqual(result.ticks, 2)
        self.assertIn("split birthed", result.error or "")

    def test_split_birth_kills_existing_occupant(self) -> None:
        machine = LittlemanMachine(parse_program(SPLIT_ROOM), tick_limit=20)
        machine.men = [
            LittleMan(0, (3, 2)),
            LittleMan(0, (3, 3)),
        ]

        machine._execute_men()

        self.assertTrue(machine.men[0].stopped)
        self.assertTrue(machine.men[1].stopped)
        self.assertFalse(machine.men[2].stopped)

    def test_two_splits_spawning_on_same_cell_kill_both_copies(self) -> None:
        machine = LittlemanMachine(parse_program(MULTI_SPLIT_ROOM), tick_limit=20)
        machine.men = [
            LittleMan(0, (2, 2), direction=(1, 0)),
            LittleMan(0, (3, 1), direction=(0, 1)),
        ]

        machine._execute_men()

        self.assertFalse(machine.men[0].stopped)
        self.assertTrue(machine.men[1].stopped)
        self.assertTrue(machine.men[2].stopped)
        self.assertFalse(machine.men[3].stopped)

    def test_split_enforces_live_man_limit(self) -> None:
        machine = LittlemanMachine(parse_program(SPLIT_ROOM), tick_limit=20)
        machine.men[0].position = (3, 2)
        with patch("interpreter.machine.MAX_LIVE_MEN", 1):
            with self.assertRaisesRegex(RuntimeFailure, "man-limit"):
                machine._tick()

    def test_movement_collision_kills_both_arrivals(self) -> None:
        machine = LittlemanMachine(parse_program(SPLIT_ROOM), tick_limit=20)
        machine.men = [
            LittleMan(0, (2, 2), direction=(1, 0)),
            LittleMan(0, (4, 2), direction=(-1, 0)),
        ]

        machine._move_men(set())

        self.assertTrue(all(man.stopped for man in machine.men))

    def test_movement_collision_kills_swapping_men(self) -> None:
        machine = LittlemanMachine(parse_program(SPLIT_ROOM), tick_limit=20)
        machine.men = [
            LittleMan(0, (2, 2), direction=(1, 0)),
            LittleMan(0, (3, 2), direction=(-1, 0)),
        ]

        machine._move_men(set())

        self.assertTrue(all(man.stopped for man in machine.men))

    def test_movement_collision_kills_blocked_occupant(self) -> None:
        machine = LittlemanMachine(parse_program(SPLIT_ROOM), tick_limit=20)
        machine.men = [
            LittleMan(0, (2, 2), direction=(1, 0)),
            LittleMan(0, (3, 2), direction=(1, 0)),
        ]

        machine._move_men({1})

        self.assertTrue(all(man.stopped for man in machine.men))


class CliTests(unittest.TestCase):
    def test_check_writes_actual_output_and_json_score(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            program_path = directory / "constant.man"
            input_path = directory / "input.txt"
            expected_path = directory / "expected.txt"
            actual_path = directory / "actual.txt"
            program_path.write_text(CONSTANT_OUTPUT, encoding="ascii")
            input_path.write_text("", encoding="utf-8")
            expected_path.write_text("3\n", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interpreter",
                    "check",
                    str(program_path),
                    str(input_path),
                    str(expected_path),
                    "--actual-output",
                    str(actual_path),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertTrue(report["passed"])
            self.assertEqual(report["footprint"], 121)
            self.assertEqual(report["footprint_tick"], 484)
            self.assertEqual(actual_path.read_text(encoding="utf-8"), "3\n")


if __name__ == "__main__":
    unittest.main()
