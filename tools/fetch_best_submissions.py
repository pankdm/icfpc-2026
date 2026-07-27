#!/usr/bin/env python3
"""Download the best submitted program for every graded problem.

The contest splits authentication across two mechanisms:

* ``API_KEY`` from ``.env`` can read an individual submission's grader result.
* A dashboard session cookie is required to list our submission history and download
  the submitted program text.

Set ``ICFPC_COOKIE`` or save the Cookie request header from a signed-in dashboard
request in ``~/.icfpc-cookie``.  The output directory is replaced only after every
program has downloaded and passed validation, so a failed refresh leaves the previous
archive intact.

Usage:
    python3 tools/fetch_best_submissions.py
    python3 tools/fetch_best_submissions.py best-submissions
    python3 tools/fetch_best_submissions.py --cookie-file /path/to/cookie
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402


DEFAULT_OUTPUT = Path(lib.REPO) / "best-submissions"
DEFAULT_COOKIE_FILE = Path("~/.icfpc-cookie").expanduser()


class FetchError(RuntimeError):
    """A useful, user-facing download or validation error."""


def load_cookie(cookie_file: Path = DEFAULT_COOKIE_FILE) -> str:
    value = os.environ.get("ICFPC_COOKIE", "").strip()
    if value:
        return value
    try:
        value = cookie_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FetchError(
            "no dashboard session cookie: set ICFPC_COOKIE or save the Cookie "
            f"request header in {cookie_file}"
        ) from exc
    if not value:
        raise FetchError(f"dashboard session cookie file is empty: {cookie_file}")
    return value


def request(url: str, *, cookie: str | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "icfpc2026-team-tools/1.0")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 401:
            raise FetchError(
                f"{url}: dashboard session is missing or expired (HTTP 401)"
            ) from exc
        raise FetchError(f"{url}: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"{url}: {exc.reason}") from exc


def request_json(path: str, *, cookie: str | None = None) -> object:
    body = request(lib.BASE + path, cookie=cookie)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FetchError(f"{path}: response was not valid JSON") from exc


def number(value):
    if value is None or isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def select_best(rows: list[dict]) -> dict[str, dict]:
    """Select maximum correctness, then minimum positive score, per problem."""
    best: dict[str, dict] = {}
    for row in rows:
        if row.get("status") != "done":
            continue
        name = row.get("problemName")
        score = number(row.get("score"))
        if not name or score is None or score <= 0:
            continue
        passed = int(number(row.get("casesPassed")) or 0)
        total = int(number(row.get("casesTotal")) or 0)
        candidate_key = (passed, total, -score)
        current = best.get(name)
        if current is None:
            best[name] = row
            continue
        current_key = (
            int(number(current.get("casesPassed")) or 0),
            int(number(current.get("casesTotal")) or 0),
            -float(number(current.get("score")) or float("inf")),
        )
        if candidate_key > current_key:
            best[name] = row
    return best


def dimensions(program: str) -> tuple[int, int]:
    rows = program.rstrip("\n").splitlines()
    occupied = [
        (x, y)
        for y, row in enumerate(rows)
        for x, glyph in enumerate(row)
        if glyph != " "
    ]
    if not occupied:
        return 0, 0
    xs = [point[0] for point in occupied]
    ys = [point[1] for point in occupied]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def decode_program(body: bytes, row: dict) -> str:
    try:
        program = body.decode("ascii")
    except UnicodeDecodeError as exc:
        raise FetchError(f"submission {row.get('id')}: program is not ASCII") from exc
    if program.lstrip().startswith(("{", "[", "<!DOCTYPE", "<html")):
        raise FetchError(
            f"submission {row.get('id')}: download looks like JSON or HTML, not a program"
        )
    actual = dimensions(program)
    expected = (
        int(number(row.get("width")) or 0),
        int(number(row.get("height")) or 0),
    )
    if expected != (0, 0) and actual != expected:
        raise FetchError(
            f"submission {row.get('id')}: dimensions {actual[0]}x{actual[1]} "
            f"do not match dashboard {expected[0]}x{expected[1]}"
        )
    return program


def submission_detail(submission_id: str) -> dict:
    """Read exact score/correctness with .env; source download still needs the cookie."""
    key = lib.api_key()
    if not key:
        raise FetchError("API_KEY is missing from .env or the environment")
    status, detail = lib._request("GET", f"/submissions/{submission_id}", key=key)
    if status != 200 or not isinstance(detail, dict):
        raise FetchError(
            f"submission {submission_id}: Bearer detail request returned HTTP {status}"
        )
    if detail.get("id") != submission_id:
        raise FetchError(f"submission {submission_id}: detail response ID mismatch")
    return detail


def manifest_entry(slug: str, row: dict, program: str) -> dict:
    return {
        "slug": slug,
        "problemName": row.get("problemName"),
        "problemId": row.get("problemId"),
        "submissionId": row.get("id"),
        "createdAt": row.get("createdAt"),
        "casesPassed": int(number(row.get("casesPassed")) or 0),
        "casesTotal": int(number(row.get("casesTotal")) or 0),
        "width": int(number(row.get("width")) or 0),
        "height": int(number(row.get("height")) or 0),
        "avgTicks": number(row.get("avgTicks")),
        "area2": number(row.get("area2")),
        "score": number(row.get("score")),
        "sha256": hashlib.sha256(program.encode("ascii")).hexdigest(),
        "file": f"{slug}.man",
    }


def compact_score(score: int | float) -> str:
    for threshold, suffix in (
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    ):
        if abs(score) >= threshold:
            scaled = score / threshold
            decimals = 0 if abs(scaled) >= 100 else 1 if abs(scaled) >= 10 else 2
            return f"{scaled:.{decimals}f}{suffix}"
    return f"{score:,.0f}"


def readme(entries: list[dict]) -> str:
    lines = [
        "# Best contest submissions",
        "",
        "This directory is generated by `python3 tools/fetch_best_submissions.py`.",
        "Each `.man` file is the exact source downloaded for our best completed",
        "submission to that graded problem. `manifest.json` records the submission ID,",
        "official score, dimensions, and SHA-256 digest.",
        "Program bytes are preserved as delivered, including trailing spaces.",
        "",
        "| problem | cases | dimensions | exact score | UI score | submission |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for entry in entries:
        score = entry["score"]
        score_text = f"{score:,.0f}" if score is not None else ""
        lines.append(
            f"| {entry['slug']} | {entry['casesPassed']}/{entry['casesTotal']} | "
            f"{entry['width']}x{entry['height']} | {score_text} | "
            f"{compact_score(score) if score is not None else ''} | "
            f"`{entry['submissionId']}` |"
        )
    lines.extend(
        [
            "",
            "Refresh this directory after new submissions. The dashboard session cookie",
            "is read from `ICFPC_COOKIE` or `~/.icfpc-cookie` and is never written here.",
            "",
        ]
    )
    return "\n".join(lines)


def replace_directory(staged: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    backup = output.with_name(output.name + ".previous")
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        output.replace(backup)
    try:
        staged.replace(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.replace(output)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def fetch(output: Path, cookie_file: Path, jobs: int = 8) -> list[dict]:
    cookie = load_cookie(cookie_file)
    problems = request_json("/public/problems")
    if not isinstance(problems, list):
        raise FetchError("public problem response was not a list")
    graded = [problem for problem in problems if problem.get("status") == "graded"]
    if not graded:
        raise FetchError("public problem response contained no graded problems")

    best = {}
    for problem in sorted(graded, key=lambda item: item["slug"]):
        slug = problem["slug"]
        query = urllib.parse.urlencode({"problemId": problem["id"]})
        rows = request_json(f"/dashboard/submissions?{query}", cookie=cookie)
        if not isinstance(rows, list):
            raise FetchError(f"{slug}: submission history response was not a list")
        selected = select_best(rows).get(problem["name"])
        if selected is None:
            raise FetchError(f"{slug}: no completed, scored submission found")
        best[slug] = (problem, selected)

    details = {}
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(submission_detail, row["id"]): row["id"]
            for _, row in best.values()
        }
        for future in as_completed(futures):
            submission_id = futures[future]
            details[submission_id] = future.result()

    for slug, (problem, row) in best.items():
        merged = dict(row)
        merged.update(details[row["id"]])
        merged["id"] = row["id"]
        merged["problemName"] = problem["name"]
        best[slug] = (problem, merged)

    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent.resolve()))
    )
    entries = []
    try:
        for slug, (_problem, row) in sorted(best.items()):
            body = request(
                f"{lib.BASE}/dashboard/submissions/{row['id']}/download",
                cookie=cookie,
                timeout=120,
            )
            program = decode_program(body, row)
            entry = manifest_entry(slug, row, program)
            (staged / entry["file"]).write_text(program, encoding="ascii")
            entries.append(entry)
            print(
                f"{slug:25} {entry['casesPassed']}/{entry['casesTotal']}  "
                f"{entry['width']}x{entry['height']}  {entry['score']:,.0f}"
            )

        generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        manifest = {
            "generatedAt": generated_at,
            "source": "per-problem dashboard histories and source downloads",
            "selection": "most cases passed, then lowest positive exact score",
            "count": len(entries),
            "submissions": entries,
        }
        (staged / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (staged / "README.md").write_text(readme(entries), encoding="utf-8")
        replace_directory(staged, output)
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"managed output directory (default: {DEFAULT_OUTPUT.relative_to(lib.REPO)})",
    )
    parser.add_argument(
        "--cookie-file",
        type=Path,
        default=DEFAULT_COOKIE_FILE,
        help="dashboard Cookie header file (default: ~/.icfpc-cookie)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=8,
        choices=range(1, 33),
        metavar="1..32",
        help="parallel API detail requests (default: 8)",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output == Path(lib.REPO).resolve():
        parser.error("output directory must not be the repository root")
    try:
        entries = fetch(output, args.cookie_file.expanduser(), args.jobs)
    except FetchError as exc:
        sys.exit(f"error: {exc}")
    print(f"\nwrote {len(entries)} best submissions to {output}")


if __name__ == "__main__":
    main()
