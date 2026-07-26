"""Compact packed-request adapter for the standard RAM protocol.

External protocol:
  * 0..255: read that address
  * ``-(address+1), value``: write ``value`` at address

Reads are atomic, which is the important hot path for search algorithms.
"""


def build(program, ox, oy):
    """Stamp a 9x18 hand adapter and return pipe-facing endpoints."""
    program.room(ox, oy, 9, 18)
    program.text(ox + 2, oy + 1, ">rv")
    program.text(ox + 1, oy + 2, "@^vXv")

    # Positive/zero read arm. Zero falls south from X and turns into it.
    for offset, glyph in enumerate("M0sWs", start=3):
        program.put(ox + 3, oy + offset, glyph)
    program.put(ox + 4, oy + 3, "<")
    program.put(ox + 3, oy + 8, "<")
    program.put(ox + 2, oy + 8, "^")

    # Negative write arm: recover address, emit [1,address], then consume and
    # forward the following value.
    for offset, glyph in enumerate("NM1W-M1sWsrs", start=3):
        program.put(ox + 5, oy + offset, glyph)
    program.put(ox + 5, oy + 15, "<")
    program.put(ox + 2, oy + 15, "^")

    return {
        "command": (ox + 3, oy - 1),
        "expanded": (ox + 9, oy + 10),
    }
