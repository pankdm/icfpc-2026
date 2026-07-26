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
    """Clobbers that are not room-drawing artefacts.

    Only ``room`` may clobber a wall glyph with a wall glyph -- that is corners
    and shared walls.  A *pipe* writing ``|`` over a ``-`` looks identical but is
    two pipes crossing, or a pipe cutting a wall, which the loader rejects with
    "pipe interrupted".  Judging the glyph pair alone silently accepts both.
    """
    return [o for o in program.overwrites
            if not (o[4] == "room" and o[2] in WALL and o[3] in WALL)]


def literal_faults(rows):
    """Backtick pairs, along rows and down columns, that span a non-digit.

    Only lines that actually hold two or more backticks are materialised -- a
    floorplan search calls this on every proposal, and walking all ~200 columns
    of a grid to find the three that matter dominated the search's cost.
    """
    faults = []
    ticks_at = {}
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "`":
                ticks_at.setdefault(y, []).append(x)

    def scan(cells, ticks, label):
        for a, b in zip(ticks[0::2], ticks[1::2]):
            for k in range(a + 1, b):
                ch = cells[k]
                if ch not in DIGITS and ch != " ":
                    faults.append((label, a, b, ch))
                    break

    for y, ticks in ticks_at.items():
        if len(ticks) >= 2:
            scan(rows[y].ljust(ticks[-1] + 1), ticks, f"row{y}")
    columns = {}
    for y, ticks in ticks_at.items():
        for x in ticks:
            columns.setdefault(x, []).append(y)
    for x, ys in columns.items():
        if len(ys) < 2:
            continue
        cells = [rows[y][x] if x < len(rows[y]) else " " for y in range(len(rows))]
        scan(cells, sorted(ys), f"col{x}")
    return faults


def dangling_pipes(program):
    """Pipes whose first/last cell is not against a room or display border.

    The loader wants both ends adjacent to a wall ("pipe ends without reaching
    another room"), and a wall cannot be recognised by its glyph because pipe
    bodies use the same '-' and '|'.
    """
    bad = []
    for i, (first, last, _n, back, fwd) in enumerate(program.pipes):
        for side, cell in (("head", back), ("tail", fwd)):
            if (program.get(*cell) not in WALL
                    or cell in program.pipe_cells):
                bad.append((i, side))
    return bad


# The banked RAM servers hand out reply attachments *inside* their own component
# (split_belts deletes the proxy I/O rooms, leaving a gap that is not a wall), so
# a correct build still reports a few loose ends.  They are the same pipes every
# time -- `_compact_components` emits pipes in a fixed order -- so a search must
# compare the loose-end *set* against its baseline, not the count: a candidate
# that accidentally fixes one known end has budget left over to break a real one,
# which is exactly how a 36,864-box snake candidate passed a count check and then
# failed every case with "pipe ends without reaching another room".
def dangling_signature(program):
    return frozenset(dangling_pipes(program))


def check(program, allow_dangling=None):
    """None when the grid is structurally plausible, else a reason string."""
    bad = bad_overwrites(program)
    if bad:
        return f"{len(bad)} collisions, first {bad[0]}"
    loose = dangling_signature(program)
    if allow_dangling is not None and loose != allow_dangling:
        return (f"dangling pipe ends {sorted(loose)} differ from the expected "
                f"{sorted(allow_dangling)}")
    if allow_dangling is None and loose:
        return f"{len(loose)} dangling pipe ends, first {sorted(loose)[0]}"
    faults = literal_faults(program.render().split("\n"))
    if faults:
        return f"{len(faults)} malformed literals, first {faults[0]}"
    return None
