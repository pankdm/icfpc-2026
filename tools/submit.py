#!/usr/bin/env python3
"""Submit a solution to the grader and poll the result.

  python3 tools/submit.py <slug> <file.man>

Submissions are per-problem and independent; only your BEST submission per problem
counts, so submitting never lowers your score.
"""
import sys
import time
import lib


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

    for i in range(45):
        time.sleep(2)
        _, pj = lib.poll(key, sub_id)
        st = (pj or {}).get("status")
        if st in ("done", "failed"):
            print(f"\nresult: {st}   cases {pj.get('casesPassed')}/{pj.get('casesTotal')}   score {pj.get('score')}")
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
