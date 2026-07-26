#!/usr/bin/env python3
"""autotune_batch.py — point autotune.py at the WHOLE repo, unattended, and report.

tools/autotune.py tunes ONE builder. Finding out which of the ~130 `solutions/*/*.py`
files are even tunable, and in which order they are worth the machine's time, is its own
job — so this does that job and then drives autotune.py as a subprocess.

    python3 tools/autotune_batch.py                     discover, plan, sweep, report
    python3 tools/autotune_batch.py --discover-only     just phase 1 + the plan
    python3 tools/autotune_batch.py --plan-only         discover + print the plan, no sweep

THREE PHASES

  1. DISCOVERY  every solutions/<slug>/*.py that is not obviously a helper gets
     `autotune.py <slug> <file> --dry-run` (parallel, timeouted). That answers, cheaply
     and for real: does the baseline build? does it pass every public case? does it
     reproduce a committed .man? how many knobs are there? Cached to
     tests/autotune-discovery.json keyed by source hash, so a re-run is instant.

  2. RANKING    problems are worth sweeping in proportion to the points still on the
     table, which `tools/ours.py` prints as its `lost` column (cached to
     tests/autotune-points.json — it needs the network). Within a problem, a builder that
     reproduces its committed .man and scores lowest IS the champion's source, so it is
     the one whose knobs matter; the other variants are dead branches.

  3. EXECUTION  one problem at a time with --jobs 6. Each sweep is already internally
     parallel, so running two at once just makes both slower on an 8-core box.

RESUMABILITY  every finished (slug, builder) is written to tests/autotune-report.json the
moment it finishes. A re-run skips anything already recorded, so an interrupted sweep
resumes instead of restarting. --force re-runs everything.

NOTHING HERE CAN BREAK A SOLUTION: autotune.py builds in a temp sandbox and only ever
writes *-tuned.man / *_tuned.py, and this script never writes into solutions/ at all.
"""
import argparse
import concurrent.futures as futures
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCOVERY = os.path.join(REPO, "tests", "autotune-discovery.json")
POINTS = os.path.join(REPO, "tests", "autotune-points.json")
REPORT = os.path.join(REPO, "tests", "autotune-report.json")
LOGS = os.path.join(REPO, "tests", "autotune-logs")

# Files that are named like builders but are not: previously-tuned artifacts, the shared
# grid DSLs, the pure-python models/simulators used to design a layout, and the one-off
# analysis scripts. Every one of these would cost a dry-run to reject, and the reject
# would be indistinguishable from a genuinely broken builder in the report.
NOT_A_BUILDER = re.compile(
    r"(_tuned\.py$|^dsl\d*\.py$|_dsl\.py$|model|_sim\.py$|^algsim\.py$|trace\.py$"
    r"|^analyze_|^verify_|^generate|metrics|_reference\.py$|^router\.py$)")


def sh(cmd, timeout, cwd=REPO):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or ""), False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"") + (e.stderr or b"")
        return -1, out.decode("utf-8", "replace") if isinstance(out, bytes) else str(out), True


def load(path, default):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"), indent=1)
    os.replace(tmp, path)


def money(s):
    return int(s.replace(",", "")) if s else None


# ── phase 1: discovery ───────────────────────────────────────────────────────
RE_BASE = re.compile(r"^\s+(\d+)/(\d+)\s+box (\d+)x(\d+)=(\d+)\s+ticks (\d+)\s+score ([\d,]+)\s+\[(.+)\]")
RE_FAIL = re.compile(r"^\s+FAIL (\d+)/(\d+)\s+box (\d+)x(\d+)=(\d+)\s*\[(.+)\]")
RE_REPRO = re.compile(r"reproduces committed (.+): (yes|NO)")
RE_KNOBS = re.compile(r"^knobs \((\d+), scope=")
RE_MACROS = re.compile(r"^macro knobs \((\d+)\)")


