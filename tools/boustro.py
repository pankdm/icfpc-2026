"""boustro.py — dense boustrophedon CFG controller layout (flowgrid drop-in).

flowgrid.lay_cfg_controller walks every code row EAST from a fixed code column
and returns there after every band regression, so a controller both stretches
vertically (2 rows per regression) and pays a full-width glide per wrap. This
emitter lays the same Flow as a boustrophedon (reflow.py's LLLM trick):

  * every op carries the COLUMN INTERVAL its pipe binding allows — the exact
    Voronoi band of its port's attachment among same-direction attachments on
    the bottom wall — and placement is "advance to the next column the band
    allows", turning down one row when the current heading runs out;
  * west-heading rows do real work (all tokens are single direction-free
    glyphs; const_ops emits no backtick literals);
  * every block gets a canonical east-heading entry row; all control transfers
    ride interval-coloured corridor columns on the west edge. Two edges may
    share a corridor when their spans meet only at a common '>' landing;
  * a `br` is the same v/X gadget flowgrid emits (entered heading SOUTH, so
    W leg = positive, S = zero, E = negative), with all three legs turned into
    westbound glides on three stacked rows.

Interface matches lay_cfg_controller closely enough for stateflow.build_program
(lay_fn=...): returns {"ports", "heads", "width", "height", "bottom", "code_x"},
plus "intent" {(x,y): port_name} so the builder can re-verify every binding
against the reference nearest-pipe rule after assembly.
"""

E, W = (1, 0), (-1, 0)


def voronoi_bands(sites):
    """sites: [(name, col)] one direction -> {name: (lo, hi)} inclusive bands.

    At the exact midpoint the WEST attachment wins (equal Manhattan distance,
    tie in reading order: same row, smaller x)."""
    sites = sorted(sites, key=lambda t: t[1])
    bands = {}
    for i, (name, c) in enumerate(sites):
        lo = 1 if i == 0 else (sites[i - 1][1] + c) // 2 + 1
        hi = 10 ** 9 if i == len(sites) - 1 else (c + sites[i + 1][1]) // 2
        bands[name] = (lo, hi)
    return bands


class Conflict(RuntimeError):
    pass


class Cursor:
    def __init__(self, opmin, opmax):
        self.cells = {}
        self.opmin, self.opmax = opmin, opmax
        self.x = self.y = None
        self.d = E

    def put(self, x, y, ch):
        old = self.cells.get((x, y))
        if old is not None and old != ch:
            raise Conflict(f"({x},{y}): {old!r} vs {ch!r}")
        self.cells[(x, y)] = ch

    def newline(self):
        t = self.x + self.d[0]
        self.put(t, self.y, "v")
        self.put(t, self.y + 1, "<" if self.d == E else ">")
        self.d = W if self.d == E else E
        self.x, self.y = t, self.y + 1

    def place(self, ch, lo, hi):
        lo, hi = max(lo, self.opmin), min(hi, self.opmax)
        if lo > hi:
            raise Conflict(f"empty band for {ch!r}: [{lo},{hi}]")
        for _ in range(4):
            if self.d == E:
                nx = max(self.x + 1, lo)
                if nx <= hi:
                    break
            else:
                nx = min(self.x - 1, hi)
                if nx >= lo:
                    break
            self.newline()
        else:
            raise Conflict(f"cannot place {ch!r} in [{lo},{hi}]")
        self.put(nx, self.y, ch)
        self.x = nx

    def to_west(self):
        """End the row so the cursor heads WEST with only blanks west of it."""
        if self.d == E:
            self.put(self.x + 1, self.y, "v")
            self.put(self.x + 1, self.y + 1, "<")
            self.x, self.y, self.d = self.x + 1, self.y + 1, W

    def branch3(self, glyph):
        """v/X entered heading south. Returns the three westbound leg rows
        (positive, zero, negative) — flowgrid's W/S/E mapping exactly."""
        t = self.x + self.d[0]
        self.put(t, self.y, "v")
        yb = self.y + 1
        self.put(t, yb, glyph)          # positive leg exits west along yb
        self.put(t, yb + 1, "<")        # zero leg drops one row, turns west
        self.put(t + 1, yb, "v")        # negative leg exits east, turns south
        self.put(t + 1, yb + 2, "<")    # ... and west two rows below
        return yb, yb + 1, yb + 2


