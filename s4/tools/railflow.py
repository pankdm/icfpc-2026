"""Dense CFG controller layout: boustrophedon code + rail-routed control flow.

``boustro.lay_cfg_boustrophedon`` spends **four rows per three-way branch** and
**one row per jump**, because every exit is turned into a westbound man who
needs a private row to reach the corridor lanes.  On snake that is 67 of 189
controller rows; on pathfinder 90 of 285.

This module keeps boustro's op placement (same ``Cursor``, same Voronoi bands,
same literal-column rule) and replaces only the *terminators*:

  jump   the man is already westbound on his last code row, so the corridor
         glyph goes straight onto that row -- **zero extra rows**.  An eastbound
         last row still needs one ``newline`` to turn around.

  branch one ``newline`` drops the man onto a private *rail row* heading west,
         where ``X`` sits in the corridor lanes.  Entering ``X`` westbound,
         ``A>0`` turns north, ``A<0`` turns south and ``A=0`` carries on west,
         so all three exits leave on their own column with **one extra row**.

         A north exit whose target is *below* (and a south exit whose target is
         *above*) needs one U-turn: the man is caught one row off the rail row
         and sent west to a second column, which is then free to run either
         way.  Row ``rail-1`` is the block's own last code row, whose westbound
         man stops at the ``newline`` turn glyph far to the east, so its whole
         corridor region is free real estate.  Row ``rail+1`` is the next
         block's entry row, so a U-turn there must stay west of every entry
         arrow -- the allocator enforces that, and reserves a private row when
         it cannot.

Corridors are single columns with arrow cells only at their two ends; the cells
in between are empty and a man glides through them.  Two corridors may share a
column only when their row spans are disjoint.  Horizontal safety is free by
construction: source arrows only ever land on terminator/rail rows and target
arrows only on entry rows, and those sets are disjoint.
"""

from boustro import (  # noqa: F401  (re-exported for builders)
    Conflict,
    Cursor,
    verify_bindings,
    voronoi_bands,
)

E, W = (1, 0), (-1, 0)


def _drop_west(cursor):
    """Turn down one row and head west, whichever way the man was walking.

    ``Cursor.newline`` alternates direction, so from a westbound row it would
    hand back an eastbound one.  The rail row must always be westbound: that is
    what makes ``X`` fan out north/west/south.
    """
    turn_x = cursor.x + cursor.d[0]
    cursor.put(turn_x, cursor.y, "v")
    cursor.put(turn_x, cursor.y + 1, "<")
    cursor.x, cursor.y, cursor.d = turn_x, cursor.y + 1, W


# --------------------------------------------------------------------------
# structure pass


def _lay_once(flow, labels, cols, glyphs, bands, x0, y0, nrail, opmax,
              lit_forbid=(), pad_after=(), split_entry=()):
    """Place every block's ops and record what the rail must carry.

    ``pad_after`` names blocks whose branch needs a *private* row under its rail
    row, because its south exit has to U-turn there and the next block's entry
    arrows would otherwise catch the U-turning man.

    ``split_entry`` names single-row branch blocks that must spend an extra
    ``newline`` so their last code row is not also their entry row.  That row is
    where the NORTH exit U-turns, and an entering man walks EAST across it, so a
    U-turn glyph east of an entry arrow would catch him.  It is only actually
    needed when the north exit U-turns AND the U-turn column cannot be placed
    west of every entry arrow -- which the allocator discovers, so this starts
    empty and grows by fixpoint instead of being paid on all 98 branches.
    """
    opmin = x0 + nrail + 2
    cursor = Cursor(opmin, opmax)
    cursor.lit_cols.update(lit_forbid)
    entry = {}
    items = []
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
            elif len(token) > 1 and token[0] == "`":
                cursor.place_run(token, opmin, opmax)
            else:
                cursor.place(token, opmin, opmax)
        if term is None:
            pass
        elif term[0] == "go":
            if cursor.d == E:
                cursor.newline()
            items.append({
                "kind": "go", "row": cursor.y, "target": term[1],
                "label": label,
            })
        elif term[0] == "br":
            if cursor.y == entry[label] and label in split_entry:
                cursor.newline()
            code_row = cursor.y
            _drop_west(cursor)        # private rail row, now heading west
            items.append({
                "kind": "br", "row": cursor.y, "code_row": code_row,
                "pos": term[1], "zero": term[2], "neg": term[3],
                "label": label,
            })
            if label in pad_after:
                cursor.y += 1
        else:
            raise Conflict(f"unknown terminator {term!r}")
        y = cursor.y + 1
    return cursor, entry, items, intent


# --------------------------------------------------------------------------
# rail allocation


class _Rail:
    """Column occupancy for the corridor lanes."""

    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.spans = {c: [] for c in range(lo, hi + 1)}
        self.glyphs = {}

    def free(self, col, a, b, share=None):
        if col < self.lo or col > self.hi:
            return False
        a, b = min(a, b), max(a, b)
        for (p, q) in self.spans[col]:
            if b < p or a > q:
                continue
            return False
        # a target arrow may coincide with an identical one
        if share is not None:
            return True
        return True

    def take(self, col, a, b, marks):
        a, b = min(a, b), max(a, b)
        for (row, glyph) in marks:
            old = self.glyphs.get((col, row))
            if old is not None and old != glyph:
                return False
        self.spans[col].append((a, b))
        for (row, glyph) in marks:
            self.glyphs[(col, row)] = glyph
        return True

    def pick(self, a, b, marks, below=None, descending=True):
        """Largest (or smallest) free column strictly below ``below``."""
        hi = self.hi if below is None else below - 1
        order = range(hi, self.lo - 1, -1) if descending else range(self.lo, hi + 1)
        for col in order:
            if self.free(col, a, b) and self.take(col, a, b, marks):
                return col
        return None


def _arrow(src_row, dst_row):
    return "v" if dst_row > src_row else "^"


def _allocate(items, entry, x0, nrail, padded, split_entry=(), north_cap=None):
    """Assign a corridor column to every control transfer.

    Returns ``(cells, blocked)``.  ``cells`` is ``None`` when allocation failed;
    ``blocked`` names the branch blocks that would need a private U-turn row.
    """
    north_cap = north_cap or {}
    rail = _Rail(x0 + 1, x0 + nrail)
    # rows that carry entry arrows, and the westernmost entry column on each
    entry_rows = set(entry.values())
    entry_min = {}
    cells = []

    def note(col, row, glyph):
        cells.append((col, row, glyph))

    # Reserve nothing up front; allocate branch triples first (they are the
    # constrained ones), then the plain jumps.
    order = sorted(range(len(items)),
                   key=lambda i: (0 if items[i]["kind"] == "br" else 1,
                                  items[i]["row"]))
    for idx in order:
        it = items[idx]
        if it["kind"] == "go":
            t, e = it["row"], entry[it["target"]]
            col = rail.pick(t, e, [(t, _arrow(t, e)), (e, ">")],
                            descending=False)
            if col is None:
                return None, set(), {}
            note(col, t, _arrow(t, e))
            note(col, e, ">")
            if e in entry_rows:
                entry_min[e] = min(entry_min.get(e, 10 ** 9), col)
            continue

        rr = it["row"]              # rail row (westbound)
        cr = it["code_row"]         # block's last code row (rail region free)
        e_pos, e_zero, e_neg = (entry[it[k]] for k in ("pos", "zero", "neg"))

        # X column: carries the north exit upward and/or the south exit down.
        # Build the marks for whatever is direct, then U-turn the rest.
        pos_direct = e_pos < rr
        neg_direct = e_neg > rr
        span_lo = min(rr, e_pos if pos_direct else cr)
        span_hi = max(rr, e_neg if neg_direct else rr + 1)
        marks = [(rr, "X")]
        if pos_direct:
            marks.append((e_pos, ">"))
        else:
            marks.append((cr, "<"))
        if neg_direct:
            marks.append((e_neg, ">"))
        else:
            marks.append((rr + 1, "<"))
        cx = rail.pick(span_lo, span_hi, marks)
        if cx is None:
            return None, set(), {}
        for row, glyph in marks:
            note(cx, row, glyph)
        if pos_direct and e_pos in entry_rows:
            entry_min[e_pos] = min(entry_min.get(e_pos, 10 ** 9), cx)
        if neg_direct and e_neg in entry_rows:
            entry_min[e_neg] = min(entry_min.get(e_neg, 10 ** 9), cx)

        # zero exit: keeps walking west off the X, so strictly west of it.
        cz = rail.pick(rr, e_zero, [(rr, _arrow(rr, e_zero)), (e_zero, ">")],
                       below=cx)
        if cz is None:
            return None, set(), {}
        note(cz, rr, _arrow(rr, e_zero))
        note(cz, e_zero, ">")
        if e_zero in entry_rows:
            entry_min[e_zero] = min(entry_min.get(e_zero, 10 ** 9), cz)

        if not pos_direct:
            # caught on the block's own last code row, then free to run either way
            cp = rail.pick(cr, e_pos, [(cr, _arrow(cr, e_pos)), (e_pos, ">")],
                           below=cx)
            if cp is None:
                return None, set(), {}
            note(cp, cr, _arrow(cr, e_pos))
            note(cp, e_pos, ">")
            if e_pos in entry_rows:
                entry_min[e_pos] = min(entry_min.get(e_pos, 10 ** 9), cp)
            if cr == entry[it["label"]]:
                # single-row block: the north U-turn glyphs sit on the block's
                # OWN entry row, so they must stay west of every entry arrow.
                it["north_row"], it["north_cx"] = cr, cx
        if not neg_direct:
            uro = rr + 1
            cn = rail.pick(uro, e_neg, [(uro, _arrow(uro, e_neg)),
                                        (e_neg, ">")], below=cx)
            if cn is None:
                return None, set(), {}
            note(cn, uro, _arrow(uro, e_neg))
            note(cn, e_neg, ">")
            if e_neg in entry_rows:
                entry_min[e_neg] = min(entry_min.get(e_neg, 10 ** 9), cn)
            # the U-turn arrows live on the next block's entry row; the man who
            # enters there walks EAST, so every entry arrow must sit east of cx.
            it["uturn_row"] = uro
            it["uturn_cx"] = cx

    # entry-row ordering check: on a row that also carries a south U-turn, all
    # entry arrows must be east of the U-turn's X column.  A row that was padded
    # is private, so it can never clash.
    blocked = set()
    resplit = {}
    for it in items:
        if it.get("north_row") is not None and it["label"] not in split_entry:
            row, cx = it["north_row"], it["north_cx"]
            if row in entry_min and entry_min[row] <= cx:
                resplit[it["label"]] = entry_min[row]
        if it.get("uturn_row") is None or it["label"] in padded:
            continue
        row, cx = it["uturn_row"], it["uturn_cx"]
        if row in entry_min and entry_min[row] <= cx:
            blocked.add(it["label"])
    if blocked or resplit:
        return None, blocked, resplit
    return cells, set(), {}


