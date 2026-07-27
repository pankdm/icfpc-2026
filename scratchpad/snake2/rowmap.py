"""Rows consumed per controller block, by tracing block()/endblock()."""
import importlib.util, json, os, sys, tempfile
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold5.py")
KW = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
DEF = dict(CW=52, ST_OUT=23, FEED_W=28, LOOPR=39, ST_X0=19, D_REP=6,
           HW_RET=48, HW_TICK=37, HW_SPAWN=49, HW_DIR=36, D_EAT=32,
           D_NOEAT=23, DRV_OUT=51, DRVX=4, D_HY=7)
DEF.update(KW)
spec = importlib.util.spec_from_file_location("bfx", BUILDER)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.MIN_CAP = 51

marks = []
orig_take = m.Rows.take


def take(self, n=1):
    y = orig_take(self, n)
    marks.append(y)
    return y


m.Rows.take = take
fd, p = tempfile.mkstemp(suffix=".man"); os.close(fd)
prog, cap, n = m.fit(save_to=p, **DEF)
os.unlink(p)
print("footprint", prog.footprint(), "rows", n)
# marks accumulate over BOTH fit() builds; keep the second half
half = len(marks) // 2
ys = marks[half:]
print("row cursor sequence (second build):")
print(" ", ys)
