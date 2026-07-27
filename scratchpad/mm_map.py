"""Coarse occupancy map of a .man: rooms as letters, pipes as '#', free as '.'.

Usage: python3 scratchpad/mm_map.py <file.man> [--rows y0:y1] [--cols x0:x1]
"""
import sys

path = sys.argv[1]
rows = open(path).read().rstrip('\n').split('\n')
w = max(len(r) for r in rows)
rows = [r.ljust(w) for r in rows]
h = len(rows)

# flood rooms from '+' corners: a room is a rectangle of +-| walls
occ = [[rows[y][x] != ' ' for x in range(w)] for y in range(h)]

# find room rectangles: scan for '+' that starts a wall run right and down
rooms = []
for y in range(h):
    for x in range(w):
        if rows[y][x] != '+':
            continue
        # extend right along '-'
        x2 = x + 1
        while x2 < w and rows[y][x2] == '-':
            x2 += 1
        if x2 >= w or rows[y][x2] != '+':
            continue
        y2 = y + 1
        while y2 < h and rows[y2][x] == '|':
            y2 += 1
        if y2 >= h or rows[y2][x] != '+':
            continue
        if rows[y2][x2] != '+':
            continue
        rooms.append((x, y, x2, y2))
rooms = [r for r in rooms if not any(
    o is not r and o[0] <= r[0] and o[1] <= r[1] and o[2] >= r[2] and o[3] >= r[3]
    for o in rooms)]
rooms.sort(key=lambda r: (r[1], r[0]))

lab = [['.' for _ in range(w)] for _ in range(h)]
for y in range(h):
    for x in range(w):
        if occ[y][x]:
            lab[y][x] = '#'
letters = 'ABCDEFGHIJKLMNOP'
for i, (x0, y0, x1, y1) in enumerate(rooms):
    ch = letters[i]
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            lab[y][x] = ch

y0, y1, x0, x1 = 0, h, 0, w
for a in sys.argv[2:]:
    if a.startswith('--rows'):
        y0, y1 = [int(v) for v in a.split('=')[1].split(':')]
    if a.startswith('--cols'):
        x0, x1 = [int(v) for v in a.split('=')[1].split(':')]

print(f"{w}x{h} rooms:")
for i, r in enumerate(rooms):
    print(f"  {letters[i]} ({r[0]},{r[1]})-({r[2]},{r[3]})  "
          f"{r[2]-r[0]+1}x{r[3]-r[1]+1}")
print('    ' + ''.join(str(x // 10 % 10) for x in range(x0, x1)))
print('    ' + ''.join(str(x % 10) for x in range(x0, x1)))
for y in range(y0, y1):
    print(f"{y:3d} " + ''.join(lab[y][x0:x1]))
