# Littleman Interpreter

Dependency-free Python 3 interpreter for ICFPC 2026 `.man` programs.

## Run a program

```sh
python3 -m interpreter run PROGRAM.man INPUT.txt OUTPUT.txt
```

The input file contains whitespace-separated signed 64-bit decimal integers. The output file is overwritten with the emitted integers, separated by spaces.

Useful options:

```sh
python3 -m interpreter run PROGRAM.man INPUT.txt OUTPUT.txt \
  --tick-limit 5000000 \
  --json
```

`run` executes until all little men stop and the output pipe drains, an error occurs, or the tick limit is reached.

## Check a solution and calculate scores

```sh
python3 -m interpreter check PROGRAM.man INPUT.txt EXPECTED.txt
```

To retain the values emitted before the check finishes:

```sh
python3 -m interpreter check PROGRAM.man INPUT.txt EXPECTED.txt \
  --actual-output ACTUAL.txt \
  --json
```

On success, the report includes:

- `footprint`: `max(width, height)^2`;
- `footprint_tick`: `footprint * ticks` for this test case;
- the dimensions, tick count, and number of emitted values.

The official footprint-tick score averages ticks across all test cases. This command checks one test case, so its tick count is that one-case average. A future batch command can combine multiple cases without changing the interpreter.

## Rounds

Use `/` to separate rounds in both input and expected-output files:

```text
1 42 / 2 41 42
```

All rounds execute in one machine run. Input after a slash remains withheld until the preceding expected-output round is complete.

The input and expected-output files must contain the same number of rounds when using `check`.

## Display support

The runtime parses and executes LM-75 displays, including address, data, and swap pipes. It records committed frames in `ExecutionResult.display_frames`.

The CLI checker currently compares numeric output files only. We should add display checking after choosing a repository format for expected frame images or color-index matrices.

## Tests

```sh
python3 -m unittest discover -s interpreter/tests -v
```

The current tests cover room and pipe parsing, numeric literals, output checking, staged rounds, tick counting, scoring, and the CLI.
