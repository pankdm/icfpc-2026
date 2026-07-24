"""Remove globally redundant rows and columns from a Littleman program."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from interpreter.parser import LoadError, parse_program
from interpreter.machine import LittlemanMachine


Validator = Callable[[str], bool]


def compact_text(
    text: str,
    validator: Validator | None = None,
    *,
    remove_rows: bool = True,
    remove_columns: bool = True,
) -> str:
    """Greedily remove straight-only rows/columns while preserving parseability."""
    rows = _rows(text)
    validate = validator or _parses

    changed = True
    while changed:
        changed = False
        if remove_rows:
            for row_index in range(len(rows)):
                if not _removable_row(rows, row_index):
                    continue
                candidate = rows[:row_index] + rows[row_index + 1 :]
                if validate(_render(candidate)):
                    rows = candidate
                    changed = True
                    break
        if changed:
            continue

        if remove_columns:
            for column_index in range(len(rows[0])):
                if not _removable_column(rows, column_index):
                    continue
                candidate = [row[:column_index] + row[column_index + 1 :] for row in rows]
                if validate(_render(candidate)):
                    rows = candidate
                    changed = True
                    break

    return _render(rows)


def dimensions(text: str) -> tuple[int, int]:
    rows = _rows(text)
    return len(rows[0]), len(rows)


def _rows(text: str) -> list[str]:
    lines = text.rstrip("\n").splitlines()
    if not lines:
        return [""]
    width = max(map(len, lines))
    return [line.ljust(width) for line in lines]


def _render(rows: list[str]) -> str:
    rendered = [row.rstrip() for row in rows]
    while rendered and not rendered[-1]:
        rendered.pop()
    return "\n".join(rendered)


def _removable_row(rows: list[str], row_index: int) -> bool:
    characters = {character for character in rows[row_index] if character != " "}
    return not characters or characters == {"|"}


def _removable_column(rows: list[str], column_index: int) -> bool:
    characters = {row[column_index] for row in rows if row[column_index] != " "}
    return not characters or characters == {"-"}


def _parses(text: str) -> bool:
    try:
        parse_program(text)
    except (LoadError, ValueError):
        return False
    return True


def public_test_validator(path: Path, tick_limit: int) -> Validator:
    specification = json.loads(path.read_text(encoding="utf-8"))
    tests = specification["publicTestData"]

    def validate(text: str) -> bool:
        try:
            program = parse_program(text)
            for test in tests:
                result = LittlemanMachine(
                    program,
                    input_rounds=[[int(value) for value in test["in"]]],
                    expected_rounds=[[int(value) for value in test["out"]]],
                    tick_limit=tick_limit,
                ).run()
                if not result.passed:
                    return False
        except (LoadError, ValueError):
            return False
        return True

    return validate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--tests", type=Path, help="accept each deletion only if all public tests pass")
    parser.add_argument("--tick-limit", type=int, default=1_000_000)
    arguments = parser.parse_args()
    if arguments.in_place and arguments.output is not None:
        parser.error("OUTPUT and --in-place are mutually exclusive")
    if not arguments.in_place and arguments.output is None:
        parser.error("provide OUTPUT or use --in-place")

    source = arguments.input.read_text(encoding="ascii")
    validator = public_test_validator(arguments.tests, arguments.tick_limit) if arguments.tests else None
    compacted = compact_text(source, validator=validator)
    output = arguments.input if arguments.in_place else arguments.output
    assert output is not None
    output.write_text(compacted + "\n", encoding="ascii")
    old_width, old_height = dimensions(source)
    new_width, new_height = dimensions(compacted)
    print(f"{arguments.input}: {old_width}x{old_height} -> {new_width}x{new_height}; wrote {output}")


if __name__ == "__main__":
    main()