def _assign_corridors(edges, entry):
    """Greedy interval colouring; spans may share a corridor only where they
    meet at the SAME '>' landing cell (same target's entry row)."""
    order = sorted(range(len(edges)),
                   key=lambda i: (min(edges[i][0], entry[edges[i][1]]),
                                  max(edges[i][0], entry[edges[i][1]])))
    corridors = []                       # per corridor: list of edge indices
    assignment = {}
    for i in order:
        sy, tgt = edges[i]
        lo, hi = min(sy, entry[tgt]), max(sy, entry[tgt])
        for ci, members in enumerate(corridors):
            ok = True
            for j in members:
                sy2, tgt2 = edges[j]
                lo2, hi2 = min(sy2, entry[tgt2]), max(sy2, entry[tgt2])
                a, b = max(lo, lo2), min(hi, hi2)
                if a > b:
                    continue
                if a == b and tgt == tgt2 and a == entry[tgt]:
                    continue             # shared '>' landing only
                ok = False
                break
            if ok:
                members.append(i)
                assignment[i] = ci
                break
        else:
            corridors.append([i])
            assignment[i] = len(corridors) - 1
    return assignment, len(corridors)


def lay_cfg_boustrophedon(program, flow, port_spec, code_x=30, x0=0, y0=0,
                          op_slack=6):
    cols = {name: x0 + code_x + spec[0] for name, spec in port_spec.items()}
    glyphs = {name: spec[1] for name, spec in port_spec.items()}
    bands = {}
    bands.update(voronoi_bands([(n, c) for n, c in cols.items()
                                if glyphs[n] == "s"]))
    bands.update(voronoi_bands([(n, c) for n, c in cols.items()
                                if glyphs[n] == "r"]))
    opmax = max(cols.values()) + op_slack
    labels = list(flow.blocks)

    ncorr = 6
    for _attempt in range(40):
        try:
            cur, entry, edges, intent = _lay_once(
                flow, labels, cols, glyphs, bands, x0, y0, ncorr, opmax)
        except Conflict as e:
            raise SystemExit(f"boustro layout conflict: {e}")
        assignment, need = _assign_corridors(edges, entry)
        if need <= ncorr:
            break
        ncorr = need
    else:
        raise SystemExit("corridor count did not converge")

    for i, (sy, tgt) in enumerate(edges):
        c = x0 + 1 + assignment[i]
        ey = entry[tgt]
        cur.put(c, sy, "v" if ey > sy else "^")
        cur.put(c, ey, ">")

    # room shell
    max_y = max(y for _, y in cur.cells)
    wall_y = max_y + 1
    width = max(opmax, max(cols.values())) + 2 - x0   # walls at x0 and x0+width-1
    height = wall_y - y0 + 1
    program.room(x0, y0, width, height)
    for (x, y), ch in cur.cells.items():
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
        "ncorr": ncorr,
    }


def _lay_once(flow, labels, cols, glyphs, bands, x0, y0, ncorr, opmax):
    opmin = x0 + ncorr + 2
    cur = Cursor(opmin, opmax)
    entry, edges, intent = {}, [], {}
    y = y0 + 1
    for li, label in enumerate(labels):
        entry[label] = y
        cur.x, cur.y, cur.d = opmin - 1, y, E
        if li == 0:
            cur.put(opmin - 1, y, "@")
        term = None
        for tok in flow.blocks[label]:
            if isinstance(tok, tuple):
                term = tok
                break
            if tok in cols:
                lo, hi = bands[tok]
                cur.place(glyphs[tok], lo, hi)
                intent[(cur.x, cur.y)] = tok
            else:
                cur.place(tok, opmin, opmax)
        if term is None:
            pass                                    # halt block ends with H op
        elif term[0] == "go":
            cur.to_west()
            edges.append((cur.y, term[1]))
        elif term[0] == "br":
            yp, yz, yn = cur.branch3("X")
            edges.append((yp, term[1]))
            edges.append((yz, term[2]))
            edges.append((yn, term[3]))
            cur.y = yn
        else:
            raise Conflict(f"unknown terminator {term!r}")
        y = cur.y + 1
    return cur, entry, edges, intent
