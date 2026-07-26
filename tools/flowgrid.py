"""Reusable straight-line/CFG compiler for generated littleman controllers.

The compiler deliberately spends area to make control-flow routing predictable:
each source edge gets its own vertical highway and its own horizontal channel,
while each target block gets a dedicated return lane.  Those routes can cross
without sharing a turn glyph, which avoids a common source of generated-grid
misroutes.

The layout combines the repo's labeled-block style (used by tcp/plotter
generators) with explicit crossing-safe routing.  Problem-specific subclasses
can add macros that expand to ordinary instruction tokens and named pipe ports.
"""


def const_ops(n, limit=2048):
    """Return ops that load a small non-negative integer without a literal."""
    assert 0 <= n < limit
    if n < 10:
        return [str(n)]
    bits = bin(n)[2:]
    out = [bits[0]]
    for bit in bits[1:]:
        out += ["M", "+"]
        if bit == "1":
            out += ["M", "1", "+"]
    return out


class Flow:
    """Ordered basic blocks containing ops, jumps, branches, and named ports."""

    def __init__(self):
        self.blocks = {}
        self.cur = None

    def at(self, label):
        assert label not in self.blocks
        self.cur = []
        self.blocks[label] = self.cur
        return self

    def e(self, *tokens):
        assert self.cur is not None
        self.cur.extend(tokens)
        return self

    def const(self, n):
        return self.e(*const_ops(n))

    def go(self, label):
        return self.e(("go", label))

    def br(self, positive, zero, negative):
        return self.e(("br", positive, zero, negative))


