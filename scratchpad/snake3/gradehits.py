"""Grade the side-filtered survivors from sidehunt.py, cheapest gate first.

Order matters: the 5 public cases are 5 engine runs and reject most candidates,
the 53-case QUICK stress gate is 53 more and only the ones that already beat the
incumbent's ticks are worth paying for.
"""
import importlib.util, json, os, sys, tempfile
import multiprocessing as mp

REPO = "/Users/dmitrykorolev/projects/icfpc-2026-main"
sys.path.insert(0, REPO + "/tools")
OUT = REPO + "/scratchpad/snake3"
HITS = sys.argv[1] if len(sys.argv) > 1 else OUT + "/side73.json"
INCUMBENT = float(sys.argv[2]) if len(sys.argv) > 2 else 38720514.0
BUILDER = os.environ.get("SNAKE_BUILDER", REPO + "/solutions/snake/build_fold6.py")
JOBS = int(os.environ.get("SNAKE_JOBS", "4"))
LM = REPO + "/interp/target/release/lm"

_mod = _gf = _QUICK = None


def _init():
    global _mod, _gf, _QUICK
    if _mod is None:
        spec = importlib.util.spec_from_file_location("bsnake", BUILDER)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        import grade_fast
        _gf = grade_fast
        st = json.load(open(REPO + "/scratchpad/snake2/stress.json"))
        must = {"grow-50", "grow-45-then-selfhit", "grow-40", "long-lap",
                "grow-30-then-selfhit"}
        _QUICK = [c for c in st if c["nrounds"] <= 14 or c["name"] in must]


def _stress(path):
    import subprocess
    for c in _QUICK:
        p = subprocess.run([LM, "--grade", path, "--input=" + c["input"],
                            "--expected=" + c["expected"], "--cap=60000",
                            "--frames=" + c["frames"]],
                           capture_output=True, text=True, timeout=300)
        try:
            v = json.loads((p.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return c["name"]
        if v.get("status") != "pass":
            return c["name"]
    return None


def _work(params):
    _init()
    fd, path = tempfile.mkstemp(suffix=".man", dir="/tmp")
    os.close(fd)
    try:
        try:
            prog, cap, nrows = _mod.fit(save_to=path, **params)
        except Exception:
            return None
        w, h, box = prog.footprint()
        r = _gf.grade("snake", path, cap=60000, jobs=1)
        if r.get("passed") != r.get("total") or not r.get("total"):
            return None
        if r["score"] >= INCUMBENT:
            return None
        bad = _stress(path)
        if bad is not None:
            return ("STRESSFAIL", bad, r["score"])
        return (r["score"], box, r["avgTicks"], cap, params, open(path).read())
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def main():
    hits = json.load(open(HITS))
    print("grading %d candidates against incumbent %d" % (len(hits), INCUMBENT),
          flush=True)
    pool = mp.Pool(JOBS)
    best = None
    for res in pool.imap_unordered(_work, [h["params"] for h in hits]):
        if not res:
            continue
        if res[0] == "STRESSFAIL":
            print("  stress-fail %-24s (would have scored %d)" % (res[1], res[2]),
                  flush=True)
            continue
        print("  PASS score %d box %d ticks %.0f cap %d" %
              (res[0], res[1], res[2], res[3]), flush=True)
        if best is None or res[0] < best[0]:
            best = res
            json.dump({"params": res[4], "score": res[0], "box": res[1],
                       "ticks": res[2], "cap": res[3]},
                      open(OUT + "/hitbest.json", "w"), indent=1)
            open(OUT + "/hitbest.man", "w").write(res[5])
    print("BEST", best[0] if best else None, flush=True)


if __name__ == "__main__":
    main()
