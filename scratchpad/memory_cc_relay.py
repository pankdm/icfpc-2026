#!/usr/bin/env python3
"""Replace memory-cc231070's I room with a man-driven relay for reuse testing."""

from pathlib import Path


SOURCE = Path("/Users/dmitrykorolev/Downloads/memory-cc231070.man")
OUTPUT = Path("/tmp/memory-cc231070-relay.man")


def put(grid, x, y, text):
    while len(grid) <= y:
        grid.append([" "] * 24)
    if len(grid[y]) < x + len(text):
        grid[y].extend(" " * (x + len(text) - len(grid[y])))
    grid[y][x:x + len(text)] = text


def main():
    grid = [list(row.ljust(24)) for row in SOURCE.read_text().splitlines()]

    # Remove the original 3x3 I room, retaining the existing pipe from (1,20)
    # into the memory's request room.
    for y in range(21, 24):
        put(grid, 0, y, "   ")

    # A one-man forwarding loop. Its outgoing pipe climbs from the top wall and
    # joins the original two-cell request pipe; a fresh I room feeds its bottom.
    put(grid, 0, 24, "+------+")
    put(grid, 0, 25, "|@>rsv |")
    put(grid, 0, 26, "|  ^ < |")
    put(grid, 0, 27, "+--+---+")
    put(grid, 1, 23, "^^^")       # horizontal segment is overwritten below
    put(grid, 1, 21, "^")
    put(grid, 1, 22, "^")
    put(grid, 1, 23, "^>>^")      # westward turn from x4, then north at x1
    put(grid, 4, 23, "<")

    # Bottom-fed input: source at (3,29), destination at relay wall (3,28).
    put(grid, 3, 28, "^")
    put(grid, 2, 30, "+-+")
    put(grid, 2, 31, "|I|")
    put(grid, 2, 32, "+-+")

    OUTPUT.write_text("\n".join("".join(row).rstrip() for row in grid) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
