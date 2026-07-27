"""Print every room's box and attachment cells for a candidate floor plan.

Attachment geometry inside each room is part of the VERIFIED configuration
(mm2rooms.py), so a re-layout may only translate rooms -- never move an
attachment along its wall. This dumps the cells a translation would produce so
the corridor lanes can be written against real numbers.
"""
import sys
sys.path.insert(0, 'solutions/matmul')
sys.path.insert(0, 'tools')
import mm2rooms as R
import router as RT
from mm2lib import RGrid


def dump(plan):
    rt = RT.Router()
    g = RGrid(rt)
    rt.add_input_room(*plan['I'])
    rooms = {}
    rooms['spl'] = R.spl(g, *plan['spl'])
    rooms['brel'] = R.brel(g, *plan['brel'])
    rooms['pcnt'] = R.pcnt(g, *plan['pcnt'])
    rooms['pcnt'].attach('CP', 'L', plan['pcnt_cp'], 'in')
    rooms['arel'] = R.arel(g, *plan['arel'])
    rooms['arel'].attach('AP', 'L', plan['arel_ap'], 'in')
    rooms['arel'].attach('AR', 'R', plan['arel_ar'], 'out')
    rooms['mul'] = R.mul(g, *plan['mul'])
    rooms['crel'] = R.crel(g, *plan['crel'])
    rooms['crel'].attach('CF', 'B', plan['crel_cf'], 'in')
    rooms['crel'].attach('CR', 'L', plan['crel_cr'], 'out')
    rooms['acc'] = R.acc(g, *plan['acc'])
    rooms['acc'].attach('CTL', 'B', plan['acc_ctl'], 'in')
    for nm, r in rooms.items():
        print(f'{nm:5s} x {r.x}..{r.x + r.w - 1}  y {r.y}..{r.y + r.h - 1}')
        for n, p in sorted(r.pipes.items()):
            print(f'      {n:4s} att {p[0], p[1]}  wall {r.walls[n]}')
    print('O room', plan['O'])


BASE = dict(I=(12, -3), spl=(12, 2), brel=(-16, 46), pcnt=(32, 20), pcnt_cp=24,
            arel=(12, 36), arel_ap=40, arel_ar=40, mul=(12, 48), crel=(24, 66),
            crel_cf=26, crel_cr=68, acc=(24, 48), acc_ctl=33, O=(44, 49))

if __name__ == '__main__':
    dump(BASE)