def solve(flow, labels, cols, glyphs, bands, x0, y0, nrail, opmax,
          lit_forbid=(), max_rail=64, pick_split=None, pick_pad=None):
    """Fixpoint over rail width, south-U-turn padding and north-U-turn caps."""
    padded = set()
    split_entry = set()
    north_cap = {}
    tries = {}
    for _ in range(600):
        cursor, entry, items, intent = _lay_once(
            flow, labels, cols, glyphs, bands, x0, y0, nrail, opmax,
            lit_forbid, pad_after=padded, split_entry=split_entry)
        cells, blocked, resplit = _allocate(
            items, entry, x0, nrail, padded, split_entry, north_cap)
        if cells is not None:
            return cursor, entry, cells, nrail, intent
        if set(resplit) - split_entry:
            # Add ONE offender per round, topmost first.  Splitting a block
            # shifts every later block's entry row, which retires some of the
            # other offenders for free -- committing the whole `resplit` set at
            # once permanently over-pays for them (measured: 700 rows vs 690).
            fresh = sorted(set(resplit) - split_entry)
            split_entry |= set(fresh[:1] if pick_split is None
                                else pick_split(fresh))
            continue
        if blocked - padded:
            fresh = sorted(blocked - padded)
            padded |= set(fresh if pick_pad is None else pick_pad(fresh))
            continue
        nrail += 2
        if nrail > max_rail:
            raise Conflict("rail allocation did not converge")
    raise Conflict("rail allocation did not converge")


# --------------------------------------------------------------------------
# driver


def lay_cfg_rail(program, flow, port_spec, code_x=30, x0=0, y0=0, op_slack=6,
                 lit_forbid=(), nrail=10, max_rail=64):
    cols = {name: x0 + code_x + spec[0] for name, spec in port_spec.items()}
    glyphs = {name: spec[1] for name, spec in port_spec.items()}
    bands = {}
    bands.update(voronoi_bands(
        [(n, c) for n, c in cols.items() if glyphs[n] == "s"]))
    bands.update(voronoi_bands(
        [(n, c) for n, c in cols.items() if glyphs[n] == "r"]))
    opmax = max(cols.values()) + op_slack
    labels = list(flow.blocks)

    cursor, entry, cells, nrail, intent = solve(
        flow, labels, cols, glyphs, bands, x0, y0, nrail, opmax,
        lit_forbid, max_rail)

    for col, row, glyph in cells:
        cursor.put(col, row, glyph)

    max_y = max(y for _, y in cursor.cells)
    wall_y = max_y + 1
    # +3, not +2: a `newline` turn glyph lands one column EAST of the last op,
    # and an op can legitimately sit at opmax when a port's band ends there.
    # With +2 that turn column IS the east wall (crash: '|' vs 'v').
    width = max(opmax, max(cols.values())) + 3 - x0
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
        "ncorr": nrail,
    }
