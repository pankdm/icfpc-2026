"""Reusable helper for littleman pipe routing.

KEY INSIGHT that unlocked the 8x8 (score-832) triangle weave:
A pipe's FINAL cell may bend to enter the destination room from a perpendicular
side (e.g. flow east then turn `^` up into the room above it). The stock
lm.Program.pipe() derives the last cell's arrow from the previous segment, so it
can only enter a room "straight on" -- it cannot express the L-turn-into-room
that compact weaves need, and it also writes an arrow ONTO the last waypoint
(which must instead be a free cell whose *forward neighbour* is the room border).

place_pipe() fixes both: you pass the explicit list of PIPE CELLS plus the exit
direction (the way the value leaves the last cell into the destination border).
The last cell is drawn as an arrowhead in `exit_dir`, bending if needed.

Validity (checked by the oracle at load):
  * first cell's BACKWARD neighbour (cell - dir(cell0->cell1)) sits on the source
    room border;
  * last cell's FORWARD neighbour (cell + exit_dir) sits on the destination
    room border;
  * pipe length >= 2 cells.
"""

ARROW = {(1, 0): '>', (-1, 0): '<', (0, 1): 'v', (0, -1): '^'}

def place_pipe(prog, path, exit_dir):
    """Draw a pipe over the given cell path into a room in direction exit_dir.

    prog     : lm.Program
    path     : [(x,y), ...] the pipe's own cells (>=2), source-adjacent first
    exit_dir : (dx,dy) direction the value leaves path[-1] into the dest border
    """
    n = len(path)
    dirs = [(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
            for i in range(n - 1)]
    dirs.append(exit_dir)                      # last cell bends toward the room
    for i, (cx, cy) in enumerate(path):
        di = dirs[i]
        bend = i > 0 and dirs[i - 1] != di
        if i == 0 or i == n - 1 or bend:
            prog.put(cx, cy, ARROW[di])
        else:
            prog.put(cx, cy, '-' if di[0] != 0 else '|')
    return prog
