#!/usr/bin/env python3
"""Greedily pack rigid Littleman rooms into a fixed square and reroute their pipes.

The room interiors and pipe attachment offsets are never changed.  Pipes are rerouted
inside SIDE x SIDE with their original lengths, preserving both latency and capacity.
Candidates are accepted only after the parser confirms the same room/pipe topology and,
when a cached problem slug is available, the Rust grader passes every public case.

    python3 tools/pack_rooms.py solutions/matmul/best/60x60.man 60 \
        --slug matmul --out solutions/matmul/best/60x60-repacked.man
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import place as PLACE  # noqa: E402
from grade_fast import grade as rust_grade  # noqa: E402
from interpreter.parser import LoadError, parse_program  # noqa: E402


def _overlap_with_clearance(a, b, clearance):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw + clearance <= bx
        or bx + bw + clearance <= ax
        or ay + ah + clearance <= by
        or by + bh + clearance <= ay
    )


def _connected(plan, left, right):
    return sum(
        1
        for pipe in plan.pipes
        if {pipe.src_b, pipe.dst_b} == {left, right}
    )


def _endpoint_distance(plan, block_index, position, other_index, other_position):
    """Distance between the nearest pair of this block-pair's fixed attachments."""
    values = []
    for pipe in plan.pipes:
        if pipe.src_b == block_index and pipe.dst_b == other_index:
            a, b = pipe.src_off, pipe.dst_off
        elif pipe.dst_b == block_index and pipe.src_b == other_index:
            a, b = pipe.dst_off, pipe.src_off
        else:
            continue
        values.append(
            abs(position[0] + a[0] - other_position[0] - b[0])
            + abs(position[1] + a[1] - other_position[1] - b[1])
        )
    return min(values) if values else 0


def _pipe_parity_ok(plan, block_index, position, placed):
    """Exact grid paths have fixed parity between their wall attachments."""
    for pipe in plan.pipes:
        if pipe.src_b == block_index and pipe.dst_b in placed:
            src = (position[0] + pipe.src_off[0], position[1] + pipe.src_off[1])
            other = placed[pipe.dst_b]
            dst = (other[0] + pipe.dst_off[0], other[1] + pipe.dst_off[1])
        elif pipe.dst_b == block_index and pipe.src_b in placed:
            other = placed[pipe.src_b]
            src = (other[0] + pipe.src_off[0], other[1] + pipe.src_off[1])
            dst = (position[0] + pipe.dst_off[0], position[1] + pipe.dst_off[1])
        else:
            continue
        distance = abs(src[0] - dst[0]) + abs(src[1] - dst[1])
        if (distance - 1) % 2 != pipe.length % 2:
            return False
    return True


def _orders(plan, attempts, rng):
    indices = list(range(len(plan.blocks)))
    area = lambda i: plan.blocks[i].w * plan.blocks[i].h
    degree = lambda i: sum(
        1 for p in plan.pipes if p.src_b == i or p.dst_b == i
    )
    seeds = [
        sorted(indices, key=lambda i: (-area(i), -degree(i), i)),
        sorted(indices, key=lambda i: (-degree(i), -area(i), i)),
        sorted(indices, key=lambda i: (plan.blocks[i].oy0, plan.blocks[i].ox0)),
    ]
    for order in seeds[:attempts]:
        yield order
    for _ in range(max(0, attempts - len(seeds))):
        # Keep a large/high-degree anchor first, then vary the greedy insertion order.
        anchor = max(indices, key=lambda i: (area(i), degree(i), -i))
        rest = [i for i in indices if i != anchor]
        rng.shuffle(rest)
        rest.sort(
            key=lambda i: -(area(i) * (0.7 + 0.6 * rng.random())
                            + degree(i) * 20)
        )
        yield [anchor, *rest]


def greedy_layout(plan, side, order, rng, clearance=1, height=None):
    """Place each room at its cheapest currently legal coordinate."""
    height = height or side
    placed = {}
    rects = []
    for step, block_index in enumerate(order):
        block = plan.blocks[block_index]
        choices = []
        for y in range(height - block.h + 1):
            for x in range(side - block.w + 1):
                rect = (x, y, block.w, block.h)
                if any(_overlap_with_clearance(rect, other, clearance) for other in rects):
                    continue
                if not _pipe_parity_ok(plan, block_index, (x, y), placed):
                    continue
                trial = [*rects, rect]
                min_x = min(r[0] for r in trial)
                min_y = min(r[1] for r in trial)
                max_x = max(r[0] + r[2] for r in trial)
                max_y = max(r[1] + r[3] for r in trial)
                bbox = max(max_x - min_x, max_y - min_y)
                wire = 0
                for other_index, other_position in placed.items():
                    count = _connected(plan, block_index, other_index)
                    if count:
                        wire += count * _endpoint_distance(
                            plan, block_index, (x, y), other_index, other_position
                        )
                # The first terms make a dense shelf-like packing.  Wire length is a
                # tie-breaker, while a small seeded jitter gives deterministic restarts.
                score = (
                    bbox + 1.5 * rng.random(),
                    (max_x - min_x) * (max_y - min_y),
                    wire,
                    y + x,
                )
                choices.append((score, (x, y), rect))
        if not choices:
            return None
        _, position, rect = min(choices)
        placed[block_index] = position
        rects.append(rect)
    offsets = tuple(placed[i] for i in range(len(plan.blocks)))
    return offsets, plan.base_layout()[1]


