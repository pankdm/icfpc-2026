"""Build-only sweep reporting (w,h): find the SHORTEST controller at each width,
because after shrink the height is what binds."""
import importlib.util, json, os, sys, tempfile
REPO = "/Users/visenbaev/icfpc26/.claude/worktrees/snake2"
sys.path.insert(0, REPO + "/tools")
BASE = json.load(open("/Users/visenbaev/icfpc26/scratchpad/snake2/w46_15_22.json"))["params"]
SHIFT = ['LOOPR','HW_RET','HW_TICK','HW_SPAWN','HW_DIR','D_EAT','D_NOEAT','DRV_OUT']
spec = importlib.util.spec_from_file_location("bfx", os.environ["SNAKE_BUILDER"])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.MIN_CAP = 51
best = {}
for cw in range(43, 49):
  for st in range(8, 21):
    for gap in (3, 4):
      for fw in range(st + 3, st + 13):
        for cy in (7, 8, 9):
          kw = dict(BASE); d = cw - BASE["CW"]; kw["CW"] = cw; kw["CY0"] = cy
          for k in SHIFT: kw[k] += d
          kw["ST_X0"] = st; kw["ST_OUT"] = st + gap; kw["ST_IN"] = st + gap + 1
          kw["FEED_W"] = fw
          fd, p = tempfile.mkstemp(suffix=".man"); os.close(fd)
          try:
              prog, cap, n = m.fit(save_to=p, **kw)
              w, h, box = prog.footprint()
              k2 = (w, h)
              if k2 not in best:
                  best[k2] = kw
          except Exception:
              pass
          finally:
              os.unlink(p)
for (w, h), kw in sorted(best.items(), key=lambda kv: max(kv[0])**2):
    print("%dx%d box %d  CW=%d CY0=%d ST_X0=%d FEED_W=%d" %
          (w, h, max(w, h)**2, kw["CW"], kw["CY0"], kw["ST_X0"], kw["FEED_W"]))
