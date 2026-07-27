"""Build one fold5 candidate to /tmp/fold5.man and grade + stress-gate it."""
import importlib.util, json, os, sys, tempfile
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
sys.path.insert(0, "/Users/visenbaev/icfpc26/scratchpad/snake2")

BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold5.py")
KW = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
OUTMAN = sys.argv[2] if len(sys.argv) > 2 else "/tmp/fold5.man"
DEF = dict(CW=52, ST_OUT=23, FEED_W=28, LOOPR=39, ST_X0=19, D_REP=12,
           HW_RET=48, HW_TICK=37, HW_SPAWN=31, HW_DIR=36, D_EAT=32,
           D_NOEAT=23, DRV_OUT=51, DRVX=4)
DEF.update(KW)
spec = importlib.util.spec_from_file_location("bfx", BUILDER)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.MIN_CAP = 51
prog, cap, n = m.fit(save_to=OUTMAN, **DEF)
print("footprint", prog.footprint(), "cap", cap, "rows", n)
import grade_fast
r = grade_fast.grade("snake", OUTMAN, cap=200000, jobs=5)
print("public", r.get("passed"), "/", r.get("total"), "score", r.get("score"), "ticks", r.get("avgTicks"))
if r.get("passed") == r.get("total"):
    sys.argv = [sys.argv[0]]
    import search4 as S
    S._init()
    print("quick gate:", S._run_cases(OUTMAN, S._QUICK) or "OK")
    print("full gate:", S._run_cases(OUTMAN, S._FULL) or "OK")