def parse_baseline(out):
    """Everything autotune's --dry-run tells us about a builder, as a dict."""
    d = {"ok": False, "error": None, "knobs": 0, "macros": 0, "reproduces": None,
         "target": None, "score": None, "passed": None, "total": None, "box": None,
         "ticks": None}
    for line in out.splitlines():
        m = RE_BASE.match(line)
        if m:
            d.update(ok=True, passed=int(m[1]), total=int(m[2]), box=int(m[5]),
                     ticks=int(m[6]), score=money(m[7]), target=m[8].strip())
            continue
        m = RE_FAIL.match(line)
        if m:
            d.update(passed=int(m[1]), total=int(m[2]), box=int(m[5]),
                     target=m[6].strip(), error=f"baseline fails {m[1]}/{m[2]} cases")
            continue
        m = RE_REPRO.search(line)
        if m:
            d["reproduces"] = (m[2] == "yes")
            continue
        m = RE_KNOBS.match(line)
        if m:
            d["knobs"] = int(m[1])
            continue
        m = RE_MACROS.match(line)
        if m:
            d["macros"] = int(m[1])
    if not d["ok"] and not d["error"]:
        # the one-line reason autotune printed in place of a baseline
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("builder ") or s.startswith("grade") or "Error" in s:
                d["error"] = s[:120]
                break
        d["error"] = d["error"] or "no baseline (autotune refused)"
    return d


def probe(slug, rel, timeout):
    t0 = time.time()
    rc, out, timedout = sh([sys.executable, "tools/autotune.py", slug, rel, "--dry-run"], timeout)
    d = parse_baseline(out) if not timedout else {
        "ok": False, "error": f"dry-run timeout ({timeout}s)", "knobs": 0, "macros": 0,
        "reproduces": None, "target": None, "score": None, "passed": None, "total": None,
        "box": None, "ticks": None}
    d.update(slug=slug, builder=rel, elapsed=round(time.time() - t0, 1))
    return d


def source_key(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:16]


def discover(args):
    cache = load(DISCOVERY, {})
    files, skipped = [], []
    for slug in sorted(os.listdir(os.path.join(REPO, "solutions"))):
        sdir = os.path.join(REPO, "solutions", slug)
        if not os.path.isdir(sdir):
            continue
        for name in sorted(os.listdir(sdir)):
            if not name.endswith(".py"):
                continue
            rel = f"solutions/{slug}/{name}"
            if not args.no_skip and NOT_A_BUILDER.search(name):
                skipped.append(rel)
                continue
            files.append((slug, rel))

    todo = []
    for slug, rel in files:
        key = source_key(os.path.join(REPO, rel))
        hit = cache.get(rel)
        if hit and hit.get("sha") == key and not args.force_rediscover:
            continue
        todo.append((slug, rel, key))

    if todo:
        print(f"discovery: probing {len(todo)} builders "
              f"({len(files) - len(todo)} cached, {len(skipped)} skipped as helpers) …")
        done = 0
        with futures.ThreadPoolExecutor(max_workers=args.discover_jobs) as ex:
            jobs = {ex.submit(probe, s, r, args.discover_timeout): (s, r, k) for s, r, k in todo}
            for f in futures.as_completed(jobs):
                slug, rel, key = jobs[f]
                try:
                    d = f.result()
                except Exception as e:                       # a builder's problem, not ours
                    d = {"slug": slug, "builder": rel, "ok": False, "knobs": 0, "macros": 0,
                         "reproduces": None, "error": f"{type(e).__name__}: {e}"}
                d["sha"] = key
                cache[rel] = d
                done += 1
                if done % 10 == 0 or done == len(todo):
                    print(f"  {done}/{len(todo)}")
        save(DISCOVERY, cache)
    else:
        print(f"discovery: all {len(files)} builders cached ({len(skipped)} skipped as helpers)")

    live = {rel: cache[rel] for _s, rel in files if rel in cache}
    return live, skipped


# ── phase 2: ranking ─────────────────────────────────────────────────────────
def lost_points(refresh):
    """{slug: points still available}. ours.py needs the network, so the answer is cached
    and a network failure degrades to the last known table rather than aborting the sweep."""
    cached = load(POINTS, None)
    if cached and not refresh:
        return cached, "cached"
    rc, out, _ = sh([sys.executable, "tools/ours.py"], 180)
    names = {}
    try:
        sys.path.insert(0, os.path.join(REPO, "tools"))
        import lib
        names = {(p.get("name") or p["slug"]): p["slug"] for p in lib.list_problems()}
    except Exception:
        pass
    table = {}
    for line in out.splitlines():
        m = re.match(r"^(.{1,21}?)\s{2,}\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+[\d.]+\s+([\d.]+)\s*$", line)
        if not m or m[1].strip() in ("problem", "TOTAL"):
            continue
        name = m[1].strip()
        slug = names.get(name)
        if slug:
            table[slug] = float(m[2])
    if table:
        save(POINTS, table)
        return table, "live"
    return cached or {}, "unavailable"


