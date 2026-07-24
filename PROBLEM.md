# ICFP Programming Contest 2026: Problem Description

This document summarizes the contest model, the Littleman language, judging, and scoring. It is intended as a practical reference for implementing generators, interpreters, optimizers, and solutions. Individual assignments define their own input/output behavior and may override general limits such as the step cap.

## Contest Objective

For each graded assignment, submit a Littleman (`.man`) program that produces the required sequence of integer outputs, or the required sequence of LM-75 display frames, for every test case.

Submissions are evaluated on public and private tests. A program passes a test as soon as it emits the complete expected output in the correct order; it does not need to halt. Emitting a wrong value fails the test immediately. Ending execution before all expected output is produced also fails the test.

Most assignments reward both correctness and efficiency. Efficiency is based on the program's spatial footprint and, usually, its execution time in ticks.

## Program Model

A Littleman program is a rectangular grid of ASCII characters. Short source lines are padded with spaces to the width of the longest line.

- A room is a rectangle whose corners are `+`, horizontal walls are `-`, and vertical walls are `|`.
- Each ordinary room contains at most one starting position, `@`.
- The little man spawned at `@` initially faces right.
- Each little man has three signed 64-bit integer registers: main hand `A`, off hand `B`, and backpack `BP`. All start at zero.
- Arithmetic wraps on signed 64-bit overflow.
- Time advances in discrete ticks, and all little men run in lockstep.
- On each tick a little man executes the cell under him, then moves one cell in his current direction unless the instruction blocks or halts him.
- Running into a room wall or executing an invalid character is a fatal error that ends the entire program.
- Execution is deterministic.

Multiple rooms and little men may appear in one program. Rooms cannot overlap or nest.

## Tick Order

Each tick performs these phases in order:

1. **Pipe movement:** every pipe value advances one cell toward its destination if the next cell is free.
2. **I/O:** a value at the output pipe's end is emitted, then the next available input value enters the input pipe if possible.
3. **Execution:** every little man executes his current instruction; displays consume their available inputs.
4. **Movement:** every non-blocked, non-halted little man advances one cell.

A value sent during the current tick begins moving on the next tick. A value that reaches a pipe's destination during the pipe phase may be received in the execution phase of that same tick.

## Instruction Set

Stepping on any character not recognized as an instruction is a fatal error.

### Constants and Registers

| Instruction | Effect |
| --- | --- |
| `0`–`9` | Set `A` to that digit. |
| `` `...` `` | Load a multi-digit literal into `A` when crossing the closing backtick. Spaces inside are ignored; direction determines digit order. |
| `M` | `B = A`. |
| `W` | Swap `A` and `B`. |
| `b` | `BP = A`. |
| `m` | Decrement `BP`, with no clamp. |
| `q` | Set `BP` to the number of values in the nearest incoming pipe. |
| `]` | Arithmetic right-shift `BP` by one bit. |

Numeric literals may be horizontal or vertical and may overlap under the detailed rules in the language reference. A literal must fit in signed 64-bit range when read in either direction.

### Arithmetic and Bitwise Operations

| Instruction | Effect |
| --- | --- |
| `+` | `A = A + B`. |
| `-` | `A = A - B`. |
| `*` | `A = A * B`. |
| `%` | `A = A mod B`, with the divisor's sign; returns `0` when `B = 0`. |
| `/` | Floored division: quotient goes to `A`, remainder to `B`. If `B = 0`, `A = 0` and `B` retains the dividend. |
| `N` | `A = -A`. |
| `&` | `A = A AND B`. |
| `\|` | `A = A OR B`. |
| `~` | `A = A XOR B`. |
| `{` | Left shift `A` by `B`; returns `0` if `B` is outside `0..63`. |
| `}` | Arithmetic right shift; returns `0` if `B < 0`, and sign-fills if `B > 63`. |

Bitwise operations use 64-bit two's-complement representation.

### Direction and Control

| Instruction | Effect |
| --- | --- |
| `>` | Face right/east. |
| `<` | Face left/west. |
| `^` | Face up/north. |
| `v` or `V` | Face down/south. |
| `X` | Turn clockwise if `A > 0`, counter-clockwise if `A < 0`, otherwise continue straight. |
| `d` | Turn clockwise if `BP > 0`, otherwise continue straight. |
| `a` | Turn counter-clockwise if `BP > 0`, otherwise continue straight. |
| `x` | Turn clockwise if the low bit of `BP` is `1`, otherwise counter-clockwise. |
| `.` or space | No operation; continue straight. |
| `H` | Halt this little man. |

A little man also stops when he touches another little man; both stop. The program continues while at least one little man remains active.

## Pipes and Concurrency

Pipes are directed, bounded channels connecting rooms.

- A pipe is at least two cells long.
- Arrowheads `>`, `<`, `^`, and `v` establish flow direction and bends.
- Horizontal sections use `-`; vertical sections use `|`.
- Both endpoints require arrowheads.
- Each pipe cell holds at most one value, so a pipe of length `n` can contain at most `n` values.
- Values move at most one cell per tick.
- A blocked send or receive leaves the little man in place to retry on the next tick.

### Pipe Instructions

| Instruction | Effect |
| --- | --- |
| `s` | Send `A` to the nearest outgoing pipe; block while its source cell is occupied. |
| `S` | Atomically send `A` to every outgoing pipe; block unless all source cells are free. |
| `r` | Receive from the nearest incoming pipe into `A`; block if no value is ready there. |
| `R` | Receive into `A` from any incoming pipe with a ready value; block if none are ready. |
| `U` | Like `R`, then turn away from the pipe that supplied the value. |

