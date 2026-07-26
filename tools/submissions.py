#!/usr/bin/env python3
"""Our submission history from the contest dashboard — the server-side box/tick split.

The public standings only expose the composite score. The dashboard exposes, per
submission, the values that score is made of: width, height, avgTicks and area2 — i.e.
whether a problem is BOX-bound or TICK-bound on the real (public+private) case set. That
is exactly what tells you which lever to pull next.

Auth: the dashboard needs a browser SESSION COOKIE (the API key does not work here, and
the login form is behind a Cloudflare Turnstile so it cannot be scripted). Grab it from
DevTools -> Network -> any /api/v1/ request -> Request Headers -> Cookie, then either:
    export ICFPC_COOKIE='__Secure-better-auth.session_token=…'
    or put that line in ~/.icfpc-cookie   (never commit it)

  python3 tools/submissions.py            best submission per problem + box/tick split
  python3 tools/submissions.py --all      full history, newest first
  python3 tools/submissions.py --match    also match each best to a local solutions/*.man
                                          of the same dimensions

NOTE: the submitted PROGRAM TEXT is not retrievable from any endpoint (checked: Bearer
GET /submissions/:id and the dashboard both omit it). git is the only copy — so never
submit a build that is not committed.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

BASE = "https://icfpcontest2026.com/api/v1"


def cookie():
    ck = os.environ.get("ICFPC_COOKIE")
    if ck:
        return ck.strip()
    path = os.path.expanduser("~/.icfpc-cookie")
    if os.path.exists(path):
        return open(path).read().strip()
    sys.exit("no session cookie: set ICFPC_COOKIE or write ~/.icfpc-cookie (see --help)")


def get(path):
    req = urllib.request.Request(BASE + path)
    req.add_header("Cookie", cookie())
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "null")


def local_mans():
    """{(w,h): [paths]} over every committed .man, for matching submissions to sources."""
    out = {}
    root = os.path.join(lib.REPO, "solutions")
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.endswith(".man"):
                continue
            p = os.path.join(dirpath, f)
            try:
                rows = open(p, encoding="utf-8").read().rstrip("\n").split("\n")
            except OSError:
                continue
            ys = [i for i, r in enumerate(rows) if r.strip()]
            if not ys:
                continue
            width = max(len(r.rstrip()) for r in rows)
            xs = [x for x in range(width) if any(len(r) > x and r[x] != " " for r in rows)]
            if not xs:
                continue
            key = (xs[-1] - xs[0] + 1, ys[-1] - ys[0] + 1)
            out.setdefault(key, []).append(os.path.relpath(p, lib.REPO))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--match", action="store_true")
    args = ap.parse_args()

    # the endpoint defaults to the 50 most recent; ?limit= widens it (200 is the max it
    # accepts — offset/page/cursor are all ignored, so that is the whole history we get)
    raw = get("/dashboard/submissions?limit=200")
    if len(raw) >= 200:
        print(f"warning: {len(raw)} rows returned — history may be truncated\n", file=sys.stderr)
    subs = [s for s in raw if s.get("status") == "done"]
    for s in subs:
        for k in ("score", "avgTicks", "width", "height", "casesPassed", "casesTotal", "area2"):
            if isinstance(s.get(k), str):
                try:
                    s[k] = float(s[k]) if k in ("score", "avgTicks") else int(s[k])
                except ValueError:
                    s[k] = None

    if args.all:
        subs.sort(key=lambda s: s["createdAt"], reverse=True)
        print(f"{'when':17}{'problem':22}{'cases':>8}{'box':>12}{'avgTicks':>12}{'score':>18}")
        for s in subs:
            box = f"{s['width']}x{s['height']}"
            print(f"{s['createdAt'][5:16]:17}{(s['problemName'] or '')[:21]:22}"
                  f"{s['casesPassed']}/{s['casesTotal']:<5}{box:>12}"
                  f"{s['avgTicks'] or 0:>12,.0f}{s['score'] or 0:>18,.0f}")
        return

    best = {}
    for s in subs:
        if s.get("score") is None:
            continue
        cur = best.get(s["problemName"])
        better = (s["casesPassed"] or 0, -(s["score"] or 0))
        if cur is None or better > (cur["casesPassed"] or 0, -(cur["score"] or 0)):
            best[s["problemName"]] = s

    # the list endpoint omits avgTicks/area2 — only the per-id detail carries them
    key = lib.api_key()
    for s in best.values():
        status, detail = lib._request("GET", f"/submissions/{s['id']}", key=key)
        if status == 200 and isinstance(detail, dict):
            for k in ("avgTicks", "area2"):
                v = detail.get(k)
                s[k] = float(v) if isinstance(v, (int, float, str)) and str(v) != "None" else None
        s.setdefault("avgTicks", None)

    mans = local_mans() if args.match else {}
    print(f"{'problem':22}{'cases':>8}{'box':>11}{'m^2':>9}{'avgTicks':>12}{'score':>18}   bound")
    print("-" * 92)
    for name, s in sorted(best.items(), key=lambda kv: -(kv[1]["score"] or 0)):
        w, h = s["width"], s["height"]
        m = max(w or 0, h or 0)
        # which dimension the box is paying for, and whether ticks or box dominates
        bound = "square" if w == h else ("HEIGHT" if h > w else "WIDTH")
        slack = abs((w or 0) - (h or 0))
        note = f"{bound}{f' (+{slack} slack)' if slack else ''}"
        print(f"{name[:21]:22}{s['casesPassed']}/{s['casesTotal']:<5}{f'{w}x{h}':>11}{m*m:>9}"
              f"{s['avgTicks'] or 0:>12,.0f}{s['score'] or 0:>18,.0f}   {note}")
        if args.match:
            hits = mans.get((w, h), [])
            print(f"{'':22}-> local {', '.join(hits[:3]) if hits else 'NO local .man of these dimensions'}"
                  f"{f' (+{len(hits)-3} more)' if len(hits) > 3 else ''}")
    print("\nbox = max(w,h)^2; score = box x avgTicks. 'slack' is free fold headroom: shrinking")
    print("the LARGER dimension is the only thing that lowers the box.")


if __name__ == "__main__":
    main()