def lay_cfg_controller(
    program,
    flow,
    pipe_columns,
    code_x=300,
    x0=0,
    y0=0,
    local_edges=False,
    direct_edges=False,
    pooled_edges=False,
    tight_gaps=False,
    dedup_edges=False,
    coalesce_targets=False,
    merge_pad=None,
    block_gap=None,
    boustrophedon=False,
):
    """Lay out *flow* and return its bounds and named external pipe ports.

    ``pipe_columns`` maps each symbolic token to ``(x_offset, glyph)`` where the
    offset is relative to the code column.  All ports leave the controller at
    its bottom edge.  The returned mapping contains ``ports``, ``heads``,
    ``width``, ``height``, ``bottom``, and ``code_x``.
    """
    code = x0 + code_x
    cols = {name: code + spec[0] for name, spec in pipe_columns.items()}
    glyphs = {name: spec[1] for name, spec in pipe_columns.items()}
    zones = {
        name: (
            code + spec[2] if len(spec) >= 4 else None,
            code + spec[3] if len(spec) >= 4 else None,
        )
        for name, spec in pipe_columns.items()
    }
    heads, pending = {}, []
    incoming = {label: 0 for label in flow.blocks}
    if direct_edges or pooled_edges:
        for tokens in flow.blocks.values():
            if tokens and isinstance(tokens[-1], tuple):
                targets = tokens[-1][1:]
                if pooled_edges and dedup_edges:
                    targets = tuple(dict.fromkeys(targets))
                for target in targets:
                    if coalesce_targets and pooled_edges:
                        incoming[target] = 1
                    else:
                        incoming[target] += 1
    y = y0 + 3

    def put(x, yy, ch):
        cur = program.get(x, yy)
        assert cur in (" ", ch), (x, yy, cur, ch)
        program.put(x, yy, ch)

    for block_index, (label, tokens) in enumerate(flow.blocks.items()):
        if direct_edges or pooled_edges:
            # One private merge row per incoming edge. Keeping all merges in
            # the blank band immediately above the target allows every route
            # to turn directly into the target lane instead of detouring via
            # a channel below the entire controller.
            pad = merge_pad if merge_pad is not None else (1 if tight_gaps else 2)
            y += incoming[label] + pad
        heads[label] = y
        put(code, y, "@" if block_index == 0 else ">")
        x = code + 1
        heading = 1
        for token in tokens:
            if isinstance(token, tuple):
                if token[0] == "go":
                    pending.append(("go", (x, y), token[1:], block_index))
                    break
                if token[0] == "br":
                    put(x, y, "v")
                    put(x, y + 1, "X")
                    pending.append(("br", (x, y + 1), token[1:], block_index))
                    y += 1
                    break
                raise ValueError(f"unknown flow token: {token!r}")
            if boustrophedon:
                # A wrap turns down one row and keeps executing in the other
                # direction: the shim corridor IS the next op row. Safe because
                # X is always entered heading south via its v-drop, const_ops
                # emits no backtick literals (which read reversed westward),
                # and pipe bands depend on the op's column, not its heading.
                if token in cols:
                    zone_low, zone_high = zones[token]
                    assert zone_low is not None, "boustrophedon needs zoned ports"
                    if heading == 1 and x > zone_high:
                        put(x, y, "v")
                        y += 1
                        put(x, y, "<")
                        heading, x = -1, x - 1
                    if heading == -1 and x < zone_low:
                        put(x, y, "v")
                        y += 1
                        put(x, y, ">")
                        heading, x = 1, x + 1
                    x = max(x, zone_low) if heading == 1 else min(x, zone_high)
                    put(x, y, glyphs[token])
                    x += heading
                else:
                    if heading == -1 and x <= code:
                        put(x, y, "v")
                        y += 1
                        put(x, y, ">")
                        heading, x = 1, x + 1
                    put(x, y, token)
                    x += heading
                continue
            if token in cols:
                column = cols[token]
                zone_low, zone_high = zones[token]
                if zone_low is not None:
                    if x > zone_high:
                        put(x, y, "v")
                        put(x, y + 1, "<")
                        put(code, y + 1, "v")
                        y += 2
                        put(code, y, ">")
                        x = code + 1
                    if x < zone_low:
                        x = zone_low
                    put(x, y, glyphs[token])
                    x += 1
                    continue
                if x > column:
                    put(x, y, "v")
                    put(x, y + 1, "<")
                    put(code, y + 1, "v")
                    y += 2
                    put(code, y, ">")
                    x = code + 1
                put(column, y, glyphs[token])
                x = column + 1
                put(x, y, "v")
                put(x, y + 1, "<")
                put(code, y + 1, "v")
                y += 2
                put(code, y, ">")
                x = code + 1
            else:
                put(x, y, token)
                x += 1
        # Rows after a block separate its branch exits from the next target's
        # incoming merge band.
        if direct_edges or pooled_edges:
            y += block_gap if block_gap is not None else (2 if tight_gaps else 3)
        else:
            y += 6

    target_col = {label: x0 + 2 + i for i, label in enumerate(flow.blocks)}
    right_highway = code + 150
    left_highway = code - 2
    routes = []
    pooled_routes = []
    target_slot = {label: 0 for label in flow.blocks}
    block_labels = list(flow.blocks)
    for kind, (x, source_y), targets, source_index in pending:
        if (
            local_edges
            and kind == "go"
            and source_index + 1 < len(block_labels)
            and targets[0] == block_labels[source_index + 1]
        ):
            target_y = heads[targets[0]]
            merge_y = target_y - 2
            local_cells = (
                [(x, yy) for yy in range(source_y, merge_y + 1)]
                + [(xx, merge_y) for xx in range(code - 1, x + 1)]
                + [(code - 1, yy) for yy in range(merge_y, target_y + 1)]
            )
            if source_y < merge_y and all(
                program.get(xx, yy) == " " for xx, yy in local_cells
            ):
                put(x, source_y, "v")
                put(x, merge_y, "<")
                put(code - 1, merge_y, "v")
                put(code - 1, target_y, ">")
                continue
        if kind == "go":
            edges = [((x, source_y), "E", targets[0])]
        else:
            positive, zero, negative = targets
            edges = [
                ((x - 1, source_y), "W", positive),
                ((x, source_y + 1), "S", zero),
                ((x + 1, source_y), "E", negative),
            ]
        if pooled_edges:
            grouped = {}
            for (source_x, edge_y), direction, target in edges:
                if target not in target_col:
                    raise ValueError(f"edge targets unknown block {target!r}")
                if direction == "W":
                    put(source_x, edge_y, "<")
                elif direction == "E":
                    put(source_x, edge_y, "v")
                    edge_y += 1
                    if kind == "br":
                        # The zero arm uses the first row below X. Keep the
                        # negative arm one row lower so their westbound paths
                        # cannot encounter each other's highway turn glyphs.
                        put(source_x, edge_y, "v")
                        edge_y += 1
                    put(source_x, edge_y, "<")
                else:
                    # The zero branch has already moved south from X into this
                    # cell; turn it west immediately.
                    put(source_x, edge_y, "<")
                grouped.setdefault(target, []).append((source_x, edge_y))
            for target, sources in grouped.items():
                source_groups = [sources] if dedup_edges else [[source] for source in sources]
                for source_group in source_groups:
                    slot = target_slot[target]
                    target_slot[target] += 1
                    merge_y = heads[target] - (1 if tight_gaps else 2) - slot
                    pooled_routes.append({
                        "sources": source_group,
                        "target": target,
                        "merge_y": merge_y,
                        "source_index": source_index,
                    })
            continue

        for (source_x, edge_y), direction, target in edges:
            if target not in target_col:
                raise ValueError(f"edge targets unknown block {target!r}")
            if pooled_edges:
                slot = target_slot[target]
                target_slot[target] += 1
                merge_y = heads[target] - (1 if tight_gaps else 2) - slot
                pooled_routes.append({
                    "sources": [(source_x, edge_y)],
                    "target": target,
                    "merge_y": merge_y,
                    "source_index": source_index,
                })
                continue
            if direction == "W":
                highway = left_highway
                left_highway -= 1
                put(source_x, edge_y, "<")
            elif direction == "E":
                highway = right_highway
                right_highway += 1
                put(source_x, edge_y, ">")
            else:
                highway = right_highway
                right_highway += 1
                put(source_x, edge_y, "v")
                edge_y += 1
                put(source_x, edge_y, ">")
            if direct_edges:
                slot = target_slot[target]
                target_slot[target] += 1
                merge_y = heads[target] - (1 if tight_gaps else 2) - slot
                target_x = target_col[target]
                if merge_y != edge_y:
                    put(highway, edge_y, "v" if merge_y > edge_y else "^")
                    put(highway, merge_y, "<" if target_x < highway else ">")
                else:
                    put(highway, edge_y, "<" if target_x < highway else ">")
                put(target_x, merge_y, "v")
                put(target_x, heads[target], ">")
            else:
                put(highway, edge_y, "v")
                routes.append((highway, target))

    if pooled_edges:
        if coalesce_targets:
            by_target = {}
            for route in pooled_routes:
                group = by_target.setdefault(route["target"], {
                    "sources": [],
                    "target": route["target"],
                    "merge_y": heads[route["target"]] - (
                        1 if tight_gaps else 2
                    ),
                    "source_index": route["source_index"],
                })
                for source in route["sources"]:
                    if source not in group["sources"]:
                        group["sources"].append(source)
            pooled_routes = list(by_target.values())
        # Color vertical route intervals. Disjoint intervals safely share a
        # highway because their only direction glyphs are at the two ends.
        lanes = []
        assigned = []
        for route in sorted(
            pooled_routes,
            key=lambda item: (
                min([item["merge_y"]] + [source[1] for source in item["sources"]]),
                max([item["merge_y"]] + [source[1] for source in item["sources"]]),
            ),
        ):
            ys = [route["merge_y"]] + [source[1] for source in route["sources"]]
            lo, hi = min(ys), max(ys)
            lane = next(
                (index for index, end in enumerate(lanes) if end < lo),
                None,
            )
            if lane is None:
                lane = len(lanes)
                lanes.append(hi)
            else:
                lanes[lane] = hi
            assigned.append((route, lane))
        for route, lane in assigned:
            highway = code - 2 - lane
            target = route["target"]
            merge_y = route["merge_y"]
            target_x = target_col[target]
            for _source_x, edge_y in route["sources"]:
                put(highway, edge_y, "v" if merge_y > edge_y else "^")
            put(highway, merge_y, "<")
            put(target_x, merge_y, "v")
            put(target_x, heads[target], ">")
        if code - 2 - len(lanes) <= max(target_col.values(), default=x0):
            raise ValueError(
                f"pooled routes need {len(lanes)} lanes; increase code_x"
            )
    elif not direct_edges and left_highway <= max(target_col.values(), default=x0):
        raise ValueError("code_x leaves too little room for target lanes and west edges")

    channel_y = y + 3
    if not direct_edges:
        for highway, target in routes:
            target_x = target_col[target]
            put(highway, channel_y, "<")
            put(target_x, channel_y, "^")
            put(target_x, heads[target], ">")
            channel_y += 1

    if pooled_edges:
        max_used_x = max(max(xx for xx, _ in program.cells), max(cols.values()))
        width = max_used_x - x0 + 2
    else:
        width = right_highway - x0 + 3
    height = channel_y - y0 + 2
    program.room(x0, y0, width, height)
    bottom = y0 + height
    return {
        "ports": {name: (column, bottom) for name, column in cols.items()},
        "heads": heads,
        "width": width,
        "height": height,
        "bottom": bottom,
        "code_x": code,
        "pooled_assignments": assigned,
    }