Using a send instruction in a room with no outgoing pipe, or a receive/`q` instruction in a room with no incoming pipe, is a fatal `no-pipe` error.

For a nearest-pipe operation, distance is the Manhattan distance from the instruction cell to the pipe segment attached to the room. Ties use reading order: top-to-bottom, then left-to-right. `R` and `U` choose among ready incoming pipes in reading order. They do not use geometric distance. `S` waits for all outgoing pipes.

## Input and Output

Input and output use special 3×3 rooms:

- The input room contains a single `I` and has exactly one outgoing pipe.
- The output room contains a single `O` and has exactly one incoming pipe.
- A program may contain at most one input room and one output room.
- Extra pipes, reversed pipes, or duplicate I/O rooms are load errors.
- A pipeless I/O room is legal.

Input is a whitespace-separated sequence of signed integers. When the input pipe's source cell is free, the next available value enters it. A value reaching the output pipe's destination is consumed and appended to program output.

Some test cases contain multiple rounds. All rounds share one program run; state is not reset. Input for the next round remains withheld until the expected output for the current round has been emitted. A round expecting no output unlocks the next round immediately.

## LM-75 Display

Some assignments require display frames instead of integer output. An LM-75 display is a rectangular room with `+` corners, `=` horizontal borders, and `:` vertical borders. Its interior is at most 64×64 cells.

The display has a current buffer, a next buffer, and a cursor. Both buffers start black (color `0`), and the cursor starts at the upper-left pixel.

Pipes are interpreted by the side they connect to:

| Side | Function |
| --- | --- |
| Top | **ADDR:** set cursor from `row * width + column`. Out-of-range or negative addresses are errors. |
| Left | **DATA:** write color `0..15` into the next buffer at the cursor, then advance the cursor in reading order with wraparound. |
| Bottom | **SWAP:** commit the next buffer. `0` also clears next and resets the cursor; `1` preserves next and the cursor. |

The display can consume one value from each of its three pipes in the same tick, in `ADDR`, `DATA`, `SWAP` order. Multiple pipes on one side, a pipe on the right, or a corner connection is a load error.

For a display assignment:

- The program must contain exactly one display at the required resolution.
- Ordinary output is forbidden.
- Every committed frame must match the next expected frame exactly.
- The final expected frame determines successful completion and tick count.

## Halting and Failure

A test run ends when:

1. every little man has stopped,
2. a fatal error occurs, or
3. the assignment's tick cap is reached.

If the last little man halts while values remain in the output pipe, pipes and I/O continue ticking until that pipe drains or the tick cap is reached.

Common runtime errors are:

- `wall`: a little man entered a room wall;
- `bad-op`: a little man executed an invalid character;
- `no-pipe`: a pipe instruction has no pipe of the required direction.

Malformed rooms, pipes, I/O rooms, displays, or literals can instead reject the program at load time.

## Tests and Submission

- Public tests are visible on the problem page and in the editor.
- Private tests are hidden but are intended to test the same behavior without hidden tricks.
- Grading uses both public and private tests.
- Submissions are graded asynchronously.
- Only the best submission for each problem counts, so a later submission cannot reduce the team's score.
- Programs are limited to 10 MB.
- Most assignments use a 5,000,000-tick cap; assignment pages may specify another cap.

## Program Efficiency Score

Lower program scores are better. Each assignment states which scoring method it uses.

Most assignments use **footprint-tick scoring**:

```text
max(width, height)^2 * average ticks across all test cases
```

Some assignments use **footprint-only scoring**:

```text
max(width, height)^2
```

`width` and `height` are the bounding-box dimensions of the entire source program. A test's tick count ends when the final correct output value is emitted, or when the final expected display frame is committed. Ticks after successful output are not counted.

## Contest Points and Ranking

Each graded problem contributes up to 2 contest points.

To be eligible for points, a team must pass at least one private test. If a problem has no private tests, passing any test is sufficient.

### Test-Case Point

Up to one point is awarded for correctness:

```text
test-case points = passed test cases / total test cases
```

### Ranking Point

Up to one additional point is awarded relative to other eligible teams:

```text
ranking points = other eligible teams ranked below or tied / other eligible teams
```

Teams are first ranked by number of passing test cases. Teams passing every test are additionally ranked by program efficiency score, where lower is better. Ties are allowed. A sole eligible team receives the full ranking point.

The team's contest result is the sum of its best point total on every graded problem. Ungraded practice problems do not count.

## Practical Implications

- Correct streaming behavior matters more than halting.
- General solutions are necessary because private tests discourage hardcoded public answers.
- Program geometry matters: reducing the larger bounding-box dimension can be more valuable than reducing area.
- For footprint-tick problems, optimize both footprint and average latency across tests.
- Pipe length affects capacity and communication delay.
- Round-based tests require persistent state and may withhold input until output is produced.
- Concurrent little men can improve latency but increase footprint and introduce blocking constraints.

## Official Sources

- [Textbook](https://icfpcontest2026.com/textbook)
- [Language Reference](https://icfpcontest2026.com/language-reference)
- [Grading](https://icfpcontest2026.com/grading)
- [Contest Rules](https://icfpcontest2026.com/rules)

This summary was prepared from the live official pages on 2026-07-24. The official assignment pages and documentation remain authoritative.
