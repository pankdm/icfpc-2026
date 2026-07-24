from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .machine import ExecutionResult, LittlemanMachine
from .parser import LoadError, load_program


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m interpreter",
        description="Run and check ICFPC 2026 Littleman programs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="execute a program and write its numeric output")
    run_parser.add_argument("program", type=Path)
    run_parser.add_argument("input", type=Path)
    run_parser.add_argument("output", type=Path)
    run_parser.add_argument("--tick-limit", type=nonnegative_int, default=5_000_000)
    run_parser.add_argument("--json", action="store_true", help="print the execution report as JSON")

    check_parser = subparsers.add_parser("check", help="check output and calculate solution scores")
    check_parser.add_argument("program", type=Path)
    check_parser.add_argument("input", type=Path)
    check_parser.add_argument("expected", type=Path)
    check_parser.add_argument("--actual-output", type=Path)
    check_parser.add_argument("--tick-limit", type=nonnegative_int, default=5_000_000)
    check_parser.add_argument("--json", action="store_true", help="print the check report as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        program = load_program(arguments.program)
        input_rounds = read_rounds(arguments.input)
        if arguments.command == "run":
            machine = LittlemanMachine(program, input_rounds=input_rounds, tick_limit=arguments.tick_limit)
            result = machine.run()
            write_output(arguments.output, result.output)
            report = execution_report(machine, result)
            print_report(report, arguments.json)
            return 0 if result.status == "halted" else 1

        expected_rounds = read_rounds(arguments.expected)
        machine = LittlemanMachine(
            program,
            input_rounds=input_rounds,
            expected_rounds=expected_rounds,
            tick_limit=arguments.tick_limit,
        )
        result = machine.run()
        if arguments.actual_output is not None:
            write_output(arguments.actual_output, result.output)
        report = check_report(machine, result)
        print_report(report, arguments.json)
        return 0 if result.passed else 1
    except (LoadError, ValueError, OSError) as error:
        report = {"status": "load-error", "error": str(error)}
        print_report(report, getattr(arguments, "json", False), stream=sys.stderr)
        return 2


def read_rounds(path: Path) -> list[list[int]]:
    text = path.read_text(encoding="utf-8")
    pieces = text.replace("/", " / ").split()
    rounds: list[list[int]] = [[]]
    for piece in pieces:
        if piece == "/":
            rounds.append([])
            continue
        try:
            value = int(piece, 10)
        except ValueError as error:
            raise ValueError(f"{path}: invalid integer token {piece!r}") from error
        if value < -(1 << 63) or value > (1 << 63) - 1:
            raise ValueError(f"{path}: integer {value} is outside signed 64-bit range")
        rounds[-1].append(value)
    return rounds


def write_output(path: Path, values: list[int]) -> None:
    text = " ".join(str(value) for value in values)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def execution_report(machine: LittlemanMachine, result: ExecutionResult) -> dict[str, object]:
    return {
        "status": result.status,
        "ticks": result.ticks,
        "output_values": len(result.output),
        "error": result.error,
        "width": machine.program.width,
        "height": machine.program.height,
        "footprint": machine.footprint,
        "display_frames": len(result.display_frames),
    }


def check_report(machine: LittlemanMachine, result: ExecutionResult) -> dict[str, object]:
    report = execution_report(machine, result)
    report.update(
        {
            "passed": result.passed,
            "expected_values": len(result.expected_output or []),
            "footprint_tick": machine.footprint * result.ticks if result.passed else None,
        }
    )
    return report


def print_report(report: dict[str, object], as_json: bool, stream=sys.stdout) -> None:
    if as_json:
        print(json.dumps(report, sort_keys=True), file=stream)
        return
    labels = {
        "status": "status",
        "passed": "passed",
        "ticks": "ticks",
        "width": "width",
        "height": "height",
        "footprint": "footprint score",
        "footprint_tick": "footprint-tick score",
        "output_values": "output values",
        "expected_values": "expected values",
        "display_frames": "display frames",
        "error": "error",
    }
    for key in labels:
        if key in report and report[key] is not None:
            print(f"{labels[key]}: {format_value(report[key])}", file=stream)


def format_value(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed
