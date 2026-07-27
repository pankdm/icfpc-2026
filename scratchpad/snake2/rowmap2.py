"""Per-block row usage: patch block()/endblock() by tracing R.y at each wrap."""
import importlib.util, json, os, sys, tempfile
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold5.py")
DEF = {"CW": 51, "ST_OUT": 22, "FEED_W": 27, "LOOPR": 38, "ST_X0": 19,
       "D_REP": 6, "HW_RET": 47, "HW_TICK": 36, "HW_SPAWN": 48, "HW_DIR": 35,
       "D_EAT": 31, "D_NOEAT": 22, "DRV_OUT": 50, "DRVX": 4, "D_HY": 7}
DEF.update(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {})
spec = importlib.util.spec_from_file_location("bfx", BUILDER)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.MIN_CAP = 51

log = []
orig_wrap = m.Emit.wrap
orig_seq = m.Emit.seq


def wrap(self):
    log.append(("wrap", self.y, self.x, self.d))
    return orig_wrap(self)


def seq(self, toks):
    log.append(("seq", self.y, len(toks), toks[:4]))
    return orig_seq(self, toks)


m.Emit.wrap = wrap
m.Emit.seq = seq
fd, p = tempfile.mkstemp(suffix=".man"); os.close(fd)
prog, cap, n = m.fit(save_to=p, **DEF)
os.unlink(p)
print("footprint", prog.footprint(), "rows", n, "cap", cap)
half = len(log) // 2
# find where the second build starts: first 'seq' after the midpoint reset
starts = [i for i, e in enumerate(log) if e[0] == "seq" and e[1] <= 12]
second = starts[len(starts) // 2] if len(starts) > 1 else 0
nw = 0
for e in log[second:]:
    if e[0] == "wrap":
        nw += 1
    else:
        print("row %3d  seq(%2d) %s   [wraps since: %d]" % (e[1], e[2], e[3], nw))
        nw = 0
print("total wraps in second build:", sum(1 for e in log[second:] if e[0] == "wrap"))
