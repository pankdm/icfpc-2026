#!/usr/bin/env python3
"""Fold matmul-46x46.man into a 43-by-43 window.

The lower room cluster moves two columns left. Pipes wholly inside that cluster
are translated verbatim; crossing pipes are re-routed at their exact original
lengths so their capacity and latency do not change.  The upper return pipe
moves its source attachment down one cell to make an exact-length route fit.
"""

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.setrecursionlimit(200_000)

import exact_pipe_router as router  # noqa: E402
import place  # noqa: E402


SOURCE = Path(__file__).with_name("matmul-46x46.man")
OUTPUT = Path(__file__).with_name("matmul-43x43.man")
WINDOW = (0, 42, 0, 42)
BLOCK_SHIFTS = {
    3: (-3, 0),
    4: (-3, 0),
    5: (-3, 0),
    6: (-3, 0),
    7: (-1, 0),
    8: (-3, 0),
}


def shifted(point, delta):
    return point[0] + delta[0], point[1] + delta[1]


def main():
    plan = place.Plan(str(SOURCE))
    base_offsets = [tuple(offset) for offset in plan.base_layout()[0]]
    offsets = [
        shifted(offset, BLOCK_SHIFTS.get(block.idx, (0, 0)))
        for block, offset in zip(plan.blocks, base_offsets)
    ]

    occupied = set()
    for block, (ox, oy) in zip(plan.blocks, offsets):
        block_cells = block.cells(ox, oy)
        if occupied & block_cells:
            raise RuntimeError(f"moved block {block.idx} overlaps another block")
        occupied |= block_cells

    guard_cells = set()
    for block, (ox, oy) in zip(plan.blocks, offsets):
        for x, y in block.border(ox, oy):
            for ddx, ddy in router.DIRS:
                neighbor = (x + ddx, y + ddy)
                if neighbor not in occupied:
                    guard_cells.add(neighbor)

    paths = {}
    route_lengths = {}
    candidates = {}
    reroute = []
    for pipe in plan.pipes:
        src_delta = BLOCK_SHIFTS.get(pipe.src_b, (0, 0))
        dst_delta = BLOCK_SHIFTS.get(pipe.dst_b, (0, 0))
        if src_delta == dst_delta:
            candidate = [shifted(cell, src_delta) for cell in pipe.cells]
            if occupied & set(candidate):
                raise RuntimeError(f"translated pipe {pipe.idx} intersects a room")
            if all(
                WINDOW[0] <= x <= WINDOW[1]
                and WINDOW[2] <= y <= WINDOW[3]
                for x, y in candidate
            ):
                candidates[pipe.idx] = (
                    candidate,
                    1 if src_delta != (0, 0) else (3 if pipe.idx == 5 else 0),
                )
            else:
                reroute.append(pipe.idx)
        else:
            reroute.append(pipe.idx)

    # Keep unchanged pipes ahead of translated ones.  If a translated pipe
    # crosses an unchanged path, only the translated path is re-routed.
    for pipe_idx, (path, _) in sorted(
        candidates.items(), key=lambda item: (item[1][1], item[0])
    ):
        if occupied & set(path):
            reroute.append(pipe_idx)
            continue
        paths[pipe_idx] = path
        route_lengths[pipe_idx] = len(path)
        occupied |= set(path)

    free = {
        (x, y)
        for y in range(WINDOW[2], WINDOW[3] + 1)
        for x in range(WINDOW[0], WINDOW[1] + 1)
        if (x, y) not in occupied
    }

    # Short, endpoint-constrained pipes go first.  The 289-cell storage pipe
    # deliberately goes last so it absorbs whatever free space remains.
    route_priority = {4: 0, 10: 1, 0: 2, 1: 3, 11: 4}
    for pipe_idx in sorted(
        reroute,
        key=lambda idx: (route_priority.get(idx, 99), plan.pipes[idx].length),
    ):
        pipe = plan.pipes[pipe_idx]
        print(f"routing pipe {pipe.idx} at up to {pipe.length} cells")
        sx, sy = offsets[pipe.src_b]
        dx, dy = offsets[pipe.dst_b]
        src_attach = (sx + pipe.src_off[0], sy + pipe.src_off[1])
        dst_attach = (dx + pipe.dst_off[0], dy + pipe.dst_off[1])

        old_sx, old_sy = base_offsets[pipe.src_b]
        old_attach = (old_sx + pipe.src_off[0], old_sy + pipe.src_off[1])
        first_dir = (
            pipe.cells[0][0] - old_attach[0],
            pipe.cells[0][1] - old_attach[1],
        )
        last_dir = pipe.dirs[-1]
        start = (src_attach[0] + first_dir[0], src_attach[1] + first_dir[1])
        end = (dst_attach[0] - last_dir[0], dst_attach[1] - last_dir[1])
        if pipe.idx == 1:
            # Match the odd path length after shifting room 7 left.
            end = (0, 26)
        route_free = free if pipe.idx == 0 else (free - guard_cells) | {start, end}

        found = None
        if pipe.idx == 4:
            candidate = (
                [(39, 11), (39, 12)]
                + [(x, 12) for x in range(40, 43)]
                + [(42, y) for y in range(13, 37)]
                + [(x, 36) for x in range(41, 34, -1)]
                + [(35, 35)]
            )
            if (
                len(candidate) == pipe.length
                and candidate[-1] == end
                and not (set(candidate) - free)
            ):
                found = candidate
        if pipe.idx == 1:
            finish = pipe.cells.index((0, 26))
            candidate = (
                [(30, 7), (31, 7), (32, 7), (32, 6), (31, 6)]
                + list(pipe.cells[3 : finish + 1])
            )
            if (
                len(candidate) == pipe.length
                and candidate[-1] == end
                and not (set(candidate) - free)
            ):
                found = candidate
        if pipe.idx == 0:
            # The room moved an odd number of columns, so move its port one
            # row as well to preserve the path's checkerboard parity.
            end = (10, 17)
            prefix = list(pipe.cells[:167])
            tail_free = {
                cell
                for cell in route_free - set(prefix)
                if 1 <= cell[0] <= 10 and 14 <= cell[1] <= 22
            }
            tail_start = (1, 14)
            tail_free.add(tail_start)
            tail_length = pipe.length - len(prefix)
            for approach in router.DIRS:
                for departure in ((0, 1), (1, 0)):
                    for seed in range(32):
                        tail = router.route_exact(
                            tail_free,
                            tail_start,
                            departure,
                            end,
                            approach,
                            tail_length,
                            seed=seed,
                            budget=4_000_000,
                        )
                        if tail:
                            found = prefix + tail
                            break
                    if found:
                        break
                if found:
                    break
        lengths = [pipe.length]
        if pipe.idx not in {0, 11}:
            lengths.extend(range(pipe.length - 1, 1, -1))
        for length in lengths if not found else []:
            # The destination arrowhead may turn on the final pipe cell, so
            # its incoming path direction need not equal the arrow direction.
            approaches = [last_dir] + [
                direction
                for direction in router.DIRS
                if direction != last_dir
            ]
            for approach in approaches:
                for seed in range(32):
                    found = router.route_exact(
                        route_free,
                        start,
                        first_dir,
                        end,
                        approach,
                        length,
                        seed=seed,
                        budget=8_000_000 if length > 100 else 1_000_000,
                    )
                    if found:
                        break
                if found:
                    break
            if found:
                break
        if not found:
            raise RuntimeError(
                f"could not reroute pipe {pipe.idx} at exact length {pipe.length}"
            )
        paths[pipe.idx] = found
        route_lengths[pipe.idx] = len(found)
        free -= set(found)

    original_paths = plan.pipe_paths_original()
    final_directions = {}
    for pipe in plan.pipes:
        path = paths[pipe.idx]
        original_paths[pipe.idx] = (
            path,
            router.dirs_of(path, final_directions.get(pipe.idx, pipe.dirs[-1])),
        )

    rendered = place.render(place.trimmed(plan.draw(offsets, original_paths)))
    OUTPUT.write_text(rendered)
    width = max(map(len, rendered.splitlines()))
    height = len(rendered.splitlines())
    print(f"wrote {OUTPUT}: {width}x{height}, box {max(width, height) ** 2}")
    print(
        "pipe lengths:",
        ", ".join(
            f"{pipe.idx}:{pipe.length}->{route_lengths[pipe.idx]}"
            for pipe in plan.pipes
            if route_lengths[pipe.idx] != pipe.length
        )
        or "unchanged",
    )


if __name__ == "__main__":
    main()
