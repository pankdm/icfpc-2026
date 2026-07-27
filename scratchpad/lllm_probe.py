"""Probe the v2 floorplan: how many rows are code vs below-room infrastructure."""
import sys, os
HERE = '/Users/visenbaev/icfpc26/s4/solutions/little-little-little-man'
sys.path.insert(0, HERE)
sys.path.insert(0, '/Users/visenbaev/icfpc26/s4/tools')
import lllm_layout as LL

_orig = LL.Lay.build_rooms


def main():
    import build2_man as BM

    def wrap(self):
        print("code maxy =", self.maxy)
        r = BM_build_rooms(self)
        print("SOUTH =", self.SOUTH)
        return r

    # build2_man installs its own build_rooms at import-of-main time; patch after
    sys.argv = ['x', '/tmp/probe.man', '--gw', '215']
    real_main = BM.main

    def patched():
        real_main()
    # easier: just call main then inspect
    BM.main()


if __name__ == '__main__':
    import build2_man as BM
    sys.argv = ['x', '/tmp/probe.man', '--gw', '215']
    orig_lay = None
    BM.main()
    txt = open('/tmp/probe.man').read().splitlines()
    # find the code room's bottom wall: the first full '=' or '-' row after row 0
    for i, row in enumerate(txt):
        stripped = row.rstrip()
        if i and stripped and set(stripped) <= set('+-=| '):
            print("wall-ish row", i, len(stripped))
    print("total rows", len(txt))
