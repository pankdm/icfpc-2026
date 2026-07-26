"""Dense boustrophedon CFG controller layout for ``flowgrid.Flow``.

Operations carry the column interval allowed by nearest-pipe binding.  Code
uses both east- and west-heading rows, while control transfers use
interval-coloured corridors on the west side of the room.
"""

E, W = (1, 0), (-1, 0)


def voronoi_bands(sites):
    """Return inclusive nearest-site bands for ``[(name, column), ...]``."""
    sites = sorted(sites, key=lambda item: item[1])
    bands = {}
    for i, (name, col) in enumerate(sites):
        lo = 1 if i == 0 else (sites[i - 1][1] + col) // 2 + 1
        hi = (
            10 ** 9
            if i == len(sites) - 1
            else (col + sites[i + 1][1]) // 2
        )
        bands[name] = (lo, hi)
    return bands


class Conflict(RuntimeError):
    pass


def verify_bindings(program, layout):
    """Check every recorded controller port op against actual pipe ownership."""
    import pipecheck

    rows = program.render().splitlines()
    width = max(len(row) for row in rows)
    rows = [row.ljust(width) for row in rows]
    min_x, min_y, _, _ = program.bounds()
    topology = pipecheck.analyze(rows)
    if topology.get("type") == "error":
        raise RuntimeError(topology.get("message"))
    incoming, outgoing = pipecheck.attachments(topology)
    attachment_positions = {}
    for pipe_i, pipe in enumerate(topology["pipes"]):
        path = pipe.get("path") or []
        if not path:
            continue
        if pipe.get("src") == 0:
            attachment_positions[("out", pipe_i)] = tuple(path[0]["pos"])
        if pipe.get("dst") == 0:
            attachment_positions[("in", pipe_i)] = tuple(path[-1]["pos"])

    bad = []
    for (x, y), port in layout["intent"].items():
        grid_x, grid_y = x - min_x, y - min_y
        kind = "out" if rows[grid_y][grid_x] == "s" else "in"
        candidates = (outgoing if kind == "out" else incoming).get(0, [])
        selected = pipecheck.bind((grid_x, grid_y), candidates)
        selected_position = attachment_positions.get((kind, selected))
        wanted_x = layout["ports"][port][0] - min_x
        if selected_position is None or selected_position[0] != wanted_x:
            bad.append(((x, y), port, selected_position, wanted_x))
    if bad:
        raise RuntimeError(f"{len(bad)} wrong port bindings; first: {bad[0]}")
    print(f"bindings OK: {len(layout['intent'])} controller ops")


class Cursor:
    def __init__(self, opmin, opmax):
        self.cells = {}
        self.opmin = opmin
        self.opmax = opmax
        self.x = self.y = None
        self.d = E

    def put(self, x, y, ch):
        old = self.cells.get((x, y))
        if old is not None and old != ch:
            raise Conflict(f"({x},{y}): {old!r} vs {ch!r}")
        self.cells[(x, y)] = ch

    def newline(self):
        turn_x = self.x + self.d[0]
        self.put(turn_x, self.y, "v")
        self.put(turn_x, self.y + 1, "<" if self.d == E else ">")
        self.d = W if self.d == E else E
        self.x, self.y = turn_x, self.y + 1

    def place(self, ch, lo, hi):
        lo = max(lo, self.opmin)
        hi = min(hi, self.opmax)
        if lo > hi:
            raise Conflict(f"empty band for {ch!r}: [{lo},{hi}]")
        for _ in range(4):
            if self.d == E:
                next_x = max(self.x + 1, lo)
                if next_x <= hi:
                    break
            else:
                next_x = min(self.x - 1, hi)
                if next_x >= lo:
                    break
            self.newline()
        else:
            raise Conflict(f"cannot place {ch!r} in [{lo},{hi}]")
        self.put(next_x, self.y, ch)
        self.x = next_x

    def to_west(self):
        if self.d == E:
            self.put(self.x + 1, self.y, "v")
            self.put(self.x + 1, self.y + 1, "<")
            self.x, self.y, self.d = self.x + 1, self.y + 1, W

    def branch3(self, glyph):
        turn_x = self.x + self.d[0]
        self.put(turn_x, self.y, "v")
        branch_y = self.y + 1
        self.put(turn_x, branch_y, glyph)
        self.put(turn_x, branch_y + 1, "<")
        self.put(turn_x + 1, branch_y, "v")
        self.put(turn_x + 1, branch_y + 2, "<")
        return branch_y, branch_y + 1, branch_y + 2


