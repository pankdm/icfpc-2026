"""Shared helpers for littleman submission/standings tooling (stdlib only)."""
import json
import os
import urllib.request
import urllib.error

BASE = "https://icfpcontest2026.com/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def api_key():
    env = os.path.join(REPO, ".env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if line.startswith("API_KEY"):
                _, _, v = line.partition("=")
                return v.strip().strip("'\"")
    return os.environ.get("API_KEY")


def _request(method, path, key=None, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("User-Agent", "icfpc2026-team-tools/1.0")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "null")
        except Exception:
            return e.code, None


def list_problems():
    _, j = _request("GET", "/public/problems")
    return j or []


def fetch_problem(slug):
    _, j = _request("GET", f"/public/problems/{slug}")
    return j


def problem_standings(problem_id):
    status, j = _request("GET", f"/standings/problems/{problem_id}")
    return j if status == 200 else None


def submit(key, problem_id, program):
    return _request("POST", "/submissions", key=key,
                    body={"problemId": problem_id, "program": program})


def poll(key, sub_id):
    return _request("GET", f"/submissions/{sub_id}", key=key)


def read_man(path):
    with open(path) as f:
        return f.read()
