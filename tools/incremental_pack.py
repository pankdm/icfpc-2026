#!/usr/bin/env python3
"""Incrementally compact a Littleman floorplan with passing checkpoints.

Each iteration tries small rigid-room moves and one-cell shears.  Room contents,
pipe connections, attachment offsets, and exact pipe lengths remain unchanged.
A candidate must improve the geometric objective, preserve parsed topology, and
pass every cached public case in the Rust simulator before it becomes the next
version in WORK_DIR.

The process is resumable: rerunning the same command continues from the newest
``vNNN-*.man`` file in the working directory.

    python3 tools/incremental_pack.py matmul \
        solutions/matmul/best/60x60.man \
        --target 50 --work-dir solutions/matmul/packing-50
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import place as PLACE  # noqa: E402
from grade_fast import grade as rust_grade  # noqa: E402


VERSION_RE = re.compile(r"^v(\d+)-.*\.man$")
DIRS = ((-1, 0), (0, -1), (1, 0), (0, 1))


def version_of(path):
    match = VERSION_RE.match(path.name)
    return int(match.group(1)) if match else -1


def existing_versions(work_dir):
    return sorted(
        (path for path in work_dir.glob("v*-*.man") if version_of(path) >= 0),
        key=version_of,
    )


def geometry(cells, offsets):
    min_x = min(x for x, _ in cells)
    min_y = min(y for _, y in cells)
    width, height, box = PLACE.box_of(cells)
    # The final term makes equal-footprint progress deterministic: pull room
    # origins toward the top-left of the current non-space bounding box.
    top_left_mass = sum(
        (x - min_x) + (y - min_y)
        for x, y in offsets
    )
    glyph_mass = sum(
        (x - min_x) + (y - min_y)
        for x, y in cells
    )
    return (
        box,
        width * height,
        max(width, height),
        width + height,
        top_left_mass,
        glyph_mass,
    )


def geometry_label(value):
    box, area, side, perimeter, mass, glyph_mass = value
    # width/height are printed separately by the caller; retain useful tie-breakers.
    return (
        f"box={box} area={area} side={side} span={perimeter} "
        f"roomMass={mass} glyphMass={glyph_mass}"
    )


def parity_ok(plan, offsets):
    """An exact pipe path must retain its endpoint-distance parity."""
    for pipe in plan.pipes:
        src = plan.endpoint(offsets, pipe.src_b, pipe.src_off)
        dst = plan.endpoint(offsets, pipe.dst_b, pipe.dst_off)
        distance = abs(src[0] - dst[0]) + abs(src[1] - dst[1])
        if (distance - 1) % 2 != pipe.length % 2:
            return False
    return True


def inside(offsets, blocks, side):
    return all(
        0 <= x
        and 0 <= y
        and x + block.w <= side
        and y + block.h <= side
        for block, (x, y) in zip(blocks, offsets)
    )


def mutations(plan, max_step):
    """Yield deterministic local moves, then compacting group shears."""
    base, attachments = plan.base_layout()
    seen = {base}

    # One rigid room at a time. Left/up are considered first; right/down can
    # unlock a later shear while the strictly improving objective prevents drift.
    for step in range(1, max_step + 1):
        for block_index in range(len(plan.blocks)):
            for dx, dy in DIRS:
                offsets = list(base)
                x, y = offsets[block_index]
                offsets[block_index] = (x + dx * step, y + dy * step)
                value = tuple(offsets)
                if value not in seen:
                    seen.add(value)
                    yield value, attachments, f"room {block_index} ({dx * step:+d},{dy * step:+d})"

    # Translate everything on one side of a cut. These moves close a whole
    # horizontal/vertical gap that no single-room move can improve.
    xs = sorted({x for x, _ in base})
    ys = sorted({y for _, y in base})
    for step in range(1, max_step + 1):
        for cut in xs[1:]:
            value = tuple(
                (x - step if x >= cut else x, y)
                for x, y in base
            )
            if value not in seen:
                seen.add(value)
                yield value, attachments, f"x-shear >= {cut} by {-step}"
        for cut in ys[1:]:
            value = tuple(
                (x, y - step if y >= cut else y)
                for x, y in base
            )
            if value not in seen:
                seen.add(value)
                yield value, attachments, f"y-shear >= {cut} by {-step}"


def topology_ok(plan, cells, layout):
    error = PLACE.verify_topology(plan, cells, layout)
    return error is None, error


def write_manifest(work_dir, record):
    with (work_dir / "history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("input", type=Path)
    parser.add_argument("--target", type=int, default=50)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--max-step", type=int, default=3)
    parser.add_argument(
        "--allow-shorter",
        action="store_true",
        help="also try shorter reroutes; simulator passes are the safety gate",
    )
    parser.add_argument(
        "--grade-candidates",
        type=int,
        default=12,
        help="maximum structurally valid improvements simulated per iteration",
    )
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument(
        "--cap",
        type=int,
        help="per-case simulator cap; use a measured tight cap to reject deadlocks quickly",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.target < 3:
        parser.error("--target must be at least 3")
    work_dir = args.work_dir or args.input.with_name(f"{args.input.stem}-packing")
    work_dir.mkdir(parents=True, exist_ok=True)

    versions = existing_versions(work_dir)
    if versions:
        current = versions[-1]
        version = version_of(current)
        print(f"resuming from {current}")
    else:
        baseline = rust_grade(args.slug, str(args.input), cap=args.cap, jobs=args.jobs)
        if baseline.get("passed") != baseline.get("total") or not baseline.get("total"):
            raise SystemExit(f"baseline does not pass every public case: {baseline}")
        fp = baseline["footprint"]
        current = work_dir / f"v000-{fp['w']}x{fp['h']}.man"
        current.write_text(args.input.read_text(encoding="ascii"), encoding="ascii")
        version = 0
        write_manifest(
            work_dir,
            {
                "version": version,
                "file": current.name,
                "source": str(args.input),
                "footprint": fp,
                "avgTicks": baseline["avgTicks"],
                "score": baseline["score"],
                "move": "baseline",
            },
        )
        print(
            f"baseline PASS {baseline['passed']}/{baseline['total']}: "
            f"{fp['w']}x{fp['h']} -> {current}"
        )

    for iteration in range(args.max_iterations):
        plan = PLACE.Plan(current)
        base_layout = plan.base_layout()
        base_cells = plan.draw(plan.base_offsets, plan.pipe_paths_original())
        base_objective = geometry(base_cells, base_layout[0])
        width, height, _ = PLACE.box_of(base_cells)
        if width <= args.target and height <= args.target:
            print(f"target reached at {current}: {width}x{height}")
            return

        # Never let a route grow beyond the current square. The boundary shrinks
        # naturally after an accepted move reduces the maximum dimension.
        current_side = max(width, height)
        routing_bound = (0, 0, current_side - 1, current_side - 1)
        candidates = []
        failures = {}
        for offsets, attachments, description in mutations(plan, args.max_step):
            if not inside(offsets, plan.blocks, current_side):
                continue
            if not plan.blocks_disjoint(offsets) or not parity_ok(plan, offsets):
                continue
            layout = (offsets, attachments)
            cells, error, _ = plan.build(
                layout,
                pipe_len="exact",
                routing_bound=routing_bound,
            )
            if cells is None:
                failures[error] = failures.get(error, 0) + 1
                continue
            objective = geometry(cells, offsets)
            if objective >= base_objective:
                continue
            ok, error = topology_ok(plan, cells, layout)
            if not ok:
                failures[error] = failures.get(error, 0) + 1
                continue
            candidates.append((objective, description, cells))
            if args.allow_shorter:
                cells, error, _ = plan.build(
                    layout,
                    pipe_len="free",
                    routing_bound=routing_bound,
                )
                if cells is None:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                objective = geometry(cells, offsets)
                if objective >= base_objective:
                    continue
                ok, error = topology_ok(plan, cells, layout)
                if not ok:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                candidates.append(
                    (objective, f"{description}; shorten moved pipes", cells)
                )

        # Some moves are impossible only because the old channel is longer than
        # the newly available corridor. Retry the complete neighborhood without
        # a length floor; public-case simulation decides whether that capacity or
        # delay was semantically required.
        if args.allow_shorter:
            for offsets, attachments, description in mutations(plan, args.max_step):
                if not inside(offsets, plan.blocks, current_side):
                    continue
                if not plan.blocks_disjoint(offsets):
                    continue
                layout = (offsets, attachments)
                cells, error, _ = plan.build(
                    layout,
                    pipe_len="free",
                    routing_bound=routing_bound,
                )
                if cells is None:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                objective = geometry(cells, offsets)
                if objective >= base_objective:
                    continue
                ok, error = topology_ok(plan, cells, layout)
                if not ok:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                candidates.append(
                    (objective, f"{description}; shorten moved pipes", cells)
                )

        # The box may be driven by a long pipe rather than a room. Force exactly
        # one pipe to find a new path of the same length while every other route
        # remains reusable. Accepted pipe moves often unlock the next room shear.
        for pipe in plan.pipes:
            cells, error, _ = plan.build(
                base_layout,
                pipe_len="exact",
                routing_bound=routing_bound,
                force_reroute={pipe.idx},
            )
            if cells is None:
                failures[error] = failures.get(error, 0) + 1
                continue
            objective = geometry(cells, base_layout[0])
            if objective >= base_objective:
                continue
            ok, error = topology_ok(plan, cells, base_layout)
            if not ok:
                failures[error] = failures.get(error, 0) + 1
                continue
            candidates.append(
                (objective, f"reroute pipe {pipe.idx} at length {pipe.length}", cells)
            )
            if args.allow_shorter:
                cells, error, paths = plan.build(
                    base_layout,
                    pipe_len="free",
                    routing_bound=routing_bound,
                    force_reroute={pipe.idx},
                )
                if cells is None:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                objective = geometry(cells, base_layout[0])
                if objective >= base_objective:
                    continue
                ok, error = topology_ok(plan, cells, base_layout)
                if not ok:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                new_length = len(paths[pipe.idx][0])
                candidates.append(
                    (
                        objective,
                        f"shorten pipe {pipe.idx}: {pipe.length}->{new_length}",
                        cells,
                    )
                )

        if args.allow_shorter:
            for pipe in plan.pipes:
                cells, error, paths = plan.build(
                    base_layout,
                    pipe_len="free",
                    routing_bound=routing_bound,
                    force_reroute={pipe.idx},
                )
                if cells is None:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                objective = geometry(cells, base_layout[0])
                if objective >= base_objective:
                    continue
                ok, error = topology_ok(plan, cells, base_layout)
                if not ok:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                new_length = len(paths[pipe.idx][0])
                candidates.append(
                    (
                        objective,
                        f"shorten pipe {pipe.idx}: {pipe.length}->{new_length}",
                        cells,
                    )
                )

        # At a one-pipe local optimum, let a pair negotiate together. This is
        # intentionally deferred because it is more expensive and most useful
        # only after the cheap micro-moves are exhausted.
        if not candidates:
            for first, second in itertools.combinations(plan.pipes, 2):
                forced = {first.idx, second.idx}
                cells, error, _ = plan.build(
                    base_layout,
                    pipe_len="exact",
                    routing_bound=routing_bound,
                    force_reroute=forced,
                )
                if cells is None:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                objective = geometry(cells, base_layout[0])
                if objective >= base_objective:
                    continue
                ok, error = topology_ok(plan, cells, base_layout)
                if not ok:
                    failures[error] = failures.get(error, 0) + 1
                    continue
                candidates.append(
                    (
                        objective,
                        f"reroute pipes {first.idx}+{second.idx} at exact lengths",
                        cells,
                    )
                )

        candidates.sort(key=lambda item: item[0])
        if args.verbose:
            print(
                f"iteration {iteration + 1}: {len(candidates)} structural improvements; "
                f"failures={sorted(failures.items(), key=lambda item: -item[1])[:5]}"
            )
        accepted = None
        for objective, description, cells in candidates[: args.grade_candidates]:
            temporary = work_dir / ".candidate.man"
            temporary.write_text(
                PLACE.render(PLACE.trimmed(cells)),
                encoding="ascii",
            )
            result = rust_grade(
                args.slug,
                str(temporary),
                cap=args.cap,
                jobs=args.jobs,
            )
            if result.get("passed") == result.get("total") and result.get("total"):
                accepted = (objective, description, temporary, result)
                break
            if args.verbose:
                print(f"  rejected by tests: {description}: {result.get('passed')}/{result.get('total')}")
        if accepted is None:
            (work_dir / ".candidate.man").unlink(missing_ok=True)
            print(
                f"stopped at {current}: no smaller/top-left local move passed "
                f"({geometry_label(base_objective)})"
            )
            return

        objective, description, temporary, result = accepted
        version += 1
        fp = result["footprint"]
        destination = work_dir / f"v{version:03d}-{fp['w']}x{fp['h']}.man"
        temporary.replace(destination)
        write_manifest(
            work_dir,
            {
                "version": version,
                "file": destination.name,
                "parent": current.name,
                "move": description,
                "objective": objective,
                "footprint": fp,
                "avgTicks": result["avgTicks"],
                "score": result["score"],
            },
        )
        print(
            f"v{version:03d} PASS {result['passed']}/{result['total']}: "
            f"{description}; {width}x{height} -> {fp['w']}x{fp['h']}; "
            f"score {result['score']:,.0f}"
        )
        current = destination

    print(f"iteration limit reached; latest passing version: {current}")


if __name__ == "__main__":
    main()