RE_CHAMP = re.compile(r"^\*\s+(\S+)\s+(\S+\.man)\s+(\d+)/(\d+)\s+\S+\s+\S+\s+(\d+)")


def champions(slugs, refresh):
    """{slug: (best committed .man, its score)} — the bar a tuned artifact has to clear.

    A builder's own baseline is NOT that bar. Three of this repo's problems have a champion
    .man with no working builder behind it (hand-written, or from a builder that now crashes),
    so tuning the best *builder* can improve it 1.2x and still leave the result 20x worse than
    the .man already committed. Without this, the report calls that an improvement."""
    cache = load(os.path.join(REPO, "tests", "autotune-champions.json"), {})
    for slug in slugs:
        if slug in cache and not refresh:
            continue
        rc, out, _ = sh(["node", "tools/grade_all.js", "--slug", slug], 1800)
        for line in out.splitlines():
            m = RE_CHAMP.match(line.strip() and line)
            if m and m[1] == slug:
                cache[slug] = {"man": m[2], "score": int(m[5])}
                break
    save(os.path.join(REPO, "tests", "autotune-champions.json"), cache)
    return cache


def rank(live, points, args):
    """Best builders first. A problem's worth is the points still on it."""
    usable = [d for d in live.values() if d.get("ok") and (d.get("knobs") or d.get("macros"))]
    by_slug = {}
    for d in usable:
        by_slug.setdefault(d["slug"], []).append(d)
    plan = []
    for slug, ds in by_slug.items():
        # Inside a problem, the LOWEST-scoring builder is the one worth tuning: only a grid
        # that beats the current champion is worth anything, so a variant that starts 3x
        # behind would have to make up 3x before its first point of value. Reproducing the
        # committed .man is a trust signal (the builder really is the champion's source) but
        # only breaks ties — plotter's champion source is 3x better than the two builders
        # that do reproduce, and ordering on reproduction alone sends the budget there.
        ds.sort(key=lambda d: (d.get("score") or float("inf"), not d.get("reproduces"),
                               -(d.get("knobs", 0) + d.get("macros", 0))))
        for d in ds[:args.per_slug]:
            plan.append(dict(d, lost=points.get(slug, 0.0)))
    champ = champions(sorted(by_slug), args.refresh_champions) if not args.no_champions else {}
    for d in plan:
        c = champ.get(d["slug"])
        d["champion"] = c["man"] if c else None
        d["champion_score"] = c["score"] if c else None
        # how far this builder starts behind the best .man already committed
        d["behind"] = round((d["score"] or 0) / c["score"], 2) if c and c.get("score") else None
    plan.sort(key=lambda d: (-d["lost"], d.get("score") or 0))
    skip = set(args.skip.split(",")) if args.skip else set()
    for d in plan:
        reason = None
        if d["builder"] in skip:
            reason = "requested via --skip"
        elif d["behind"] and d["behind"] > args.max_behind:
            # tuning gains ~1.05-1.2x; a builder 20x behind the champion cannot reach it, so
            # every second spent on it is a second not spent where a win would count
            reason = f"{d['behind']:.0f}x behind champion {os.path.basename(d['champion'])}"
        d["skip_reason"] = reason
    return plan


# ── phase 3: execution ───────────────────────────────────────────────────────
RE_BEST = re.compile(r"^BEST ([\d,]+) -> ([\d,]+)\s+\(([\d.]+)x\)")
RE_ACC = re.compile(r"^\s+(\S+): (-?\d+) -> (-?\d+)\s+\(score ([\d,]+)\)")
RE_NOIMP = re.compile(r"^no improvement found \(baseline score ([\d,]+)\)")
RE_SCREEN = re.compile(r"^screened (\d+) knobs in ([\d.]+)s.*?searching (\d+)")
RE_WAVE = re.compile(r"^\s+(\d+) valid, (\d+) fail, (\d+) inert, (\d+) build-error")


def checkpoint_path(target):
    """Where autotune.checkpoint() drops its structured result for this target."""
    stem = os.path.splitext(os.path.basename(target))[0]
    if stem.endswith("-tuned"):
        stem = stem[:-len("-tuned")]
    return os.path.join(REPO, os.path.dirname(target), f"{stem}-tuned.json")