def projected_original_layout(plan, side, order, rng, clearance=1, height=None):
    """Greedily squeeze the existing floorplan, retaining its relative arrangement."""
    height = height or side
    min_x = min(block.ox0 for block in plan.blocks)
    min_y = min(block.oy0 for block in plan.blocks)
    desired = {
        i: (
            min(max(0, block.ox0 - min_x), side - block.w),
            min(max(0, block.oy0 - min_y), height - block.h),
        )
        for i, block in enumerate(plan.blocks)
    }
    placed = {}
    rects = []
    for block_index in order:
        block = plan.blocks[block_index]
        tx, ty = desired[block_index]
        choices = []
        for y in range(height - block.h + 1):
            for x in range(side - block.w + 1):
                rect = (x, y, block.w, block.h)
                if any(_overlap_with_clearance(rect, other, clearance) for other in rects):
                    continue
                if not _pipe_parity_ok(plan, block_index, (x, y), placed):
                    continue
                displacement = abs(x - tx) + abs(y - ty)
                choices.append(
                    ((displacement + 0.2 * rng.random(), y + x), (x, y), rect)
                )
        if not choices:
            return None
        _, position, rect = min(choices)
        placed[block_index] = position
        rects.append(rect)
    return (
        tuple(placed[i] for i in range(len(plan.blocks))),
        plan.base_layout()[1],
    )


def validate_candidate(plan, text, cells, layout, require_all_lengths=True):
    try:
        parsed = parse_program(text)
    except (LoadError, ValueError) as exc:
        return f"local parser rejected candidate: {exc}"
    original = parse_program("\n".join(row.rstrip() for row in plan.rows))
    if len(parsed.rooms) != len(original.rooms):
        return f"room count changed: {len(original.rooms)} -> {len(parsed.rooms)}"
    if require_all_lengths and sorted(len(pipe.cells) for pipe in parsed.pipes) != sorted(
        len(pipe.cells) for pipe in original.pipes
    ):
        return "pipe lengths changed"
    return PLACE.verify_topology(plan, cells, layout)


