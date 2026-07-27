"""champions.py — find the file behind each LIVE score, across every git ref.

WHY THIS EXISTS. Three separate times on 2026-07-26 an agent (me) optimised a file that
looked like the champion and was not, then read the server's reply against the wrong
baseline:

  * `submitted/plotter.man` == `solutions/plotter/champion-9f675d41.man`, 79x79. The LIVE
    plotter build is 48x58 and 28x better; it exists only on `origin/dualhead-reopen`.
  * `submitted/gradebook/89cfafeb` (61x116) scored 2,495,152,808; the live build was 61x71
    at 203,387,211, three generations newer, also only on `origin/dualhead-reopen`.
  * `submitted/brackets.man` is 23x23; the live build is 15x15.

The failure mode is always the same: **a local file named `champion-*` or sitting in
`submitted/` is not evidence of anything.** `main` was 81 commits behind a teammate's
branch, so most of `submitted/` was a fossil. And `tools/submissions.py --match` cannot
save you — it matches by DIMENSIONS ONLY, which is how the sudoku mis-submission happened.

WHAT IS ACTUALLY AUTHORITATIVE. Every `tools/submit.py` run archives the exact bytes it
sent to `submitted/<slug>/<id>.man` and the server's verdict to `<id>.json`. That pair is
proof: the score in the sidecar belongs to those bytes and to no others. This tool walks
that archive across EVERY ref (not just the checked-out one), keeps the best-scoring entry
per problem, and tells you the ref and path to start from.

    python3 tools/champions.py                 # table: live score, where the file lives
    python3 tools/champions.py --stale         # only problems whose champion is NOT on HEAD
    python3 tools/champions.py --extract DIR   # write every champion into DIR/<slug>.man

The `on_head` column is the one that matters before starting work. If it says NO, anything
you build from the working tree starts from a fossil.
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict

TEAM = "Snakes, Monkeys, and Two Smoking Lambdas"

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    proc = subprocess.run(["git", "-C", REPO, *args],
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""


def refs():
    out = git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    names = [line.strip() for line in out.splitlines() if line.strip()]
    # HEAD first so "on_head" is decided by the tree the agent is actually working in.
    return ["HEAD"] + names


def scan():
    """{slug: [(score, cases, ref, man_path)]} from every archived submission sidecar."""
    found = defaultdict(list)
    for ref in refs():
        listing = git("ls-tree", "-r", "--name-only", ref)
        for path in listing.splitlines():
            path = path.strip()
            if not path.startswith("submitted/") or not path.endswith(".json"):
                continue
            parts = path.split("/")
            if len(parts) != 3:
                continue
            slug = parts[1]
            blob = git("show", f"{ref}:{path}")
            if not blob:
                continue
            try:
                data = json.loads(blob)
            except Exception:
                continue
            score = data.get("score")
            if not score:
                continue
            man = path[:-5] + ".man"
            found[slug].append((float(score), data.get("cases"), ref, man))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale", action="store_true",
                    help="show only problems whose champion is missing from HEAD")
    ap.add_argument("--extract", default=None,
                    help="write each champion to DIR/<slug>.man")
    args = ap.parse_args()

    found = scan()
    if not found:
        sys.exit("no archived submissions found — has tools/submit.py ever run?")

    rows = []
    for slug, entries in sorted(found.items()):
        entries.sort(key=lambda e: e[0])
        score, cases, ref, man = entries[0]
        on_head = bool(git("cat-file", "-e", f"HEAD:{man}") == "") and bool(
            git("ls-tree", "HEAD", man).strip())
        rows.append((slug, score, cases, ref, man, on_head, len(entries)))

    if args.stale:
        rows = [r for r in rows if not r[5]]
        if not rows:
            print("every live champion is present on HEAD")
            return

    print(f"{'problem':22s} {'best server score':>20s} {'subs':>5s} {'on HEAD':>8s}  where")
    print("-" * 100)
    for slug, score, cases, ref, man, on_head, n in rows:
        where = man if on_head else f"{ref}:{man}"
        print(f"{slug:22s} {score:>20,.0f} {n:>5d} {'yes' if on_head else 'NO':>8s}  {where}")

    # Cross-check against the LIVE standings. The archive only proves what THIS repo
    # submitted; a teammate submitting from their own checkout leaves no trace here. When
    # the live score beats every archived one, the champion's bytes are nowhere in git and
    # no local file can be trusted as a starting point.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import lib
        live = {}
        for problem in lib.list_problems():
            if problem.get("status") != "graded":
                continue
            for entry in lib.problem_standings(problem["id"]).get("rows", []):
                if entry.get("teamName") == TEAM:
                    live[problem["slug"]] = float(entry.get("score") or 0)
                    break
    except Exception as exc:  # standings are a nicety, not a requirement
        live = {}
        print(f"\n(live cross-check unavailable: {exc})")

    unarchived = []
    for slug, score, _, _, _, _, _ in rows:
        our = live.get(slug)
        if our and our < score * 0.999:
            unarchived.append((slug, our, score))
    if unarchived:
        print()
        print("LIVE SCORE BEATS EVERY ARCHIVED SUBMISSION — the champion's bytes are not in")
        print("git at all (submitted from a teammate's checkout). No local file is a valid")
        print("starting point for these; ask before optimising them:")
        for slug, our, best in unarchived:
            print(f"  {slug:22s} live {our:>18,.0f}   best archived {best:>18,.0f}"
                  f"   ({best / our:.1f}x worse)")

    missing = [r for r in rows if not r[5]]
    if missing:
        print()
        print(f"{len(missing)} champion(s) are NOT in the checked-out tree. Do NOT optimise "
              f"the local file for these — retrieve the real one first:")
        for slug, _, _, ref, man, _, _ in missing:
            print(f"  git show {ref}:{man} > /tmp/{slug}.man")

    if args.extract:
        os.makedirs(args.extract, exist_ok=True)
        for slug, _, _, ref, man, _, _ in rows:
            blob = git("show", f"{ref}:{man}")
            if blob:
                out = os.path.join(args.extract, f"{slug}.man")
                open(out, "w").write(blob)
                print(f"wrote {out}")


if __name__ == "__main__":
    main()