def parse_sweep(out):
    r = {"baseline_score": None, "best_score": None, "gain": None, "accepted": [],
         "candidates": 0, "screened": None, "screen_secs": None, "searched": None,
         "converged": False, "out_of_budget": False}
    base = parse_baseline(out)
    r["baseline_score"] = base.get("score")
    in_accept = False
    for line in out.splitlines():
        if line.startswith("converged") or "already tried — converged" in line:
            r["converged"] = True
        elif line.startswith("budget exhausted"):
            r["out_of_budget"] = True
        m = RE_SCREEN.match(line)
        if m:
            r["screened"], r["screen_secs"], r["searched"] = int(m[1]), float(m[2]), int(m[3])
            continue
        m = RE_WAVE.match(line)
        if m:
            r["candidates"] += sum(int(m[i]) for i in (1, 2, 3, 4))
            continue
        m = RE_NOIMP.match(line)
        if m:
            r["baseline_score"] = r["baseline_score"] or money(m[1])
            r["best_score"] = r["baseline_score"]
            continue
        m = RE_BEST.match(line)
        if m:
            r["baseline_score"] = money(m[1])
            r["best_score"] = money(m[2])
            r["gain"] = float(m[3])
            in_accept = True
            continue
        if in_accept:
            m = RE_ACC.match(line)
            if m:
                r["accepted"].append({"knob": m[1], "from": int(m[2]), "to": int(m[3]),
                                      "score": money(m[4])})
            elif line.strip():
                in_accept = False
    return r


def screen_allowance(entry, args):
    """Seconds autotune will burn BEFORE its first candidate, and therefore before --budget
    starts to mean anything.

    --budget only gates the start of new CANDIDATES; the build-only screening pass that runs
    first is not charged to it. Screening costs two builds per knob, so it scales with the
    knob count — hand a 344-knob builder a flat 240s budget and it buys zero candidate
    evaluations, then reports a local optimum that was never actually tested.

    The per-knob rate is NOT a constant: it is the builder's own run time, and across this
    repo that spans 35x (brackets/stack6 0.058 s/knob, plotter/build_planB 2.04 s/knob) with
    no useful correlation to anything discovery measures. So the rate is LEARNED — every
    finished sweep writes its measured s/knob back into the discovery cache, and only a
    builder that has never been swept falls back to --screen-rate."""
    rate = entry.get("screen_rate") or args.screen_rate
    return rate * (entry.get("knobs") or 0) * (6.0 / max(args.jobs, 1))


def sweep(entry, budget, args):
    """Run one autotune sweep to completion (or to the wall) and summarise it."""
    slug, rel = entry["slug"], entry["builder"]
    tag = f"{slug}__{os.path.basename(rel)[:-3]}"
    os.makedirs(LOGS, exist_ok=True)
    log = os.path.join(LOGS, tag + ".log")

    ckpt = checkpoint_path(entry["target"]) if entry.get("target") else None
    ckpt_before = os.path.getmtime(ckpt) if ckpt and os.path.exists(ckpt) else None

    cmd = [sys.executable, "tools/autotune.py", slug, rel,
           "--jobs", str(args.jobs), "--passes", str(args.passes), "--budget", str(int(budget))]
    if args.no_macros:
        cmd.append("--no-macros")
    # autotune stops STARTING candidates at --budget; the wave in flight still has to land,
    # so the hard kill has to sit well above it or we would murder finished-but-unprinted work.
    hard = budget + args.grace
    t0 = time.time()
    rc, out, timedout = sh(cmd, hard)
    elapsed = round(time.time() - t0, 1)
    open(log, "w").write(out)

    res = parse_sweep(out)
    res.update(slug=slug, builder=rel, target=entry.get("target"),
               champion=entry.get("champion"), champion_score=entry.get("champion_score"),
               reproduces=entry.get("reproduces"), lost=entry.get("lost"),
               knobs=entry.get("knobs"), macros=entry.get("macros"),
               budget=int(budget), search_budget=int(entry.get("search_budget", budget)),
               elapsed=elapsed, log=os.path.relpath(log, REPO))

    # A kill (or a crash) loses the final BEST line, but autotune checkpoints every accepted
    # win the moment it lands — so the win is on disk even when stdout never got to say so.
    if ckpt and (res["best_score"] is None or timedout) and os.path.exists(ckpt):
        if os.path.getmtime(ckpt) != ckpt_before:
            c = load(ckpt, {})
            if c.get("best_score"):
                res["baseline_score"] = res["baseline_score"] or c.get("baseline_score")
                res["best_score"] = c["best_score"]
                res["accepted"] = c.get("accepted") or res["accepted"]
                res["from_checkpoint"] = True

    if res["baseline_score"] and res["best_score"]:
        res["gain"] = round(res["baseline_score"] / res["best_score"], 4)
        if res["best_score"] < res["baseline_score"]:
            # a win that ran out of clock is still a win, but the search is not finished
            res["status"] = "improved" if res["converged"] else "improved-partial"
        elif res["converged"]:
            res["status"] = "converged"          # a real local optimum: every knob was tried
        else:
            # the clock ran out first — "nothing found" here is NOT "nothing to find"
            res["status"] = "budget-out"
    elif timedout:
        res["status"] = "timeout"
    else:
        res["status"] = "error"
        res["error"] = (out.strip().splitlines() or ["no output"])[-1][:160]
    if res["status"] == "budget-out" and not res["candidates"]:
        res["status"] = "screen-only"            # the screening pass ate the whole budget
    return res


