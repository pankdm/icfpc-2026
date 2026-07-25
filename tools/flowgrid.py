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


def lay_cfg_controller(program, flow, pipe_columns, code_x=300, x0=0, y0=0):
    """Lay out *flow* and return its bounds and named external pipe ports.

    ``pipe_columns`` maps each symbolic token to ``(x_offset, glyph)`` where the
    offset is relative to the code column.  All ports leave the controller at
    its bottom edge.  The returned mapping contains ``ports``, ``heads``,
    ``width``, ``height``, ``bottom``, and ``code_x``.
    """
    code = x0 + code_x
    cols = {name: code + spec[0] for name, spec in pipe_columns.items()}
    glyphs = {name: spec[1] for name, spec in pipe_columns.items()}
    heads, pending = {}, []
    y = y0 + 3

    def put(x, yy, ch):
        cur = program.get(x, yy)
        assert cur in (" ", ch), (x, yy, cur, ch)
        program.put(x, yy, ch)

    for block_index, (label, tokens) in enumerate(flow.blocks.items()):
        heads[label] = y
        put(code, y, "@" if block_index == 0 else ">")
        x = code + 1
        for token in tokens:
            if isinstance(token, tuple):
                if token[0] == "go":
                    pending.append(("go", (x, y), token[1:]))
                    break
                if token[0] == "br":
                    put(x, y, "v")
                    put(x, y + 1, "X")
                    pending.append(("br", (x, y + 1), token[1:]))
                    y += 1
                    break
                raise ValueError(f"unknown flow token: {token!r}")
            if token in cols:
                column = cols[token]
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
        # These rows are reserved for incoming control-flow merges.
        y += 6

    target_col = {label: x0 + 2 + i for i, label in enumerate(flow.blocks)}
    right_highway = code + 150
    left_highway = code - 2
    routes = []
    for kind, (x, source_y), targets in pending:
        if kind == "go":
            edges = [((x, source_y), "E", targets[0])]
        else:
            positive, zero, negative = targets
            edges = [
                ((x - 1, source_y), "W", positive),
                ((x, source_y + 1), "S", zero),
                ((x + 1, source_y), "E", negative),
            ]
        for (source_x, edge_y), direction, target in edges:
            if target not in target_col:
                raise ValueError(f"edge targets unknown block {target!r}")
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
            put(highway, edge_y, "v")
            routes.append((highway, target))

    if left_highway <= max(target_col.values(), default=x0):
        raise ValueError("code_x leaves too little room for target lanes and west edges")

    channel_y = y + 3
    for highway, target in routes:
        target_x = target_col[target]
        put(highway, channel_y, "<")
        put(target_x, channel_y, "^")
        put(target_x, heads[target], ">")
        channel_y += 1

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
    }
