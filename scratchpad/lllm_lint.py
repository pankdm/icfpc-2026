"""Run manlint's structural checks on a build3 grid (needs the live Program)."""
import os
import sys

ROOT = '/Users/visenbaev/icfpc26'
sys.path.insert(0, os.path.join(ROOT, 's4', 'solutions', 'little-little-little-man'))
sys.path.insert(0, os.path.join(ROOT, 's4', 'tools'))
import manlint                       # noqa: E402
import build3_man as B3               # noqa: E402


def main():
    sys.argv = ['build3_man.py'] + sys.argv[1:]
    prog_holder = {}
    real_save = None

    import littleman as lm
    orig_save = lm.Program.save

    def save(self, path):
        prog_holder['p'] = self
        return orig_save(self, path)
    lm.Program.save = save
    B3.main()
    p = prog_holder['p']
    print("bad_overwrites   :", manlint.bad_overwrites(p)[:5])
    print("room_over_pipe   :", manlint.room_over_pipe(p)[:5])
    print("dangling_pipes   :", manlint.dangling_pipes(p))
    rows = p.render().splitlines()
    print("literal_faults   :", manlint.literal_faults(rows)[:5])
    print("check()          :", manlint.check(p))


if __name__ == '__main__':
    main()
