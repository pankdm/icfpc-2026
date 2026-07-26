"""bindsolve.py — enumerate every legal pipe-ATTACHMENT assignment for a room.

WHY THIS EXISTS.  `r`/`s`/`q` lock onto the NEAREST pipe segment attached to the
room (Manhattan distance from the instruction cell to the attachment cell, ties
broken by reading order).  So a room's pipe geometry silently decides which pipe
every single op talks to, and:

  * moving a room, or nudging one attachment, RE-BINDS instructions with no error;
  * a cell sitting exactly on the midpoint between two attachments TIES and
    resolves by reading order, reaching the wrong room;
  * none of this shows up as a load error, and a full public-case pass will not
    catch it — it surfaces only as silently wrong values or a private failure.

Deriving midpoints by hand is how designs in this repo have quietly broken.  Don't:
state which pipe each op MUST reach and let this enumerate the assignments that
satisfy all of them strictly.  The search is tiny (walls x positions, cubed for
three pipes is ~1e5), so brute force is the right tool.

    from bindsolve import solve
    sols = solve(w=15, h=27, want={
        'cmdA': [(5, 5), (2, 7), (5, 9), (5, 13)],     # cells that must reach cmdA
        'cmdB': [(8, 4), (7, 8), (9, 8), (8, 12)],
        'sel':  [(12, 25)],
    })
    # -> [{'cmdA': (-1, 24), 'cmdB': (15, 23), 'sel': (12, 27)}, ...]

Coordinates are ROOM-LOCAL: the room's outer rect is (0,0)..(w-1,h-1), its
interior is 1..w-2 x 1..h-2, and a returned attachment is the PIPE CELL just
outside a non-corner wall cell — x=-1 / x=w for the side walls, y=-1 / y=h for the
top and bottom.  Add the room's origin to get grid coordinates, and note that the
matching BORDER (wall) cell — what tools/router.py wants as a net endpoint — is the
attachment clamped back onto the wall.

Separate calls for incoming and outgoing pipes: `s`/`S` compare only among
OUTGOING pipes and `r`/`R`/`U`/`q` only among INCOMING ones, so the two groups
never interfere and solving them together only invents constraints.

A returned assignment guarantees STRICT nearest-ness for every listed cell — no
ties anywhere — so it is safe against reading-order surprises.  An EMPTY result is
information, not a dead end: it means no geometry can separate those ops, and the
op layout itself has to change.  That happened in the memory dual-head build (see
solutions/memory/dualhead2_floor.py): sending two tokens down the selector pipe
had zero valid assignments, which is what forced the register trick that reduced
it to one send.
"""

Attachment = tuple


def wall_attachments(w, h, walls="LRTB"):
    """Every legal attachment cell (pipe cell outside a non-corner wall cell)."""
    out = []
    if "L" in walls:
        out += [(-1, y) for y in range(1, h - 1)]
    if "R" in walls:
        out += [(w, y) for y in range(1, h - 1)]
    if "T" in walls:
        out += [(x, -1) for x in range(1, w - 1)]
    if "B" in walls:
        out += [(x, h) for x in range(1, w - 1)]
    return out


def wall_of(att, w, h):
    """Which wall an attachment sits on ('L'/'R'/'T'/'B')."""
    x, y = att
    return "L" if x < 0 else "R" if x >= w else "T" if y < 0 else "B"


def border_cell(att, w, h):
    """The wall cell behind an attachment — the endpoint tools/router.py wants."""
    x, y = att
    return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))


def _d(cell, att):
    return abs(cell[0] - att[0]) + abs(cell[1] - att[1])


def check(assign, want):
    """True iff every cell in want[name] is STRICTLY nearest to assign[name]."""
    for name, cells in want.items():
        mine = assign[name]
        for cell in cells:
            mine_d = _d(cell, mine)
            for other, att in assign.items():
                if other != name and _d(cell, att) <= mine_d:
                    return False
    return True


def solve(w, h, want, walls=None, limit=None):
    """All strictly-valid attachment assignments for the pipes named in `want`.

    `want` maps pipe name -> the op cells that must bind to it (room-local).
    `walls` optionally restricts a pipe to a subset of "LRTB", e.g.
    {'cmdA': 'L', 'cmdB': 'R'} to keep a controller between two consumers.
    """
    walls = walls or {}
    names = list(want)
    cands = {n: wall_attachments(w, h, walls.get(n, "LRTB")) for n in names}
    sols = []

    def rec(i, assign):
        if limit is not None and len(sols) >= limit:
            return
        if i == len(names):
            if check(assign, want):
                sols.append(dict(assign))
            return
        n = names[i]
        for att in cands[n]:
            if att in assign.values():
                continue
            assign[n] = att
            rec(i + 1, assign)
            del assign[n]

    rec(0, {})
    return sols


if __name__ == "__main__":
    # The memory dual-head CONTROL, as actually solved: 68 assignments.
    sols = solve(15, 27, {
        'cmdA': [(5, 5), (2, 7), (5, 9), (5, 13), (2, 15), (5, 17), (5, 21), (4, 23)],
        'cmdB': [(8, 4), (7, 8), (9, 8), (8, 12), (7, 16), (9, 16), (11, 21), (10, 23)],
        'sel': [(12, 25)],
    })
    print(len(sols), "strictly-valid assignments")
    for s in sols[:5]:
        print({k: (v, wall_of(v, 15, 27)) for k, v in s.items()})
