"""Reusable grid-walking helper for hand-building littleman state machines.

Why this exists: littleman programs are laid out as raw (x, y) -> char grids,
and turn instructions (`>`,`<`,`^`,`v`) change the little man's facing *before*
the tick's move happens. Hand-computing column offsets for a multi-cell path
(especially ones with literals, whose digit order flips with direction) is
extremely easy to get off-by-one on. `Cursor` mechanically applies the same
execute-then-move semantics the interpreter uses, so the column arithmetic
can't drift out of sync with hand-counting.

Used by lead_expander.py and phrase_expander.py in this folder.
"""
from littleman import Program  # requires tools/ on sys.path; see callers

DIRS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
ARROW_DIR = {">": "E", "<": "W", "^": "N", "v": "S", "V": "S"}


class Cursor:
    """Walks a Program grid the way the littleman interpreter does: place a
    char, then move one cell in the (possibly just-updated) facing."""

    def __init__(self, program: Program, x: int, y: int, facing: str = "E"):
        self.p = program
        self.x, self.y = x, y
        self.facing = facing

    def step(self, ch: str) -> "Cursor":
        cur = self.p.get(self.x, self.y)
        if cur != " ":
            raise ValueError(f"cell ({self.x},{self.y}) already has {cur!r}, tried to place {ch!r}")
        self.p.put(self.x, self.y, ch)
        if ch in ARROW_DIR:
            self.facing = ARROW_DIR[ch]
        dx, dy = DIRS[self.facing]
        self.x += dx
        self.y += dy
        return self

    def lit(self, value: int) -> "Cursor":
        """Place a backtick-delimited literal in the current facing (E or W
        only). Digit order is pre-reversed for W so it reads correctly when
        crossed right-to-left later -- see PROBLEM.md: "direction determines
        digit order"."""
        digits = str(value)
        if self.facing == "W":
            digits = digits[::-1]
        elif self.facing != "E":
            raise ValueError("lit() only supports E/W placement")
        self.step("`")
        for d in digits:
            self.step(d)
        self.step("`")
        return self

    def pad_to(self, target_x: int, filler: str = ".") -> "Cursor":
        """Step no-ops until the *next* step would land exactly on target_x.
        Only meaningful if the cursor hasn't already passed target_x -- callers
        must reserve enough distance between branch points for this to have
        room to work (see phrase_expander.py's ROW1_FIXED_PREFIX budgeting)."""
        if self.facing == "W":
            while self.x - 1 > target_x:
                self.step(filler)
        elif self.facing == "E":
            while self.x + 1 < target_x:
                self.step(filler)
        else:
            raise ValueError("pad_to only supports E/W")
        return self
