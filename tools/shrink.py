"""shrink.py — run every safe geometry pass to a FIXPOINT, with a two-tier gate.

WHY THIS EXISTS. The repo already has eight semantics-preserving passes (`dce`, `peep`,
`sched`, `stairfold`, `reroute`, `fold`, `polish`, `roomfit`). Nothing composes them, and
`equiv.py` — the one tool that can accept a candidate WITHOUT simulating it — is imported
by nobody. This driver fixes both.

THE LAW THAT MAKES COMPOSITION NECESSARY (measured, `tools/dce.py`):

    A HOLE DOES NOT SHRINK `max(w,h)`.

Ticks are cells WALKED, not instructions executed, so blanking a cell in the middle of a
grid changes neither term of `max(w,h)^2 * avg ticks`. Measured across every champion:
3-83 dead cells each and **zero** at the bounding-box extremes; re-measured 2026-07-26 on
`snake/micro9` and the gradebook champion, **0 dead cells** in both. Removal on its own is
finished on our champions. What pays is REMOVAL COMPOSED WITH COMPACTION: a pass that
empties a line, followed by a pass that deletes it. Hence a fixpoint loop rather than a
menu — `stairfold` empties a shim row that only then becomes a `polish` candidate, and
`polish` deleting a row can expose a new `fold` pair on the rows that close up behind it.

PASS ORDER (hole-openers first, line-deleters last, walls last of all):

    dce        blank cells no man can reach                  -> opens holes
    stairfold  flatten walk staircases                       -> empties shim rows
    reroute    re-route op-free connectors through live rows -> empties donor rows
    fold       merge two adjacent lines into one             -> deletes a line
    polish     delete a blank / all-`|` / all-`-` line       -> deletes a line
    roomfit    pull each room's wall in to its content       -> pays immediately

THE TWO-TIER GATE. Grade-gated search dies on large instances (one LLM case is ~256s even
in the Rust engine), so grade only when you must:

  tier 1  `tools/equiv.py` proves the two grids behave IDENTICALLY — same op sequence per
          man, same path length, same pipe structure — without running a single case. A
          transformation that only MOVES things cannot change the tick count, so if equiv
          says EQUIVALENT the candidate is accepted on box alone, at zero grading cost.
          This is the only tier that can gate a candidate on a grid we cannot afford to
          simulate.
  tier 2  anything equiv cannot prove (stairfold and fold deliberately change tick counts)
          falls through to `grade_fast`. Accepted only if it passes EVERY case AND scores
          strictly lower.

TIER 2 WAS VALIDATED END-TO-END, 2026-07-26 — and the incident is worth recording because
the first reading of it was wrong. Run on `submitted/gradebook/89cfafeb`, tier 2 accepted a
`stairfold` + `fold` pair: box 13,456 -> 12,544, local 679,531,845 -> 632,629,760 (1.0741x),
oracle 7/7 public. Submitted, it scored 2,323,323,161 against that same build's own
2,495,152,808 — **1.0740x, matching the local prediction to four significant figures on the
full 20-case set including privates.** The transform was exactly as safe as it claimed.

The near-miss was a METHODOLOGY error, not a tool error: the 2,323,323,161 was first
compared against the LIVE score of 203,387,211, which belonged to a different build
(61x71, box 5041) three generations newer, and that made a real 1.07x win look like a 12x
private regression. CLAUDE.md already warns "identify champions by SCORE, never by box";
the same rule applies to the BASELINE — a candidate can only be compared against the score
of the exact build it was derived from. Read the sidecar `.json` next to the archived
submission; do not reach for the problem's live score.

So the rule this tool enforces:

  * TIER 1 needs no case at all. `equiv` proves the op sequence, path length and pipe
    structure are unchanged, so behaviour is identical on EVERY case by construction. It is
    the only tier affordable on grids too big to simulate (one LLM case is ~256s).
  * TIER 2 is honest but relative. It reports an improvement over THE INPUT GRID. Record
    which build the input was, or the number is uninterpretable.

Residual risk tier 2 genuinely cannot see: `fold` and `stairfold` change WALK LENGTHS, and
a walk length feeds a delay-line pipe (gradebook's 54-cell pipe 0->7 is a delay line whose
LENGTH IS CAPACITY). Public cases may not reach the depth that exposes a mis-sized ring.
That risk is real but was NOT what happened here.

`grade_fast` averages avgTicks over PASSING cases ONLY, so a partial pass is compared
against a different case set and is NOT comparable. This driver therefore requires
passed == total before it will even look at the score.

The Rust engine is a PRE-FILTER, not the judge. Re-grade the winner with
`node tools/grade.js <slug> <out.man>` before submitting.

Usage:
    python3 tools/shrink.py <slug> <file.man> [--out OUT] [--rounds N] [--jobs N]
                                             [--cap N] [--cases F] [--dry-run] [-v]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(REPO, "tools")


def _run(cmd, timeout=None):
    return subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout
    )


def footprint(path):
    """Bounding box of non-space cells: (w, h, box, content)."""
    cells = [
        (x, y)
        for y, row in enumerate(open(path).read().splitlines())
        for x, ch in enumerate(row)
        if ch != " "
    ]
    if not cells:
        return 0, 0, 0, 0
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    w = max(xs) - min(xs) + 1
    h = max(ys) - min(ys) + 1
    return w, h, max(w, h) ** 2, len(cells)


def grade(slug, path, jobs, cap, cases):
    """Rust-engine grade. Returns (ok, avg_ticks, box, score, note).

    The SCORE comes from the grader, never from `box * avg_ticks`. Not every problem is
    scored that way: `history-lesson` is FOOTPRINT-ONLY, where the grader reports 6,561 for
    a build whose `box * avgTicks` is 1,409,519,313. Computing the objective here would
    chase tick reductions worth exactly nothing and could reject a genuine box win whose
    ticks happened to rise.
    """
    cmd = [sys.executable, os.path.join(TOOLS, "grade_fast.py"), slug, path,
           "--jobs", str(jobs)]
    if cap:
        cmd += ["--cap", str(cap)]
    if cases:
        cmd += ["--cases", cases]
    proc = _run(cmd)
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return False, None, None, None, "grade_fast produced no JSON"
    passed, total = data.get("passed"), data.get("total")
    if passed != total:
        # Averaged over a different case set — deliberately not comparable.
        return False, None, None, None, f"{passed}/{total} cases"
    box = data["footprint"]["box"]
    return (True, data["avgTicks"], box, data["score"], f"{passed}/{total} cases")


def equivalent(before, after):
    """True when equiv.py PROVES identical behaviour (so ticks cannot have changed)."""
    proc = _run([sys.executable, os.path.join(TOOLS, "equiv.py"), before, after])
    return "NOT EQUIVALENT" not in proc.stdout and "EQUIVALENT" in proc.stdout


# --- the passes -------------------------------------------------------------------
# Each returns (candidate_path_or_None, status). A pass that CRASHES must be reported as
# a crash, never as "nothing to do" — otherwise the driver announces a fixpoint it has
# not actually reached. `tools/reroute.py` currently dies on the gradebook champion
# ("unterminated literal in segment", blockify3.py:90) and that has to be visible.
# `moves_only` marks passes that cannot change a tick count, so tier 1 can accept them.

def _shell_pass(cmd, out):
    proc = _run(cmd)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        why = tail[-1].strip() if tail else f"exit {proc.returncode}"
        return None, f"CRASHED: {why[:120]}"
    if not os.path.exists(out):
        return None, "no output"
    return out, "ok"


def _pass_dce(slug, src, work, jobs, cap, cases):
    out = os.path.splitext(src)[0] + "-dce.man"
    return _shell_pass([sys.executable, os.path.join(TOOLS, "dce.py"), slug, src], out)


def _pass_stairfold(slug, src, work, jobs, cap, cases):
    out = os.path.join(work, "stairfold.man")
    return _shell_pass(
        [sys.executable, os.path.join(TOOLS, "stairfold.py"), src, out], out)


def _pass_reroute(slug, src, work, jobs, cap, cases):
    out = os.path.join(work, "reroute.man")
    return _shell_pass(
        [sys.executable, os.path.join(TOOLS, "reroute.py"), src, out], out)


def _pass_fold(slug, src, work, jobs, cap, cases):
    out = os.path.join(work, "fold.man")
    cmd = [sys.executable, os.path.join(TOOLS, "fold.py"), slug, src,
           "--out", out, "--engine", "fast"]
    if cap:
        cmd += ["--cap", str(cap)]
    if cases:
        cmd += ["--cases", cases]
    return _shell_pass(cmd, out)


def _pass_polish(slug, src, work, jobs, cap, cases):
    out = os.path.join(work, "polish.man")
    cmd = [sys.executable, os.path.join(TOOLS, "polish.py"), slug, src,
           "--out", out, "--engine", "fast", "--jobs", str(jobs)]
    if cap:
        cmd += ["--cap", str(cap)]
    if cases:
        cmd += ["--cases", cases]
    return _shell_pass(cmd, out)


def _pass_roomfit(slug, src, work, jobs, cap, cases):
    out = os.path.splitext(src)[0] + "-roomfit.man"
    return _shell_pass(
        [sys.executable, os.path.join(TOOLS, "roomfit.py"), slug, src], out)


PASSES = [
    ("dce",       _pass_dce,       True),   # blanks unreachable cells: no man's path moves
    ("stairfold", _pass_stairfold, False),  # deliberately shortens walks
    ("reroute",   _pass_reroute,   False),  # path length may change
    ("fold",      _pass_fold,      False),  # merging lines shortens walks
    ("polish",    _pass_polish,    False),
    ("roomfit",   _pass_roomfit,   True),   # only walls move; nothing inside shifts
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("man")
    ap.add_argument("--out", default=None, help="default <stem>-shrunk.man")
    ap.add_argument("--rounds", type=int, default=6, help="max fixpoint rounds")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--cases", default=None)
    ap.add_argument("--only", default=None,
                    help="comma-separated subset of passes to run")
    ap.add_argument("--proved-only", action="store_true",
                    help="tier 1 only: accept nothing that equiv cannot PROVE identical. "
                         "Use on grids too big to grade, or when a sized ring / delay "
                         "line makes a walk-length change risky.")
    ap.add_argument("--dry-run", action="store_true", help="never write the output file")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    passes = PASSES
    if args.only:
        wanted = {name.strip() for name in args.only.split(",")}
        passes = [p for p in PASSES if p[0] in wanted]
        unknown = wanted - {p[0] for p in PASSES}
        if unknown:
            sys.exit(f"unknown pass(es): {', '.join(sorted(unknown))}")

    work = tempfile.mkdtemp(prefix="shrink-")
    current = os.path.join(work, "current.man")
    shutil.copy(args.man, current)

    ok, ticks, box, score, note = grade(
        args.slug, current, args.jobs, args.cap, args.cases)
    if not ok:
        sys.exit(f"baseline does not pass ({note}) — nothing to compare against")
    w, h, _, content = footprint(current)
    print(f"baseline {os.path.basename(args.man)}: {w}x{h} box {box:,} "
          f"avgTicks {ticks:,.0f} score {score:,.0f} ({note}), "
          f"{content:,} content cells")

    history = []
    crashed = {}
    for round_i in range(1, args.rounds + 1):
        improved = False
        for name, fn, moves_only in passes:
            cand, status = fn(args.slug, current, work, args.jobs, args.cap, args.cases)
            if status.startswith("CRASHED"):
                crashed[name] = status
                print(f"  round {round_i} {name:10s} {status}")
                continue
            if not cand or not os.path.exists(cand):
                if args.verbose:
                    print(f"  round {round_i} {name:10s} produced nothing")
                continue
            if open(cand).read() == open(current).read():
                if args.verbose:
                    print(f"  round {round_i} {name:10s} no change")
                continue

            cw, ch, cbox, ccontent = footprint(cand)

            # tier 1 — proof, no simulation. Only legal for move-only passes, and only
            # when the box actually falls (equal behaviour + equal box is worth nothing).
            if moves_only and cbox < box and equivalent(current, cand):
                # Behaviour is identical, so ticks are unchanged and the score scales with
                # the box under either scoring rule.
                print(f"  round {round_i} {name:10s} ACCEPT (proved equivalent) "
                      f"box {box:,} -> {cbox:,}  [no grading]")
                shutil.copy(cand, current)
                score = score * cbox / box
                box = cbox
                history.append((round_i, name, "equiv", cbox, ticks, score))
                improved = True
                continue

            # tier 2 — grade. Requires ALL cases; a partial pass is not comparable.
            if args.proved_only:
                if args.verbose:
                    print(f"  round {round_i} {name:10s} skipped "
                          f"(not provably equivalent; --proved-only)")
                continue
            cok, cticks, cbox2, cscore, cnote = grade(
                args.slug, cand, args.jobs, args.cap, args.cases)
            if not cok:
                print(f"  round {round_i} {name:10s} reject ({cnote})")
                continue
            if cscore >= score:
                print(f"  round {round_i} {name:10s} reject "
                      f"score {cscore:,.0f} >= {score:,.0f}")
                continue
            print(f"  round {round_i} {name:10s} ACCEPT box {box:,} -> {cbox2:,} "
                  f"ticks {ticks:,.0f} -> {cticks:,.0f} "
                  f"score {score:,.0f} -> {cscore:,.0f} ({cnote})")
            shutil.copy(cand, current)
            box, ticks, score = cbox2, cticks, cscore
            history.append((round_i, name, "graded", cbox2, cticks, cscore))
            improved = True

        if not improved:
            print(f"fixpoint after {round_i} round(s)")
            break

    w, h, box, content = footprint(current)
    print(f"\nfinal: {w}x{h} box {box:,} avgTicks {ticks:,.0f} score {score:,.0f}, "
          f"{content:,} content cells ({content / (w * h) * 100:.1f}% density)")
    if crashed:
        print("PASSES THAT CRASHED (this is NOT a fixpoint for them — they never ran):")
        for name, why in crashed.items():
            print(f"  {name}: {why}")
    if not history:
        print("no pass found anything — this grid is at the fixpoint of the passes that ran")
        return
    print(f"{len(history)} accepted change(s): "
          + ", ".join(f"{n}({g})" for _, n, g, _, _, _ in history))

    if args.dry_run:
        print("--dry-run: not written")
        return
    out = args.out or os.path.splitext(args.man)[0] + "-shrunk.man"
    shutil.copy(current, out)
    print(f"wrote {out}")
    if any(gate == "graded" for _, _, gate, _, _, _ in history):
        print(f"NOTE: the score above is relative to THE INPUT GRID ({args.man}). Compare "
              "any server result against that build's own archived score (the sidecar "
              ".json beside it), NOT against the problem's live score — a newer champion "
              "from another branch will make a real win look like a regression.")
    print(f"NOW RE-GRADE WITH THE ORACLE: node tools/grade.js {args.slug} {out}")


if __name__ == "__main__":
    main()
