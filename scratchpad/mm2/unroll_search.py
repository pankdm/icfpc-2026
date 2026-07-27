"""Is MUL's MAC racetrack unrollable past U=1?

Cost model from DESIGN_mm2.md: a closed rectangular loop of perimeter P costs P
ticks/lap; the 4 corners must be turn glyphs (no computing op turns a man
unconditionally), so P = 6U + 4 and ticks/MAC = 6 + 4/U.

The model ignores the binding constraint: `r`/`s` lock onto the NEAREST pipe
(Manhattan to the pipe cell just outside the wall, reading-order ties). With U
copies of the cycle on one loop, AR must beat BR at *every* r_AR cell and lose at
every r_BR cell. This enumerates every ring shape, every rotation of the cycle
around it, and every placement of the 4 attachments on the room walls.
"""
import itertools

CYCLE = ['*', 'PP', 'AR', 'M', 'BR', 'BF']      # MUL body, in execution order
IN, OUT = ('AR', 'BR'), ('PP', 'BF')


def ring_cells(w, h):
    """Perimeter cells of a w x h rectangle in walk order, plus the corner set."""
    cells = []
    for x in range(w):
        cells.append((x, 0))
    for y in range(1, h):
        cells.append((w - 1, y))
    for x in range(w - 2, -1, -1):
        cells.append((x, h - 1))
    for y in range(h - 2, 0, -1):
        cells.append((0, y))
    corners = {(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)}
    return cells, corners


def feasible(slots, W, H, ox, oy):
    """slots: {op name -> [cells]} in ROOM coords. Try every attachment 4-tuple."""
    cands = []
    for x in range(1, W - 1):
        cands += [(x, -1), (x, H)]
    for y in range(1, H - 1):
        cands += [(-1, y), (W, y)]

    def d(c, p):
        return abs(c[0] - p[0]) + abs(c[1] - p[1])

    def solve(pair):
        """ordered attach cells for (nm0, nm1) satisfying both Voronoi sets"""
        out = []
        for a in cands:
            for b in cands:
                if a == b:
                    continue
                ok = True
                for nm, p, q in ((pair[0], a, b), (pair[1], b, a)):
                    for cell in slots[nm]:
                        dn, do = d(cell, p), d(cell, q)
                        if dn > do or (dn == do and (p[1], p[0]) > (q[1], q[0])):
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    out.append((a, b))
        return out

    ins, outs = solve(IN), solve(OUT)
    for a, b in ins:
        for c, e in outs:
            if len({a, b, c, e}) == 4:
                return {'AR': a, 'BR': b, 'PP': c, 'BF': e}
    return None


def try_shape(w, h, U, spares):
    """Ring w x h; lay U copies of CYCLE + `spares` no-ops on the non-corner cells."""
    cells, corners = ring_cells(w, h)
    P = len(cells)
    if P != 6 * U + 4 + spares:
        return None
    op_idx = [i for i, c in enumerate(cells) if c not in corners]
    if len(op_idx) != 6 * U + spares:
        return None
    body = CYCLE * U
    # every rotation of the loop, and every way to place the spare cells
    for rot in range(P):
        seq = [cells[(i + rot) % P] for i in range(P)]
        cset = {(c) for c in corners}
        free = [i for i, c in enumerate(seq) if c not in cset]
        for spare_at in itertools.combinations(range(len(free)), spares):
            prog, k = [], 0
            for j in range(len(free)):
                if j in spare_at:
                    prog.append('.')
                else:
                    prog.append(body[k]); k += 1
            slots = {}
            for nm, j in zip(prog, free):
                if nm in ('*', 'M', '.'):
                    continue
                slots.setdefault(nm, []).append(seq[j])
            if len(slots) != 4:
                continue
            # place the ring inside a room with a 1-cell margin all round
            ox = oy = 1
            rs = {nm: [(x + ox, y + oy) for x, y in v] for nm, v in slots.items()}
            for W in range(w + 2, w + 6):
                for H in range(h + 2, h + 6):
                    got = feasible(rs, W, H, ox, oy)
                    if got:
                        return (w, h, rot, spare_at, W, H, got)
    return None


if __name__ == '__main__':
    for U in (1, 2, 3, 4):
        for spares in (0, 1, 2, 3, 4):
            P = 6 * U + 4 + spares
            found = []
            for w in range(2, P):
                h = (P + 4) // 2 - w
                if h < 2 or 2 * (w + h) - 4 != P:
                    continue
                r = try_shape(w, h, U, spares)
                if r:
                    found.append(r)
            tpm = P / U
            tag = 'OK ' if found else '-- '
            print(f'{tag}U={U} spares={spares}  P={P}  {tpm:.2f} ticks/MAC  '
                  f'{len(found)} shape(s)')
            for f in found[:2]:
                print(f'      ring {f[0]}x{f[1]} rot={f[2]} spares_at={f[3]} '
                      f'room {f[4]}x{f[5]} attach {f[6]}')
