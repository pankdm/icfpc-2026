#!/usr/bin/env python3
"""Download & cache every released problem's full spec (incl publicTestData).

Writes one pretty-JSON file per problem to tests/<slug>.json, plus a summary
tests/index.json (slug -> {name, set, scoring, tickCap, publicCount,
privateCount, status}). Idempotent / re-runnable: overwrites the cache each run.

Uses tools/lib.py's API client (it sets a User-Agent the WAF accepts).

    python3 tools/fetch_tests.py            # fetch all problems
    python3 tools/fetch_tests.py <slug> ..  # fetch only these slugs
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

REPO = lib.REPO
TESTS = os.path.join(REPO, "tests")


def main(argv):
    os.makedirs(TESTS, exist_ok=True)
    problems = lib.list_problems()
    if not problems:
        print("ERROR: problem list came back empty", file=sys.stderr)
        return 1
    if argv:
        wanted = set(argv)
        problems = [p for p in problems if p.get("slug") in wanted]
        missing = wanted - {p.get("slug") for p in problems}
        for m in missing:
            print(f"WARN: unknown slug {m!r} (not in problem list)", file=sys.stderr)

    index = {}
    ok = 0
    for meta in problems:
        slug = meta.get("slug")
        if not slug:
            continue
        try:
            spec = lib.fetch_problem(slug)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {slug}: {e}", file=sys.stderr)
            continue
        if not spec:
            print(f"FAIL {slug}: empty spec", file=sys.stderr)
            continue
        path = os.path.join(TESTS, f"{slug}.json")
        with open(path, "w") as f:
            json.dump(spec, f, indent=2, sort_keys=True)
            f.write("\n")
        public_count = len(spec.get("publicTestData") or [])
        index[slug] = {
            "name": spec.get("name") or meta.get("name"),
            "set": spec.get("problemSetName") or meta.get("problemSetName"),
            "scoring": spec.get("scoring"),
            "tickCap": spec.get("tickCap"),
            "publicCount": public_count,
            "privateCount": spec.get("privateTestCount"),
            "status": spec.get("status") or meta.get("status"),
        }
        ok += 1
        print(f"  cached {slug:<20} {public_count:>3} public  "
              f"[{index[slug]['scoring']}, {index[slug]['status']}]")

    with open(os.path.join(TESTS, "index.json"), "w") as f:
        json.dump(index, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\ncached {ok}/{len(problems)} problems -> {TESTS}/")
    print(f"index -> {os.path.join(TESTS, 'index.json')}")
    return 0 if ok == len(problems) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
