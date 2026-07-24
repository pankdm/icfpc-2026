"""Generate an append-log implementation of the memory problem.

Writes append ``address + 1, value`` records to a pipe-resident log.  A read
appends ``-1``, scans and re-appends the complete log, and sends every matching
value to an accumulator.  A separate done pipe tells the accumulator to output
the last match, or zero when there was no match.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import littleman as lm


CONTROLLER_TOP = 5
CONTROLLER_BOTTOM = 32
WORKER_LEFT = 32
WORKER_RIGHT = 47
LOG_END = -1


def build_stream_log_memory() -> lm.Program:
    program = lm.Program()
    program.room(0, CONTROLLER_TOP, 30, CONTROLLER_BOTTOM - CONTROLLER_TOP + 1)
    program.room(
        WORKER_LEFT,
        CONTROLLER_TOP,
        WORKER_RIGHT - WORKER_LEFT + 1,
        CONTROLLER_BOTTOM - CONTROLLER_TOP + 1,
    )

    _place_controller(program)
    _place_worker(program)
    _place_io(program)
    _place_control_pipes(program)
    _place_log_pipes(program)
    return program


def _controller_put(program: lm.Program, x: int, y: int, character: str) -> None:
    program.put(x, CONTROLLER_TOP + y, character)


def _place_controller(program: lm.Program) -> None:
    put = lambda x, y, character: _controller_put(program, x, y, character)

    # Input dispatch. READ continues east; WRITE turns south.
    put(1, 3, ">")
    put(2, 3, "@")
    put(3, 3, "r")
    put(4, 3, "X")

    # READ: keep address+1 in B, append the negative log terminator, then scan.
    put(5, 3, "r")
    put(6, 3, "M")
    put(7, 3, "1")
    put(8, 3, "+")
    put(9, 3, "M")
    put(10, 3, str(abs(LOG_END)))
    put(11, 3, "N")
    put(12, 3, "v")
    put(12, 16, ">")
    put(14, 16, "s")
    put(20, 16, "^")
    put(20, 8, "<")

    # Scan a record key. Positive keys turn north; the terminator turns south.
    put(10, 8, "r")
    put(9, 8, "X")

    # Re-append the key and compare it on a low row where s selects LOG.
    put(9, 7, "<")
    put(2, 7, "v")
    put(2, 14, ">")
    put(14, 14, "s")
    put(15, 14, "-")
    put(16, 14, "X")

    # Save a match flag in BP, then merge all three comparison branches.
    put(17, 14, "b")
    put(18, 14, "v")
    put(18, 18, "<")
    put(9, 18, "v")

    put(16, 13, "1")
    put(16, 12, "b")
    put(16, 10, "<")
    put(10, 10, "v")

    put(16, 15, "1")
    put(16, 16, "b")
    put(16, 20, "<")
    put(10, 20, "v")

    # Re-append the value. BP==0 copies it to DATA; BP>0 skips DATA.
    put(9, 22, ">")
    put(10, 22, ">")
    put(11, 22, "r")
    put(14, 22, "s")
    put(16, 22, "d")
    put(24, 22, "s")
    put(25, 22, "^")
    put(25, 8, "<")
    put(16, 24, ">")
    put(25, 24, "^")

    # End of scan: signal DONE and return to the input dispatcher.
    put(9, 9, ">")
    put(24, 9, "s")
    put(28, 9, "v")
    put(28, 25, "<")
    put(27, 25, "<")
    put(1, 25, "^")

    # WRITE: append address+1, then append the unmodified value.
    put(4, 4, "<")
    put(3, 4, "v")
    put(3, 17, ">")
    put(4, 17, "r")
    put(5, 17, "M")
    put(6, 17, "1")
    put(7, 17, "+")
    put(14, 17, "s")
    put(27, 17, "v")
    put(27, 19, "<")
    put(3, 19, "v")
    put(3, 21, ">")
    put(4, 21, "r")
    put(14, 21, "s")
    put(27, 21, "v")


def _place_worker(program: lm.Program) -> None:
    # U distinguishes three incoming streams by attachment direction:
    # LOG from below -> north, DATA from the left -> east, DONE from above -> south.
    program.put(41, 21, "@")
    program.put(42, 21, ">")
    program.put(43, 21, ">")
    program.put(44, 21, "U")

    # LOG: forward unchanged to the return pipe, then loop back to U.
    program.put(44, 12, ">")
    program.put(45, 12, "s")
    program.put(46, 12, "v")
    program.put(46, 21, "v")
    program.put(46, 24, "<")
    program.put(43, 24, "^")

    # DATA: remember the latest matching value in B, then join the U loop.
    program.put(45, 21, "M")

    # DONE: output B, reset B to zero, and return to U.
    program.put(44, 22, "W")
    program.put(44, 23, "<")
    program.put(34, 23, "^")
    program.put(34, 9, ">")
    program.put(43, 9, "s")
    program.put(44, 9, "0")
    program.put(45, 9, "M")
    program.put(46, 9, "v")
    program.put(46, 11, "<")
    program.put(42, 11, "v")


def _place_io(program: lm.Program) -> None:
    program.input_room(1, CONTROLLER_BOTTOM + 4)
    program.pipe([(2, CONTROLLER_BOTTOM + 3), (2, CONTROLLER_BOTTOM + 1)])

    program.output_room(51, 8)
    program.pipe([(48, 9), (50, 9)])


def _place_control_pipes(program: lm.Program) -> None:
    # Matching values: controller -> worker DATA (left attachment).
    program.pipe([(30, 21), (31, 21)])

    # End-of-scan token: controller -> worker DONE (top attachment).
    program.pipe([(30, 14), (31, 14), (31, 3), (44, 3), (44, 4)])


def _place_log_pipes(program: lm.Program) -> None:
    # Controller LOG output -> worker LOG input.  The serpent stops at x=42 so
    # column 44 remains available for the final upward leg into the worker.
    outbound = [
        (14, CONTROLLER_BOTTOM + 1),
        (14, CONTROLLER_BOTTOM + 6),
        (10, CONTROLLER_BOTTOM + 6),
        (10, CONTROLLER_BOTTOM + 7),
    ]
    y = CONTROLLER_BOTTOM + 7
    rightward = True
    for row in range(9):
        x = 42 if rightward else 10
        outbound.append((x, y))
        if row != 8:
            y += 1
            outbound.append((x, y))
        rightward = not rightward
    outbound.extend([(44, y), (44, CONTROLLER_BOTTOM + 1)])
    program.pipe(outbound)

    # Worker LOG return -> controller LOG input.  This pipe alone must hold the
    # complete re-appended log so the worker can leave its relay path and process
    # DONE after a scan.
    returned = [(48, 12), (49, 12), (49, CONTROLLER_BOTTOM + 17)]
    y = CONTROLLER_BOTTOM + 17
    leftward = True
    for row in range(15):
        x = 9 if leftward else 48
        returned.append((x, y))
        if row != 14:
            y += 1
            returned.append((x, y))
        leftward = not leftward
    returned.extend([(8, y), (8, CONTROLLER_BOTTOM + 1)])
    program.pipe(returned)


def main() -> None:
    output = Path(__file__).with_name("stream-log.man")
    program = build_stream_log_memory()
    program.save(output)
    width, height, footprint = program.footprint()
    print(f"wrote {output} ({width}x{height}, footprint {footprint})")


if __name__ == "__main__":
    main()