def _assign_corridors(edges, entry):
    order = sorted(
        range(len(edges)),
        key=lambda i: (
            min(edges[i][0], entry[edges[i][1]]),
            max(edges[i][0], entry[edges[i][1]]),
        ),
    )
    corridors = []
    assignment = {}
    for edge_i in order:
        source_y, target = edges[edge_i]
        lo, hi = sorted((source_y, entry[target]))
        for corridor_i, members in enumerate(corridors):
            compatible = True
            for member_i in members:
                source_y2, target2 = edges[member_i]
                lo2, hi2 = sorted((source_y2, entry[target2]))
                overlap_lo = max(lo, lo2)
                overlap_hi = min(hi, hi2)
                if overlap_lo > overlap_hi:
                    continue
                if (
                    overlap_lo == overlap_hi
                    and target == target2
                    and overlap_lo == entry[target]
                ):
                    continue
                compatible = False
                break
            if compatible:
                members.append(edge_i)
                assignment[edge_i] = corridor_i
                break
        else:
            corridors.append([edge_i])
            assignment[edge_i] = len(corridors) - 1
    return assignment, len(corridors)


def lay_cfg_boustrophedon(
    program,
    flow,
    port_spec,
    code_x=30,
    x0=0,
    y0=0,
    op_slack=6,
):
    cols = {
        name: x0 + code_x + spec[0]
        for name, spec in port_spec.items()
    }
    glyphs = {name: spec[1] for name, spec in port_spec.items()}
    bands = {}
    bands.update(
        voronoi_bands(
            [(name, col) for name, col in cols.items() if glyphs[name] == "s"]
        )
    )
    bands.update(
        voronoi_bands(
            [(name, col) for name, col in cols.items() if glyphs[name] == "r"]
        )
    )
    opmax = max(cols.values()) + op_slack
    labels = list(flow.blocks)

    corridor_count = 6
    for _ in range(40):
        cursor, entry, edges, intent = _lay_once(
            flow,
            labels,
            cols,
            glyphs,
            bands,
            x0,
            y0,
            corridor_count,
            opmax,
        )
        assignment, needed = _assign_corridors(edges, entry)
        if needed <= corridor_count:
            break
        corridor_count = needed
    else:
        raise Conflict("corridor count did not converge")

    for edge_i, (source_y, target) in enumerate(edges):
        col = x0 + 1 + assignment[edge_i]
        target_y = entry[target]
        cursor.put(col, source_y, "v" if target_y > source_y else "^")
        cursor.put(col, target_y, ">")

    max_y = max(y for _, y in cursor.cells)
    wall_y = max_y + 1
    # +1 on opmax reserves the TURN column: newline/to_west/branch3 put their glyph at
    # self.x + d, i.e. opmax+1, while place() only clamps ops to opmax. Without the
    # reserve that turn glyph lands on the room's own right wall and the build dies with
    # AssertionError (x, y, '|', 'v') as soon as an op actually reaches opmax — which is
    # what any attempt to widen the op bands (replica ports, band overrides) triggers.
    width = max(opmax + 1, max(cols.values())) + 2 - x0
    height = wall_y - y0 + 1
    program.room(x0, y0, width, height)
    for (x, y), ch in cursor.cells.items():
        old = program.get(x, y)
        assert old in (" ", ch), (x, y, old, ch)
        program.put(x, y, ch)

    bottom = y0 + height
    return {
        "ports": {name: (col, bottom) for name, col in cols.items()},
        "heads": dict(entry),
        "width": width,
        "height": height,
        "bottom": bottom,
        "code_x": x0 + code_x,
        "intent": intent,
        "bands": bands,
        "ncorr": corridor_count,
    }


def _lay_once(flow, labels, cols, glyphs, bands, x0, y0, ncorr, opmax):
    opmin = x0 + ncorr + 2
    cursor = Cursor(opmin, opmax)
    entry = {}
    edges = []
    intent = {}
    y = y0 + 1
    for label_i, label in enumerate(labels):
        entry[label] = y
        cursor.x, cursor.y, cursor.d = opmin - 1, y, E
        if label_i == 0:
            cursor.put(opmin - 1, y, "@")
        term = None
        for token in flow.blocks[label]:
            if isinstance(token, tuple):
                term = token
                break
            if token in cols:
                lo, hi = bands[token]
                cursor.place(glyphs[token], lo, hi)
                intent[(cursor.x, cursor.y)] = token
            else:
                cursor.place(token, opmin, opmax)
        if term is None:
            pass
        elif term[0] == "go":
            cursor.to_west()
            edges.append((cursor.y, term[1]))
        elif term[0] == "br":
            positive_y, zero_y, negative_y = cursor.branch3("X")
            edges.append((positive_y, term[1]))
            edges.append((zero_y, term[2]))
            edges.append((negative_y, term[3]))
            cursor.y = negative_y
        else:
            raise Conflict(f"unknown terminator {term!r}")
        y = cursor.y + 1
    return cursor, entry, edges, intent
