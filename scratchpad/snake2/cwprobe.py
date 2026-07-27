"""What does each CW give: capacity, footprint, build error?"""
import importlib.util, sys, os, tempfile
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
spec = importlib.util.spec_from_file_location("bf2", REPO + "/solutions/snake/build_fold2_tuned.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.MIN_CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 51
BEST = {'CW': 53, 'ST_OUT': 23, 'FEED_W': 27, 'LOOPR': 40, 'ST_X0': 19, 'D_REP': 10,
        'D_HX': 9, 'HW_RET': 49, 'HW_TICK': 36, 'HW_SPAWN': 50, 'HW_DIR': 37,
        'D_EAT': 32, 'D_NOEAT': 33, 'DRV_OUT': 52, 'DRVX': 4, 'D_COLL': 3}
for cw in range(45, 58):
    kw = dict(BEST); kw["CW"] = cw
    fd, path = tempfile.mkstemp(suffix=".man"); os.close(fd)
    try:
        prog, cap, nrows = m.fit(save_to=path, **kw)
        print("CW=%2d cap=%2d rows=%3d footprint=%s" % (cw, cap, nrows, prog.footprint()))
    except Exception as e:
        print("CW=%2d FAIL %s: %s" % (cw, type(e).__name__, str(e)[:90]))
    finally:
        os.unlink(path)
