"""Trade band rows (CY0) for controller width (CW): height is not the binder."""
import importlib.util, json, os, sys, tempfile
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold5.py")
DEF = dict(CW=52, ST_OUT=23, FEED_W=28, LOOPR=39, ST_X0=19, D_REP=6,
           HW_RET=48, HW_TICK=37, HW_SPAWN=49, HW_DIR=36, D_EAT=32,
           D_NOEAT=23, DRV_OUT=51, DRVX=4, D_HY=7)
SHIFT = ['LOOPR', 'HW_RET', 'HW_TICK', 'HW_SPAWN', 'HW_DIR', 'D_EAT', 'D_NOEAT',
         'DRV_OUT']
spec = importlib.util.spec_from_file_location("bfx", BUILDER)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.MIN_CAP = 51
for cy in (7, 8, 9, 10, 11, 12):
    for cw in range(44, 54):
        kw = dict(DEF)
        d = cw - DEF["CW"]
        kw["CW"] = cw
        kw["CY0"] = cy
        for k in SHIFT:
            kw[k] += d
        fd, p = tempfile.mkstemp(suffix=".man"); os.close(fd)
        try:
            prog, cap, n = m.fit(save_to=p, **kw)
            print("CY0=%2d CW=%2d cap=%2d %s" % (cy, cw, cap, prog.footprint()))
        except Exception as e:
            print("CY0=%2d CW=%2d FAIL %s" % (cy, cw, str(e)[:70]))
        finally:
            os.unlink(p)