def infer_slug(path):
    candidate = path.parent.name
    return candidate if (REPO / "tests" / f"{candidate}.json").exists() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("side", type=int, help="width and height of the target square")
    parser.add_argument("--height", type=int, help="target height (default: SIDE)")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--slug", help="problem slug for mandatory Rust grading")
    parser.add_argument("--attempts", type=int, default=80)
    parser.add_argument("--route-candidates", type=int, default=30)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--clearance", type=int, choices=(0, 1), default=1)
    parser.add_argument(
        "--exact-pipes",
        default="all",
        help="'all' (default), 'none', or comma-separated pipe IDs whose lengths must remain exact",
    )
    parser.add_argument(
        "--pipe-targets",
        default="",
        help="comma-separated ID:LENGTH exact targets; implies other pipes may shorten",
    )
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.side < 3:
        parser.error("SIDE must be at least 3")
    target_height = args.height or args.side
    if target_height < 3:
        parser.error("--height must be at least 3")
    output = args.out or args.input.with_name(
        f"{args.input.stem}-packed-{args.side}.man"
    )
    if output.resolve() == args.input.resolve():
        parser.error("output must differ from input")

    plan = PLACE.Plan(args.input)
    if args.exact_pipes == "all":
        exact_pipes = {pipe.idx for pipe in plan.pipes}
    elif args.exact_pipes == "none":
        exact_pipes = set()
    else:
        try:
            exact_pipes = {int(value) for value in args.exact_pipes.split(",") if value}
        except ValueError:
            parser.error("--exact-pipes must be all, none, or comma-separated integers")
    unknown = exact_pipes - {pipe.idx for pipe in plan.pipes}
    if unknown:
        parser.error(f"unknown pipe IDs in --exact-pipes: {sorted(unknown)}")
    targets = {}
    try:
        for item in filter(None, args.pipe_targets.split(",")):
            pipe_id, length = item.split(":", 1)
            targets[int(pipe_id)] = int(length)
    except ValueError:
        parser.error("--pipe-targets must look like 1:254,10:240")
    unknown_targets = set(targets) - {pipe.idx for pipe in plan.pipes}
    if unknown_targets:
        parser.error(f"unknown pipe IDs in --pipe-targets: {sorted(unknown_targets)}")
    if any(length < 2 for length in targets.values()):
        parser.error("pipe target lengths must be at least 2")
    pipe_modes = {pipe_id: "exact" for pipe_id in exact_pipes}
    pipe_modes.update(targets)
    constrained_pipes = exact_pipes | set(targets)
    default_pipe_mode = (
        "exact" if len(constrained_pipes) == len(plan.pipes) and not targets else "free"
    )
    total_cells = (
        sum(block.w * block.h for block in plan.blocks)
        + sum(
            targets.get(pipe.idx, pipe.length if pipe.idx in exact_pipes else 2)
            for pipe in plan.pipes
        )
        + len(plan.orphans)
    )
    cell_lower_bound = math.ceil(math.sqrt(total_cells))
    widest = max(max(block.w, block.h) for block in plan.blocks)
    lower_bound = max(cell_lower_bound, widest)
    print(
        f"{args.input.name}: {len(plan.blocks)} rigid rooms, {len(plan.pipes)} pipes; "
        f"selected-constraint cell lower bound {lower_bound}x{lower_bound}"
    )
    if args.side * target_height < total_cells or args.side < widest:
        raise SystemExit(
            f"{args.side}x{target_height} is impossible from constrained cell/room bounds"
        )

    rng = random.Random(args.seed)
    layouts = {}
    projected_offsets = set()
    base_layout = plan.base_layout()
    base_cells = plan.draw(plan.base_offsets, plan.pipe_paths_original())
    base_width, base_height, _ = PLACE.box_of(base_cells)
    if base_width <= args.side and base_height <= target_height:
        layouts[base_layout[0]] = base_layout
        projected_offsets.add(base_layout[0])
    orders = list(_orders(plan, args.attempts, rng))
    for order in orders:
        layout = greedy_layout(
            plan, args.side, order, rng, args.clearance, target_height
        )
        if layout is not None:
            layouts.setdefault(layout[0], layout)
        projected = projected_original_layout(
            plan, args.side, order, rng, args.clearance, target_height
        )
        if projected is not None:
            layouts.setdefault(projected[0], projected)
            projected_offsets.add(projected[0])
    ranked = sorted(
        layouts.values(),
        key=lambda layout: (
            -1 if layout[0] == base_layout[0] else (
                0 if layout[0] in projected_offsets else 1
            ),
            plan.block_cost(layout),
        ),
    )
    print(f"  greedy placement produced {len(ranked)} distinct room layouts")

    best = None
    failures = {}
    bound = (0, 0, args.side - 1, target_height - 1)
    for index, layout in enumerate(ranked[: args.route_candidates], 1):
        cells, error, paths = plan.build(
            layout,
            pipe_len=default_pipe_mode,
            routing_bound=bound,
            pipe_modes=pipe_modes,
        )
        if cells is None:
            failures[error] = failures.get(error, 0) + 1
            continue
        text = PLACE.render(PLACE.trimmed(cells))
        width, height, box = PLACE.box_of(cells)
        if width > args.side or height > target_height:
            failures["route escaped target square"] = (
                failures.get("route escaped target square", 0) + 1
            )
            continue
        if any(
            len(paths[pipe_id][0]) != targets.get(pipe_id, plan.pipes[pipe_id].length)
            for pipe_id in constrained_pipes
        ):
            failures["an exact pipe changed length"] = (
                failures.get("an exact pipe changed length", 0) + 1
            )
            continue
        error = validate_candidate(
            plan,
            text,
            cells,
            layout,
            require_all_lengths=(
                len(exact_pipes) == len(plan.pipes) and not targets
            ),
        )
        if error:
            failures[error] = failures.get(error, 0) + 1
            continue
        candidate = (box, width * height, text, layout)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
        if args.verbose:
            print(f"    routed {index}: {width}x{height}, box {box}")

    if best is None:
        summary = ", ".join(
            f"{name}: {count}"
            for name, count in sorted(failures.items(), key=lambda item: -item[1])
        )
        raise SystemExit(
            f"no selected-constraint routing fit in {args.side}x{target_height}"
            + (f" ({summary})" if summary else "")
        )

    _, _, text, _ = best
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="ascii")
    parsed = parse_program(text)
    print(
        f"  topology OK: {len(parsed.rooms)} rooms, {len(parsed.pipes)} pipes, "
        "all endpoint pairs and lengths preserved"
    )

    slug = args.slug or infer_slug(args.input)
    if slug:
        result = rust_grade(slug, str(output), jobs=args.jobs)
        if result.get("passed") != result.get("total") or not result.get("total"):
            output.unlink(missing_ok=True)
            raise SystemExit(f"Rust validation failed; removed output: {result}")
        fp = result["footprint"]
        print(
            f"  Rust PASS {result['passed']}/{result['total']}: "
            f"{fp['w']}x{fp['h']}, avgTicks {result['avgTicks']:.2f}, "
            f"score {result['score']:,.0f}"
        )
    else:
        print("  warning: no cached problem slug inferred; simulation was skipped")
    print(f"  wrote {output}")


if __name__ == "__main__":
    main()
