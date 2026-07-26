#!/usr/bin/env python3
"""Submit a solution to the grader and poll the result.

  python3 tools/submit.py <slug> <file.man>

Submissions are per-problem and independent; only your BEST submission per problem
counts, so submitting never lowers your score.

Every submission is ARCHIVED under submitted/<slug>/ before it is polled. This is not
bookkeeping: two live champions have already gone missing from the tree. The brackets
one was recoverable only because someone happened to commit it on another branch
(stack6.man, 23x23); the tcp one is gone for good — no .man blob reachable from any ref
matches it, and the server exposes no way to read a submitted program back
(/submissions, /teams/me/submissions and /public/submissions all 404, and
GET /submissions/<id> needs an id nobody recorded). A champion you cannot reproduce is a
champion you cannot improve, and both times the cost was measured in tens of percent.
"""
import json
import os
import sys
import time
import lib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def archive(slug, sub_id, src, program, result=None):
    """Keep the EXACT bytes that were submitted, keyed by submission id."""
    d = os.path.join(REPO, "submitted", slug)
    os.makedirs(d, exist_ok=True)
    man = os.path.join(d, f"{sub_id}.man")
    if not os.path.exists(man):
        with open(man, "w", encoding="utf-8") as fh:
            fh.write(program)
    meta = {"slug": slug, "submissionId": sub_id, "source": src,
            "submittedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if result:
        meta.update({k: result.get(k) for k in
                     ("status", "score", "casesPassed", "casesTotal")})
    with open(os.path.join(d, f"{sub_id}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
    return man


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: python3 tools/submit.py <slug> <file.man>")
    slug, file = sys.argv[1], sys.argv[2]
    key = lib.api_key()
    if not key:
        sys.exit("no API_KEY found (.env)")
    probs = lib.list_problems()
    p = next((x for x in probs if x.get("slug") == slug), None)
    if not p:
        sys.exit(f"unknown slug {slug}")
    if p.get("status") == "practice":
        sys.exit("practice problem — the grader rejects submissions")

    program = lib.read_man(file)
    status, j = lib.submit(key, p["id"], program)
    if status not in (200, 201, 202):
        sys.exit(f"submit failed: HTTP {status} {j}")
    sub_id = j.get("id")
    print(f"submitted {file} -> {slug}: id={sub_id} status={j.get('status')}")
    print(f"archived  {archive(slug, sub_id, file, program)}  (commit this)")

    for i in range(45):
        time.sleep(2)
        _, pj = lib.poll(key, sub_id)
        st = (pj or {}).get("status")
        if st in ("done", "failed"):
            print(f"\nresult: {st}   cases {pj.get('casesPassed')}/{pj.get('casesTotal')}   score {pj.get('score')}")
            archive(slug, sub_id, file, program, pj)
            if pj.get("loadError"):
                print("loadError:", pj["loadError"])
            if pj.get("error"):
                print("error:", pj["error"])
            ok = st == "done" and pj.get("casesPassed") == pj.get("casesTotal")
            sys.exit(0 if ok else 1)
        print(f"\r  {st}... ({(i + 1) * 2}s)   ", end="", flush=True)
    print("\nstill pending — re-check with tools/status.py")


if __name__ == "__main__":
    main()
