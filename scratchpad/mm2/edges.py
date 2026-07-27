"""Which cells define each of the four box edges, and how many rows/cols are nearly
empty?  Prints, per extreme row/column, the occupied cells so a rigid move can be
targeted at the ONE thing holding the edge out."""
import sys

path = sys.argv[1]
rows = [r.rstrip('\n') for r in open(path)]
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
h = len(rows)
print(f"{path}: {w}x{h}")

n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
for x in list(range(n)) + list(range(w - n, w)):
    cells = [(y, rows[y][x]) for y in range(h) if rows[y][x] != ' ']
    print(f"col {x:2d}  {len(cells):3d} cells  " + ' '.join(f"{y}{c}" for y, c in cells[:22]))
print()
for y in list(range(n)) + list(range(h - n, h)):
    cells = [(x, rows[y][x]) for x in range(w) if rows[y][x] != ' ']
    print(f"row {y:2d}  {len(cells):3d} cells  " + ' '.join(f"{x}{c}" for x, c in cells[:22]))
print()
sparse = [(y, sum(1 for x in range(w) if rows[y][x] != ' ')) for y in range(h)]
print("rows with <6 cells:", [(y, c) for y, c in sparse if c < 6])
sparsec = [(x, sum(1 for y in range(h) if rows[y][x] != ' ')) for x in range(w)]
print("cols with <6 cells:", [(x, c) for x, c in sparsec if c < 6])