# ── reporting ────────────────────────────────────────────────────────────────
def fmt_score(v):
    return f"{v:,}" if isinstance(v, (int, float)) else "-"


def print_table(runs, discovery, skipped, plan):
    ok = [d for d in discovery.values() if d.get("ok")]
    tunable = [d for d in ok if d.get("knobs") or d.get("macros")]
    print("\n" + "=" * 108)
    print("DISCOVERY")
    print(f"  {len(discovery)} builder-shaped files probed, {len(skipped)} skipped as helpers")
    print(f"  {len(ok)} have a passing baseline, {len(tunable)} of those have knobs "
          f"({len([d for d in ok if d.get('reproduces')])} reproduce a committed .man)")
    bad = {}
    for d in discovery.values():
        if not d.get("ok"):
            bad[(d.get("error") or "?").split(":")[0][:44]] = bad.get(
                (d.get("error") or "?").split(":")[0][:44], 0) + 1
    for reason, n in sorted(bad.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>3}  {reason}")

    print("\nSWEEP RESULTS")
    print(f"{'problem':17}{'builder':28}{'lost':>5}{'baseline':>14}{'best':>14}{'gain':>7}"
          f"{'cands':>7}  status / knob")
    print("-" * 118)
    rows = sorted(runs.values(), key=lambda r: -(r.get("gain") or 1))
    improved = 0
    for r in rows:
        knob = ""
        if r.get("accepted"):
            knob = "; ".join(f"{a['knob']} {a['from']}->{a['to']}" for a in r["accepted"][:3])
            improved += 1
        elif r.get("status") == "skipped":
            knob = r.get("note", "")
        elif r.get("status") in ("error", "timeout"):
            knob = (r.get("error") or "")[:44]
        gain = f"{r['gain']:.3f}x" if r.get("gain") else "-"
        print(f"{r['slug'][:16]:17}{os.path.basename(r['builder'])[:27]:28}"
              f"{(r.get('lost') or 0):>5.2f}{fmt_score(r.get('baseline_score')):>14}"
              f"{fmt_score(r.get('best_score')):>14}{gain:>7}{r.get('candidates') or 0:>7}"
              f"  {r.get('status')}{'  ' + knob if knob else ''}")
    print("-" * 118)

    def of(*st):
        return [r for r in rows if r.get("status") in st]

    won, flat, short = of("improved", "improved-partial"), of("converged"), of("budget-out", "screen-only")
    print(f"{len(won)} improved, {len(flat)} CONVERGED with no improvement, "
          f"{len(short)} ran out of clock, {len(of('error', 'timeout'))} error/timeout, "
          f"{len(of('skipped'))} skipped")
    if flat:
        print("\n  CONFIRMED LOCAL OPTIMA (every knob tried, nothing helps — a real result):")
        for r in flat:
            print(f"    {r['slug']}/{os.path.basename(r['builder'])}  "
                  f"{r.get('candidates')} candidates at score {fmt_score(r.get('baseline_score'))}")
    if short:
        print("\n  INCONCLUSIVE (budget ran out mid-search — NOT evidence of a local optimum):")
        for r in short:
            print(f"    {r['slug']}/{os.path.basename(r['builder'])}  "
                  f"{r.get('candidates')} of ~{(r.get('searched') or 0) * 4} candidates tried")
    if won:
        print("\n  IMPROVEMENTS:")
        for r in won:
            cs, best = r.get("champion_score"), r.get("best_score")
            if cs and best and best <= cs:
                verdict = f"NEW BEST for {r['slug']} (previous best {fmt_score(cs)})"
            elif cs and best:
                verdict = (f"still {best / cs:.1f}x behind champion "
                           f"{os.path.basename(r['champion'])} ({fmt_score(cs)}) — DEAD BRANCH, "
                           f"improves this variant but not the problem")
            else:
                verdict = "no champion comparison available"
            print(f"    {r['slug']}/{os.path.basename(r['builder'])}: "
                  f"{fmt_score(r.get('baseline_score'))} -> {fmt_score(best)} "
                  f"({r['gain']:.3f}x)  — {verdict}")
            for a in r.get("accepted", []):
                print(f"        {a['knob']}: {a['from']} -> {a['to']}  "
                      f"(score {fmt_score(a['score'])})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--total-budget", type=float, default=2400,
                    help="seconds for the whole sweep phase (default 2400 = 40 min)")
    ap.add_argument("--per-problem", type=float, default=0,
                    help="seconds per problem (default: total/plan-size, clamped)")
    ap.add_argument("--min-budget", type=float, default=150)
    ap.add_argument("--max-budget", type=float, default=600)
    ap.add_argument("--screen-rate", type=float, default=0.35,
                    help="measured seconds of knob screening per knob at --jobs 6 (see "
                         "screen_allowance: this is added on top of the search budget)")
    ap.add_argument("--grace", type=float, default=240,
                    help="extra wall clock over --budget before autotune is killed")
    ap.add_argument("--jobs", type=int, default=6, help="autotune --jobs (default 6)")
    ap.add_argument("--passes", type=int, default=6)
    ap.add_argument("--no-macros", action="store_true")
    ap.add_argument("--per-slug", type=int, default=2, help="builders to sweep per problem")
    ap.add_argument("--top", type=int, default=0, help="only sweep the top N of the plan")
    ap.add_argument("--skip", default="", help="comma-separated builder paths to skip")
    ap.add_argument("--discover-jobs", type=int, default=8)
    ap.add_argument("--discover-timeout", type=float, default=120)
    ap.add_argument("--force-rediscover", action="store_true")
    ap.add_argument("--no-skip", action="store_true", help="probe helper-looking files too")
    ap.add_argument("--refresh-points", action="store_true", help="re-fetch ours.py")
    ap.add_argument("--refresh-champions", action="store_true",
                    help="re-grade every committed .man to refresh the per-problem best")
    ap.add_argument("--no-champions", action="store_true",
                    help="skip the champion comparison (faster, but 'improved' loses its meaning)")
    ap.add_argument("--max-behind", type=float, default=8.0,
                    help="skip a builder starting more than this many x behind the problem's "
                         "best committed .man — tuning wins ~1.2x, so it could never catch up")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-run problems already in the report")
    args = ap.parse_args()

    t0 = time.time()
    discovery, skipped = discover(args)

    ok = [d for d in discovery.values() if d.get("ok")]
    print(f"\n  usable baselines: {len(ok)}/{len(discovery)}  "
          f"(with knobs: {len([d for d in ok if d.get('knobs') or d.get('macros')])})")
    for d in sorted(ok, key=lambda d: d["builder"]):
        print(f"    {d['builder']:<46} {fmt_score(d.get('score')):>14}  "
              f"{d.get('passed')}/{d.get('total')}  knobs {d.get('knobs')}+{d.get('macros')}m  "
              f"{'reproduces committed' if d.get('reproduces') else 'out of sync'}")
    if args.discover_only:
        return

    points, src = lost_points(args.refresh_points)
    print(f"\npoints available per problem ({src}): "
          + ", ".join(f"{k} {v:.2f}" for k, v in sorted(points.items(), key=lambda kv: -kv[1])[:8]))

    plan = rank(discovery, points, args)
    if args.top:
        plan = plan[:args.top]

    report = load(REPORT, {})
    runs = report.get("runs", {}) if isinstance(report, dict) else {}
    if args.force:
        runs = {}

    todo = [e for e in plan if e["builder"] not in runs and not e["skip_reason"]]
    # Split the clock: every planned sweep first has to pay its own (fixed, knob-proportional)
    # screening cost, and only what is left over is real search time to share out.
    screen_total = sum(screen_allowance(e, args) for e in todo)
    search_pool = max(args.total_budget - screen_total, args.min_budget * len(todo))
    for e in plan:
        e["screen_allow"] = screen_allowance(e, args)
        e["search_budget"] = args.per_problem or max(
            args.min_budget, min(args.max_budget, search_pool / max(len(todo), 1)))

    print(f"\nPLAN — {len(plan)} (slug, builder) pairs, {len(todo)} still to do, "
          f"{args.total_budget:.0f}s total = {screen_total:.0f}s of knob screening "
          f"+ {search_pool:.0f}s of search, --jobs {args.jobs}")
    print(f"{'#':>3} {'problem':17}{'builder':26}{'lost':>5}{'baseline':>14}{'champion':>14}"
          f"{'behind':>8}{'knobs':>8}{'screen':>8}{'search':>8}  note")
    for i, e in enumerate(plan, 1):
        note = e["skip_reason"] or ("already done — resuming" if e["builder"] in runs else "")
        behind = "{:.1f}x".format(e["behind"]) if e.get("behind") else "-"
        print(f"{i:>3} {e['slug'][:16]:17}{os.path.basename(e['builder'])[:25]:26}"
              f"{e['lost']:>5.2f}{fmt_score(e.get('score')):>14}"
              f"{fmt_score(e.get('champion_score')):>14}{behind:>8}"
              f"{str(e.get('knobs')) + '+' + str(e.get('macros')) + 'm':>8}"
              f"{e['screen_allow']:>7.0f}s{e['search_budget']:>7.0f}s  {note}")
    if args.plan_only:
        return

    for i, e in enumerate(plan, 1):
        key = e["builder"]
        if e["skip_reason"]:
            runs.setdefault(key, dict(slug=e["slug"], builder=key, lost=e["lost"],
                                      baseline_score=e.get("score"), best_score=None,
                                      status="skipped", note=e["skip_reason"], accepted=[]))
            continue
        if key in runs:
            print(f"\n[{i}/{len(plan)}] {key}: already in the report ({runs[key]['status']}) — skip")
            continue
        left = args.total_budget - (time.time() - t0)
        if left < args.min_budget:
            print(f"\ntotal budget exhausted ({time.time() - t0:.0f}s) — stopping "
                  f"({len(plan) - i + 1} pairs left for the next run)")
            break
        b = e["screen_allow"] + min(e["search_budget"], max(args.min_budget, left))
        print(f"\n[{i}/{len(plan)}] sweeping {key}  (budget {b:.0f}s = "
              f"{e['screen_allow']:.0f}s screen + {min(e['search_budget'], max(args.min_budget, left)):.0f}s "
              f"search, {left:.0f}s of total left) …", flush=True)
        r = sweep(e, b, args)
        runs[key] = r
        # Learn this builder's screening rate so the NEXT run budgets it correctly (see
        # screen_allowance). This is why a second pass finds things the first one could not.
        if r.get("screen_secs") and r.get("screened"):
            cache = load(DISCOVERY, {})
            if key in cache:
                cache[key]["screen_rate"] = round(
                    r["screen_secs"] / r["screened"] * (args.jobs / 6.0), 4)
                save(DISCOVERY, cache)
        print(f"    -> {r['status']}: {fmt_score(r.get('baseline_score'))} -> "
              f"{fmt_score(r.get('best_score'))} in {r['elapsed']}s"
              + (f"  [{', '.join(a['knob'] for a in r['accepted'])}]" if r.get("accepted") else ""))
        save(REPORT, {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                      "runs": runs})

    dsum = {"probed": len(discovery), "skipped_as_helpers": len(skipped),
            "usable_baseline": len(ok),
            "tunable": len([d for d in ok if d.get("knobs") or d.get("macros")]),
            "reproduce_committed": len([d for d in ok if d.get("reproduces")])}
    save(REPORT, {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                  "discovery": dsum, "skipped_as_helpers": sorted(skipped),
                  "baselines": {d["builder"]: {k: d.get(k) for k in
                                               ("slug", "ok", "score", "passed", "total", "box",
                                                "ticks", "knobs", "macros", "reproduces",
                                                "target", "error")}
                                for d in sorted(discovery.values(), key=lambda x: x["builder"])},
                  "runs": runs})
    print_table(runs, discovery, skipped, plan)
    print(f"\nwrote {os.path.relpath(REPORT, REPO)}  ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()
