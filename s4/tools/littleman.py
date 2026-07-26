"""littleman.py — a Python API for building littleman (.man) programs.

Build a program by placing rooms, men, instructions, pipes, I/O rooms and displays
on a grid, then:
    p = Program()
    ...
    print(p.render())            # the .man text
    p.footprint()                # (w, h, max(w,h)**2)  -- lower score is better
    p.grade("triangle")          # local grade vs the reference oracle (needs Node)
    p.save("solutions/triangle/mine.man")

Coordinates are (x, y) = (col, row), y grows downward. render() trims to the
non-space bounding box, so absolute placement offsets don't matter — compose freely.

──────────────────────────────────────────────────────────────────────────────
EXTENDING THIS API (for solution agents):
  Add reusable, well-named builders as you discover common patterns — e.g. a
  length-prefixed read loop, an int-output tail, a backpack countdown, a display
  raster filler. Put higher-level patterns BELOW the `# === PATTERNS ===` marker
  and document each with a one-line docstring. Keep the core primitives stable.
──────────────────────────────────────────────────────────────────────────────
"""
import os
import json
import tempfile
import subprocess
from collections import namedtuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIRS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
ARROW = {"E": ">", "W": "<", "N": "^", "S": "v"}
VEC2ARROW = {(1, 0): ">", (-1, 0): "<", (0, 1): "v", (0, -1): "^"}
Rect = namedtuple("Rect", "x0 y0 x1 y1 ix0 iy0 ix1 iy1")  # outer + inclusive interior


class Program:
    def __init__(self):
        self.cells = {}
        # Every clobber of one non-space glyph by a different one. `pipe` and
        # `room` overwrite silently, so a floorplan search has no other cheap
        # way to tell a colliding proposal from a legal one (the symptom is a
        # loader "pipe interrupted" much later).  Recording is free; nothing
        # reads this unless a caller chooses to.
        self.overwrites = []
        # (first_cell, last_cell, length) per pipe.  A pipe's length is its FIFO
        # capacity as well as its latency, so a floorplan search that reshapes a
        # queue has to be able to check it did not shrink below the deepest
        # frontier the program can enqueue.
        self.pipes = []

    # ---- primitives ----
    def put(self, x, y, ch, kind="cell"):
        old = self.cells.get((x, y))
        if old is not None and old != " " and old != ch:
            # `kind` matters because room drawing legitimately clobbers wall
            # glyphs with wall glyphs (corners, shared walls) while a pipe
            # crossing a wall or another pipe writes exactly the same pair of
            # glyphs and is fatal ("pipe interrupted" at load time).
            self.overwrites.append((x, y, old, ch, kind))
        self.cells[(x, y)] = ch
        return self

    def get(self, x, y):
        return self.cells.get((x, y), " ")

    def text(self, x, y, s, d="E"):
        """Place a run of characters starting at (x,y) heading d (E/W/N/S)."""
        dx, dy = DIRS[d]
        for i, ch in enumerate(s):
            self.put(x + i * dx, y + i * dy, ch)
        return self

    def room(self, x, y, w, h, glyphs="+-|"):
        """Draw a w×h room with top-left at (x,y). Returns its Rect (outer + interior)."""
        cor, hor, ver = glyphs
        for i in range(w):
            self.put(x + i, y, hor, "room")
            self.put(x + i, y + h - 1, hor, "room")
        for j in range(h):
            self.put(x, y + j, ver, "room")
            self.put(x + w - 1, y + j, ver, "room")
        for cx, cy in [(x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)]:
            self.put(cx, cy, cor, "room")
        return Rect(x, y, x + w - 1, y + h - 1, x + 1, y + 1, x + w - 2, y + h - 2)

    def input_room(self, x, y):
        r = self.room(x, y, 3, 3)
        self.put(x + 1, y + 1, "I")
        return r

    def output_room(self, x, y):
        r = self.room(x, y, 3, 3)
        self.put(x + 1, y + 1, "O")
        return r

    def display(self, x, y, w, h):
        """LM-75 display room (corners +, horizontal =, vertical :)."""
        return self.room(x, y, w, h, glyphs="+=:")

    def man(self, x, y):
        self.put(x, y, "@")
        return self

    def pipe(self, points):
        """Draw a pipe through orthogonal waypoints [(x,y), ...].
        Arrowheads at the start, every bend, and the end; body glyphs on straights.
        The start cell's *backward* neighbour must sit on the source room's border and
        the end cell's *forward* neighbour on the destination room's border.
        """
        cells = []
        for i in range(len(points) - 1):
            (x0, y0), (x1, y1) = points[i], points[i + 1]
            dx = (x1 > x0) - (x1 < x0)
            dy = (y1 > y0) - (y1 < y0)
            for k in range(abs(x1 - x0) + abs(y1 - y0)):
                cells.append((x0 + dx * k, y0 + dy * k, dx, dy))
        lx, ly = points[-1]
        cells.append((lx, ly, cells[-1][2], cells[-1][3]))
        for idx, (x, y, dx, dy) in enumerate(cells):
            bend = idx > 0 and (cells[idx - 1][2], cells[idx - 1][3]) != (dx, dy)
            if idx == 0 or idx == len(cells) - 1 or bend:
                self.put(x, y, VEC2ARROW[(dx, dy)], "pipe")
            else:
                self.put(x, y, "-" if dx != 0 else "|", "pipe")
        self.pipes.append((points[0], points[-1], len(cells)))
        return self

    # ---- output / scoring ----
    def bounds(self):
        pts = [p for p, c in self.cells.items() if c != " "]
        if not pts:
            return (0, 0, -1, -1)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def render(self):
        minx, miny, maxx, maxy = self.bounds()
        if maxx < minx:
            return ""
        rows = []
        for y in range(miny, maxy + 1):
            rows.append("".join(self.get(x, y) for x in range(minx, maxx + 1)).rstrip())
        return "\n".join(rows)

    def footprint(self):
        minx, miny, maxx, maxy = self.bounds()
        if maxx < minx:
            return (0, 0, 0)
        w, h = maxx - minx + 1, maxy - miny + 1
        return (w, h, max(w, h) ** 2)

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w") as f:
            f.write(self.render() + "\n")
        return path

    def grade(self, slug):
        """Grade locally against the reference oracle. Returns dict with passed/total,
        footprint, avgTicks, score, results. Requires Node + sim/littleman.wasm."""
        with tempfile.NamedTemporaryFile("w", suffix=".man", delete=False) as f:
            f.write(self.render())
            tmp = f.name
        out = subprocess.run(
            ["node", os.path.join(REPO, "tools", "grade_json.js"), slug, tmp],
            capture_output=True, text=True)
        try:
            return json.loads(out.stdout.strip().splitlines()[-1])
        except Exception:
            return {"error": (out.stdout + out.stderr)[:2000]}


