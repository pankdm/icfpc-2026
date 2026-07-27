#!/usr/bin/env python3
"""12x12 floorplan search for the FIVE-row sort-numbers main room (main5.BASE).

Rooms: main 10x7 (interior 8x5), relay 5x4 or 4x5, input 3x3, output 3x3 = 118
cells, leaving 26... no: 70+20+9+9 = 108, leaving 36 free cells for pipes.

Constraints checked before routing:
  * the INPUT pipe's terminal must flow in the direction that makes `U` step onto
    the lap chain (south wall, pointing north, in the base orientation);
  * input terminal < return terminal in reading order (main's `R` takes the first
    ready pipe in reading order and lap 1 must drain input);
  * `q`'s nearest incoming pipe is the return pipe;
  * the two arm `s` cells bind to the relay pipe, the exit `s` to the output pipe;
  * the main->relay pipe is exactly 2 cells (q reads the circulating count only
    ~7 ticks after the last send; a longer pipe makes it undercount);
  * the return pipe alone holds n-1 = 15 values.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import main5
import search as S

BOX = S.BOX
CWD = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}


def rotdir(d, times):
    for _ in range(times % 4):
        d = CWD[d]
    return d


def places(w, h, occ):
    for y in range(BOX - h + 1):
        for x in range(BOX - w + 1):
            r = (x, y, x + w - 1, y + h - 1)
            if not (S.rect_cells(r) & occ):
                yield r


def plans():
    for rot in (0, 1, 2, 3):
        mgrid, roles = main5.rotate(main5.BASE, main5.ROLE, rot)
        udir = rotdir((0, -1), rot)
        iw, ih = len(mgrid[0]), len(mgrid)
        for mrect in places(iw + 2, ih + 2, set()):
            mc = S.rect_cells(mrect)
            arole = {k: (mrect[0] + 1 + v[0], mrect[1] + 1 + v[1]) for k, v in roles.items()}
            for rshape in ((5, 4), (4, 5)):
                for rrect in places(rshape[0], rshape[1], mc):
                    rc = mc | S.rect_cells(rrect)
                    for irect in places(3, 3, rc):
                        ic = rc | S.rect_cells(irect)
                        for orect in places(3, 3, ic):
                            yield mgrid, arole, udir, {
                                'main': mrect, 'relay': rrect,
                                'inp': irect, 'outp': orect}


def assignments(plan, arole, udir, cap):
    msrc = plan.srcs('main')
    mdst = plan.dsts('main')
    if not (msrc and mdst):
        return []
    out = []
    for (rs, rsd) in msrc:
        for (os_, osd) in msrc:
            if os_ == rs:
                continue
            cands = [('relay', rs), ('outp', os_)]
            if S.nearer(cands, arole['s_less']) != 'relay':
                continue
            if S.nearer(cands, arole['s_gtr']) != 'relay':
                continue
            if S.nearer(cands, arole['s_exit']) != 'outp':
                continue
            for (idst, idd) in mdst:
                if idd != udir or idst in (rs, os_):
                    continue
                for (rd, rdd) in mdst:
                    if rd in (rs, os_, idst):
                        continue
                    if (idst[1], idst[0]) >= (rd[1], rd[0]):
                        continue
                    if S.nearer([('ret', rd), ('in', idst)], arole['q']) != 'ret':
                        continue
                    out.append((rs, rsd, os_, osd, rd, rdd, idst, idd))
                    if len(out) >= cap:
                        return out
    return out


def build(plan, mgrid, asg):
    """main->relay first (it must stay short: 'q' reads the circulating count only
    ~11 ticks after the last send, and the relay adds up to 6 ticks of latency),
    then the >=15-cell return pipe as long as possible, then output and input."""
    rs, rsd, os_, osd, rd, rdd, idst, idd = asg
    reserved = {rs, os_, idst}
    for (rld, rldd) in plan.dsts('relay'):
        if rld in reserved or rld == rd:
            continue
        for p2 in S.route(plan, rs, rsd, rld, rldd, {rd, idst, os_}, 2, 6,
                          want=4, budget=40000):
            u2 = set(p2[0])
            rets = []
            for (rls, rlsd) in plan.srcs('relay'):
                if rls in u2 or rls in (os_, idst, rd):
                    continue
                rets += [(rlsd, p) for p in S.route(plan, rls, rlsd, rd, rdd,
                                                    u2 | {os_, idst}, 15, 22,
                                                    want=300, budget=400000)]
            rets.sort(key=lambda t: len(t[1][0]))
            for (_, p1) in rets[:60]:
                u1 = u2 | set(p1[0])
                for (od, odd) in plan.dsts('outp'):
                    if od in u1 or od in (os_, idst):
                        continue
                    for p3 in S.route(plan, os_, osd, od, odd, u1 | {idst}, 2, 14,
                                      want=3, budget=40000):
                        u3 = u1 | set(p3[0])
                        for (isr, isd) in plan.srcs('inp'):
                            if isr in u3:
                                continue
                            for p4 in S.route(plan, isr, isd, idst, idd, u3, 2, 18,
                                              want=2, budget=40000):
                                txt = S.render(plan, mgrid, rldd, [p1, p2, p3, p4])
                                if txt:
                                    return txt
    return None


def grade(path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'grade_fast.py'),
                        'sort-numbers', path], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default=os.path.join(HERE, 'out5'))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    seen = set()
    n = w = 0
    best = None
    for mgrid, arole, udir, rooms in plans():
        n += 1
        plan = S.Plan(rooms)
        if len(plan.free) < 21:
            continue
        for asg in assignments(plan, arole, udir, 30):
            txt = build(plan, mgrid, asg)
            if not txt or txt in seen:
                continue
            seen.add(txt)
            p = os.path.join(args.outdir, 'c%04d.man' % w)
            open(p, 'w').write(txt)
            w += 1
            res = grade(p)
            if res and res.get('passed') == res.get('total'):
                print('PASS', p, res['score'], res['avgTicks'], flush=True)
                if best is None or res['score'] < best[0]:
                    best = (res['score'], p)
            elif res:
                print('fail %s %s/%s %s' % (p, res.get('passed'), res.get('total'),
                                            res['results'][0].get('reason')), flush=True)
            break
        if n % 20000 == 0:
            print('plans=%d wrote=%d' % (n, w), flush=True)
    print('DONE plans=%d wrote=%d best=%s' % (n, w, best))


if __name__ == '__main__':
    main()
