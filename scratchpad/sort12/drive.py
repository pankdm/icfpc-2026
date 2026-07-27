#!/usr/bin/env python3
"""Driver for the 12x12 sort-numbers floorplan search.  Writes candidates to
scratchpad/sort12/out/ and grades them with the Rust engine.

usage: python3 drive.py [--max N] [--stop-on-pass]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import mainroom
import search as S

BOX = S.BOX


def placements(w, h, occ):
    for y in range(BOX - h + 1):
        for x in range(BOX - w + 1):
            r = (x, y, x + w - 1, y + h - 1)
            if not (S.rect_cells(r) & occ):
                yield r


def plans():
    for rot in (0, 1, 2, 3):
        mgrid, roles = mainroom.rotate(mainroom.BASE, mainroom.ROLE, rot)
        iw, ih = len(mgrid[0]), len(mgrid)
        for mrect in placements(iw + 2, ih + 2, set()):
            mc = S.rect_cells(mrect)
            arole = {k: (mrect[0] + 1 + v[0], mrect[1] + 1 + v[1]) for k, v in roles.items()}
            for rshape in ((5, 4), (4, 5)):
                for rrect in placements(rshape[0], rshape[1], mc):
                    rc = mc | S.rect_cells(rrect)
                    for irect in placements(3, 3, rc):
                        ic = rc | S.rect_cells(irect)
                        for orect in placements(3, 3, ic):
                            yield mgrid, arole, {'main': mrect, 'relay': rrect,
                                                 'inp': irect, 'outp': orect}


def solve(mgrid, arole, rooms, budget):
    plan = S.Plan(rooms)
    if len(plan.free) < 21:
        return []
    msrc = plan.srcs('main')
    mdst = plan.dsts('main')
    rsrc = plan.srcs('relay')
    rdst = plan.dsts('relay')
    isrc = plan.srcs('inp')
    odst = plan.dsts('outp')
    if not (msrc and mdst and rsrc and rdst and isrc and odst):
        return []
    out = []
    # 1. which main source feeds the relay, which feeds output
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
            # 2. which main terminal is the return pipe, which is input
            for (rd, rdd) in mdst:
                if rd in (rs, os_):
                    continue
                for (idst, idd) in mdst:
                    if idst in (rs, os_, rd):
                        continue
                    if (idst[1], idst[0]) >= (rd[1], rd[0]):
                        continue                      # input must read first
                    if S.nearer([('ret', rd), ('in', idst)], arole['q']) != 'ret':
                        continue
                    out.append((plan, rs, rsd, os_, osd, rd, rdd, idst, idd))
                    if len(out) >= budget:
                        return out
    return out


SHORT = 8          # cap on the three short pipes


def build(plan, mgrid, asg, verbose=False):
    """Route the three SHORT pipes first (few options, must not hog cells), then
    the >=15-cell return pipe out of whatever free cells remain."""
    _, rs, rsd, os_, osd, rd, rdd, idst, idd = asg
    out = []
    reserved = {rd, idst}
    for (rld, rldd) in plan.dsts('relay'):
        if rld in reserved or rld in (rs, os_):
            continue
        for p2 in S.route(plan, rs, rsd, rld, rldd, reserved | {os_}, 2, SHORT,
                          want=6, budget=40000):
            u2 = set(p2[0])
            for (od, odd) in plan.dsts('outp'):
                if od in u2 or od in reserved or od == os_:
                    continue
                for p3 in S.route(plan, os_, osd, od, odd, u2 | reserved, 2, SHORT,
                                  want=4, budget=40000):
                    u3 = u2 | set(p3[0])
                    for (isr, isd) in plan.srcs('inp'):
                        if isr in u3 or isr == rd:
                            continue
                        for p4 in S.route(plan, isr, isd, idst, idd, u3 | {rd}, 2, 20,
                                          want=3, budget=40000):
                            u4 = u3 | set(p4[0])
                            for (rls, rlsd) in plan.srcs('relay'):
                                if rls in u4 or rls == rd:
                                    continue
                                best = S.route_long(plan, rls, rlsd, rd, rdd, u4,
                                                    S.RET_MIN, 30, budget=250000)
                                if not best:
                                    continue
                                txt = S.render(plan, mgrid, rldd,
                                               [best, p2, p3, p4])
                                if txt:
                                    out.append(txt)
                                    return out
    return out


def grade(path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'grade_fast.py'),
                        'sort-numbers', path], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=10 ** 9)
    ap.add_argument('--outdir', default=os.path.join(HERE, 'out'))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    seen = set()
    nplans = ncand = nwrote = 0
    best = None
    for mgrid, arole, rooms in plans():
        nplans += 1
        if nplans > args.max:
            break
        for asg in solve(mgrid, arole, rooms, 40):
            ncand += 1
            for txt in build(asg[0], mgrid, asg):
                if txt in seen:
                    continue
                seen.add(txt)
                p = os.path.join(args.outdir, 'c%04d.man' % nwrote)
                open(p, 'w').write(txt)
                nwrote += 1
                res = grade(p)
                if res and res.get('passed') == res.get('total'):
                    print('PASS', p, res['score'], res['avgTicks'])
                    if best is None or res['score'] < best[0]:
                        best = (res['score'], p)
                elif res:
                    print('fail %s %d/%d' % (p, res.get('passed', 0), res.get('total', 0)))
        if nplans % 20000 == 0:
            print('plans=%d cands=%d wrote=%d' % (nplans, ncand, nwrote), flush=True)
    print('DONE plans=%d cands=%d wrote=%d best=%s' % (nplans, ncand, nwrote, best))


if __name__ == '__main__':
    main()
