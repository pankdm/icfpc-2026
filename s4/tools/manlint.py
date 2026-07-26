"""Cheap structural checks a floorplan search can afford on every proposal.

``littleman.Program`` places glyphs without validating anything, and the two
failure modes that a moved component produces are both silent until the oracle's
loader rejects the grid:

  * a pipe drawn through another pipe or through a room wall -- recorded by
    ``Program.overwrites`` (wall-glyph-on-wall-glyph is the legal case: room
    corners and shared walls);
  * an accidental literal.  Backticks pair up along a row *and* down a column,
    and every cell between a pair must be a digit or a space.  Two components
    whose init literals land in one column therefore turn the whole span between
    them into a malformed literal.

Both checks are pure string work, so they cost microseconds next to the ~0.5 s
an oracle round-trip needs.
"""

WALL = set("+-|:=")
DIGITS = set("0123456789")


def bad_overwrites(program):
    """Clobbers that are not room-drawing artefacts."""
    return [o for o in program.overwrites
            if not (o[2] in WALL and o[3] in WALL)]


def literal_faults(rows):
    """Backtick pairs, along rows and down columns, that span a non-digit."""
    faults = []
    width = max((len(r) for r in rows), default=0)
    grid = [r.ljust(width) for r in rows]

    def scan(cells, label):
        ticks = [i for i, ch in enumerate(cells) if ch == "`"]
        for a, b in zip(ticks[0::2], ticks[1::2]):
            for k in range(a + 1, b):
                if cells[k] not in DIGITS and cells[k] != " ":
                    faults.append((label, a, b, cells[k]))
                    break

    for y, row in enumerate(grid):
        scan(row, f"row{y}")
    for x in range(width):
        scan([grid[y][x] for y in range(len(grid))], f"col{x}")
    return faults


def check(program):
    """None when the grid is structurally plausible, else a reason string."""
    bad = bad_overwrites(program)
    if bad:
        return f"{len(bad)} collisions, first {bad[0]}"
    faults = literal_faults(program.render().split("\n"))
    if faults:
        return f"{len(faults)} malformed literals, first {faults[0]}"
    return None