# ──────────────────────────────────────────────────────────────────────────────
# ROADMAP — toward a DSL that emits (eventually optimal) solutions:
#   1. PATTERNS layer (below): reusable named builders for recurring shapes
#      (length-prefixed read loop, Horner accumulate, int-output tail, backpack
#      countdown, display raster fill). Agents grow this.
#   2. LAYOUT layer (future): describe the man's linear instruction sequence + I/O,
#      and auto-fold it into the smallest square-ish block (boustrophedon with turn
#      glyphs, handling literals reading reversed on westward rows) and auto-route
#      the I/O pipes — minimizing max(w,h) (which is squared) and ticks.
#   3. SEARCH layer (future): given a computation, enumerate/mutate layouts and pick
#      the lowest-scoring one that grades PASS on the oracle (superoptimization).
# Score to minimize = max(w,h)^2 * avg_ticks (or just max(w,h)^2 for footprint-only).
# ──────────────────────────────────────────────────────────────────────────────

# === PATTERNS === (higher-level, reusable builders — agents: add yours here)

def demo_triangle():
    """Reference example: the n-th triangular number, T = n(n+1)/2 (score ~1053).
    Shows the common int-in/int-out shape: I room -> compute room -> O room."""
    p = Program()
    p.input_room(0, 0)               # I at cols 0-2
    p.output_room(4, 0)              # O at cols 4-6
    p.room(0, 5, 9, 4)               # compute room, interior cols 1-7 rows 6-7
    p.text(1, 6, "@rM*+Wv")          # read n, B=n, n^2, +n = n(n+1), swap, turn down
    p.text(1, 7, "H.s/W2<")          # <- walk west: 2, swap, /2, send, halt
    p.pipe([(1, 3), (1, 4)])         # input pipe: I down into compute top
    p.pipe([(5, 4), (5, 3)])         # output pipe: compute up into O
    return p


if __name__ == "__main__":
    p = demo_triangle()
    print(p.render())
    print("footprint:", p.footprint())
    print("grade:", json.dumps(p.grade("triangle")))
