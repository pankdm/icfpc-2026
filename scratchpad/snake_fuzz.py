#!/usr/bin/env python3
"""Adversarial generality harness for solutions/snake/micro4.man.

Builds cases (hand-written scenarios + random legal games), computes the expected
frames with solutions/snake/snake_model.py, and grades the .man with the Rust
engine (`lm --grade`).  Reports every mismatch.

    python3 scratchpad/snake_fuzz.py [--man F] [--fuzz N] [--seed S] [--jobs J]
                                     [--only NAME] [--oracle]
"""
import argparse
import json
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "solutions", "snake"))
import snake_model as M  # noqa: E402

LM = "/Users/dmitrykorolev/projects/icfpc-2026-pfbits/interp/target/release/lm"
if not os.path.exists(LM):
    LM = os.path.join(ROOT, "interp", "target", "release", "lm")
ORACLE = os.path.join(ROOT, "tools", "grade_json.js")

N = 16
DIRS = M.DIRS
OPPOSITE = {2: 4, 4: 2, 3: 5, 5: 3}


# ----------------------------------------------------------------- expectation
def expected_frames(rounds):
    """rounds: list of token-lists.  -> per-round frame lists (model ground truth)."""
    per_round = []
    game = None
    for toks in rounds:
        vals = [int(t) for t in toks]
        if game is None:
            game = M.Snake(vals[0], vals[1])
            per_round.append([game.frame()])
            continue
        if game.over:
            raise ValueError("case continues past a loss: %r" % (rounds,))
        op = vals[0]
        if op == 0:
            game.tick()
            per_round.append([game.frame()])
        elif op == 1:
            game.spawn(vals[1], vals[2])
            per_round.append([game.frame()])
        else:
            game.turn(op)
            per_round.append([])
    return per_round


def trim(rounds):
    """Cut the case at the losing tick -- a real test case ends there."""
    g = None
    out = []
    for toks in rounds:
        v = [int(t) for t in toks]
        out.append(list(v))
        if g is None:
            g = M.Snake(v[0], v[1])
            continue
        if v[0] == 0:
            g.tick()
        elif v[0] == 1:
            g.spawn(v[1], v[2])
        else:
            g.turn(v[0])
        if g.over:
            break
    return out


def max_len(rounds):
    game = None
    best = 1
    for toks in rounds:
        vals = [int(t) for t in toks]
        if game is None:
            game = M.Snake(vals[0], vals[1])
            continue
        op = vals[0]
        if op == 0:
            game.tick()
        elif op == 1:
            game.spawn(vals[1], vals[2])
        else:
            game.turn(op)
        best = max(best, len(game.body))
    return best


def died(rounds):
    game = None
    for toks in rounds:
        vals = [int(t) for t in toks]
        if game is None:
            game = M.Snake(vals[0], vals[1])
            continue
        op = vals[0]
        if op == 0:
            game.tick()
        elif op == 1:
            game.spawn(vals[1], vals[2])
        else:
            game.turn(op)
    return game.over


# ----------------------------------------------------------------- run one case
def run_case(man, rounds, cap=15_000_000):
    frames = expected_frames(rounds)
    inp = " / ".join(" ".join(str(t) for t in r) for r in rounds)
    cmd = [LM, "--grade", man, "--input=" + inp, "--expected=" +
           " / ".join("" for _ in rounds), "--cap=%d" % cap,
           "--frames=" + json.dumps(frames)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    try:
        return json.loads((p.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"status": "engine-error",
                "reason": ((p.stderr or "") + (p.stdout or ""))[:300]}


def run_case_oracle(man, rounds, cap=15_000_000):
    """Same case through the wasm oracle via a temp spec + tools/grade_json.js."""
    import tempfile
    frames = expected_frames(rounds)
    spec = {"scoring": "footprint-tick", "tickCap": cap, "publicTestData": [{
        "name": "fuzz",
        "rounds": [{"in": [str(t) for t in r], "out": [], "frames": f}
                   for r, f in zip(rounds, frames)]}]}
    slug = "snakefuzz"
    path = os.path.join(ROOT, "tests", slug + ".json")
    with open(path, "w") as fh:
        json.dump(spec, fh)
    try:
        p = subprocess.run(["node", ORACLE, slug, man], capture_output=True,
                           text=True, cwd=ROOT, timeout=1800)
        try:
            v = json.loads((p.stdout or "").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"status": "oracle-error",
                    "reason": ((p.stderr or "") + (p.stdout or ""))[:300]}
        r = (v.get("results") or [{}])[0]
        return {"status": r.get("status"), "settleTick": r.get("settleTick"),
                "reason": r.get("reason")}
    finally:
        os.remove(path)


# ------------------------------------------------------------- hand scenarios
def sc_wall(sx, sy, d):
    """Start at (sx,sy), face d, walk straight into that wall."""
    r = [[sx, sy]]
    if d != 3:
        r.append([d])
    x, y = sx, sy
    dx, dy = DIRS[d]
    while 0 <= x + dx < N and 0 <= y + dy < N:
        x, y = x + dx, y + dy
        r.append([0])
    r.append([0])              # the losing tick
    return r


def hand_cases():
    cases = {}

    # -- 1. immediate loss: one round of setup, one tick, dead ---------------
    cases["die-immediately-right"] = [[15, 7], [0]]
    cases["die-immediately-left"] = [[0, 7], [5], [0]]
    cases["die-immediately-up"] = [[7, 0], [2], [0]]
    cases["die-immediately-down"] = [[7, 15], [4], [0]]

    # -- 2. death on every wall, from a corner, after a long straight run ----
    for name, (sx, sy, d) in {
            "wall-east": (0, 8, 3), "wall-west": (15, 8, 5),
            "wall-north": (8, 15, 2), "wall-south": (8, 0, 4)}.items():
        cases[name] = sc_wall(sx, sy, d)
    cases["corner-0-0-up"] = [[0, 0], [2], [0]]
    cases["corner-0-0-left"] = [[0, 0], [5], [0]]
    cases["corner-15-15-down"] = [[15, 15], [4], [0]]
    cases["corner-15-15-right"] = [[15, 15], [0]]

    # -- 3. only the starting round ------------------------------------------
    cases["single-round"] = [[8, 8]]
    cases["start-then-spawn-only"] = [[8, 8], [1, 3, 3]]
    cases["start-then-turn-only"] = [[8, 8], [4]]      # zero extra frames

    # -- 4. fruit eaten on the very first tick -------------------------------
    cases["eat-on-first-tick"] = [[4, 4], [1, 5, 4], [0]]
    cases["eat-first-tick-then-die"] = [
        [14, 4], [1, 15, 4], [0], [0]]

    # -- 5. fruit adjacent to the head in every direction --------------------
    cases["fruit-adjacent-behind"] = [[8, 8], [1, 7, 8], [0], [0]]
    cases["fruit-adjacent-above"] = [[8, 8], [1, 8, 7], [0], [2], [0]]
    cases["fruit-adjacent-below"] = [[8, 8], [1, 8, 9], [0], [4], [0]]

    # -- 6. tail-follow is LEGAL (move into the cell the tail just vacated) --
    #    grow to 4, then spiral so the head enters the vacated tail cell.
    cases["tail-follow-4"] = [
        [5, 5], [1, 6, 5], [0], [1, 7, 5], [0], [4], [1, 7, 6], [0],
        [5], [0], [2], [0], [3], [0]]
    #    2-cell snake immediately following its tail
    cases["tail-follow-2"] = [[8, 8], [1, 9, 8], [0], [4], [0], [5], [0], [2], [0]]

    # -- 7. self-collision death ---------------------------------------------
    #    length 5 ring, head walks into its own neck
    cases["self-collision-5"] = [
        [2, 2], [1, 3, 2], [0], [1, 4, 2], [0], [4], [1, 4, 3], [0],
        [5], [1, 3, 3], [0], [2], [0]]

    # -- 8. direction change immediately before a losing tick ----------------
    cases["turn-then-die"] = [[8, 0], [2], [0]]
    cases["turn-turn-then-die"] = [[0, 8], [4], [2], [5], [0]]
    cases["run-turn-die"] = [[8, 8], [0], [0], [0], [2], [0], [0], [0],
                             [0], [0], [0], [0], [0]]

    # -- 9. spawn on the frame right before the losing tick -------------------
    cases["spawn-then-die"] = [[15, 8], [1, 3, 3], [0]]

    # -- 10. growth stress: grow as long as possible in a boustrophedon -------
    for target in (10, 20, 30, 40, 50, 60, 68):
        cases["grow-%d" % target] = grow_case(target)

    # -- 11. longest legal run without growing (pure ticks) -------------------
    cases["long-lap"] = lap_case(laps=6)

    # -- 12. display-address extremes: 0 and 255, and the row-wrap traps ------
    #    moving right off (15,y) must LOSE, not wrap to (0,y+1); moving left
    #    off (0,y) must LOSE, not wrap to (15,y-1).
    cases["addr-0-head"] = [[0, 0], [1, 1, 0], [0], [4], [0]]
    cases["addr-255-head"] = [[14, 15], [1, 15, 15], [0], [0]]
    cases["fruit-at-0"] = [[3, 3], [1, 0, 0], [0], [0]]
    cases["fruit-at-255"] = [[3, 3], [1, 15, 15], [0], [0]]
    cases["no-wrap-right"] = [[13, 5], [0], [0], [0]]          # dies at x=15+1
    cases["no-wrap-left"] = [[2, 5], [5], [0], [0], [0]]        # dies at x=0-1
    cases["row0-full-sweep"] = [[0, 0]] + [[0]] * 16            # 16 ticks: dies at x=16
    cases["col-sweep-down"] = [[7, 0], [4]] + [[0]] * 16

    # -- 13. long snake that then dies by self-collision -----------------------
    cases["grow-30-then-selfhit"] = grow_then_selfhit(30)
    cases["grow-45-then-selfhit"] = grow_then_selfhit(45)

    # -- 13b. redundant / repeated direction rounds ---------------------------
    cases["same-dir-repeat"] = [[4, 4], [3], [0], [3], [0], [3], [0]]
    cases["turn-run-of-3"] = [[4, 4], [0], [4], [4], [4], [0], [0]]
    cases["turn-before-every-tick"] = [
        [4, 4], [4], [0], [3], [0], [4], [0], [3], [0], [2], [0], [3], [0]]
    cases["turn-last-round"] = [[4, 4], [0], [4]]        # ends on a frameless round
    cases["spawn-turn-eat"] = [[4, 4], [1, 4, 5], [4], [0]]

    # -- 14. closed loops: EVERY tick is a tail-follow ------------------------
    for (w, h) in [(2, 2), (2, 3), (3, 3), (4, 3), (4, 4), (6, 5), (8, 6), (16, 16)]:
        cases["loop-%dx%d" % (w, h)] = loop_case(
            w, h, laps=2, x0=0 if w == 16 else 4, y0=0 if h == 16 else 4)

    return cases


def grow_then_selfhit(target):
    """Grow to `target` in a boustrophedon, then double back into the neck."""
    rounds = grow_case(target)
    g = _replay(rounds)
    # find a direction that loses by SELF-COLLISION (not by the wall)
    for d in (2, 3, 4, 5):
        if len(g.body) > 1 and OPPOSITE[g.dir] == d:
            continue
        hx, hy = g.body[-1]
        dx, dy = DIRS[d]
        nx, ny = hx + dx, hy + dy
        if not (0 <= nx < N and 0 <= ny < N):
            continue
        occ = set(g.occ)
        occ.discard(g.body[0])
        if (nx, ny) in occ:
            if d != g.dir:
                rounds.append([d])
            rounds.append([0])
            return rounds
    rounds.append([0])                                  # fall back to a wall death
    return rounds


DIRCODE = {(0, -1): 2, (1, 0): 3, (0, 1): 4, (-1, 0): 5}


def _perimeter(x0, y0, w, h):
    cells = [(x0 + i, y0) for i in range(w)]
    cells += [(x0 + w - 1, y0 + j) for j in range(1, h)]
    cells += [(x0 + i, y0 + h - 1) for i in range(w - 2, -1, -1)]
    cells += [(x0, y0 + j) for j in range(h - 2, 0, -1)]
    return cells


def loop_case(w, h, laps=2, x0=4, y0=4):
    """Grow the snake so it exactly fills the perimeter of a w x h rectangle,
    then drive it round and round: EVERY tick is a tail-follow (the head moves
    into the cell the tail vacates on that same tick), which is LEGAL."""
    ring = _perimeter(x0, y0, w, h)
    k = len(ring)
    rounds = [list(ring[0])]
    d = 3
    for i in range(1, k):
        px, py = ring[i - 1]
        nx, ny = ring[i]
        nd = DIRCODE[(nx - px, ny - py)]
        if nd != d:
            rounds.append([nd])
            d = nd
        rounds.append([1, nx, ny])         # fruit exactly where the head goes
        rounds.append([0])
    # now the body IS the ring, head at ring[-1], tail at ring[0]
    for step in range(laps * k):
        cur = ring[(k - 1 + step) % k]
        nxt = ring[(k + step) % k]
        nd = DIRCODE[(nxt[0] - cur[0], nxt[1] - cur[1])]
        if nd != d:
            rounds.append([nd])
            d = nd
        rounds.append([0])
    return rounds


def tail_follow_case(k):
    """Legacy alias -- kept so --only tail-follow still selects something."""
    return None


def _replay(rounds):
    g = None
    for toks in rounds:
        v = [int(t) for t in toks]
        if g is None:
            g = M.Snake(v[0], v[1])
            continue
        if v[0] == 0:
            g.tick()
        elif v[0] == 1:
            g.spawn(v[1], v[2])
        else:
            g.turn(v[0])
    return g


def grow_case(target):
    """Snake at (0,0) heading right; boustrophedon sweep, fruit right in front
    of the head every tick, so it grows on EVERY tick until length == target."""
    rounds = [[0, 0]]
    body = [(0, 0)]
    x, y = 0, 0
    d = 3
    while len(body) < target:
        dx, dy = DIRS[d]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < N and 0 <= ny < N) or (nx, ny) in body:
            # turn down one row, then reverse the horizontal direction
            if y + 1 >= N:
                break
            rounds.append([4])
            rounds.append([1, x, y + 1])
            rounds.append([0])
            body.append((x, y + 1))
            y += 1
            d = 5 if d == 3 else 3
            rounds.append([d])
            continue
        rounds.append([1, nx, ny])
        rounds.append([0])
        body.append((nx, ny))
        x, y = nx, ny
    return rounds


def lap_case(laps=4):
    """A short snake driving many laps around the border -- lots of ticks, no
    growth, exercises the direction pipeline repeatedly."""
    rounds = [[1, 1], [1, 2, 1], [0], [1, 3, 1], [0]]     # length 3 at (1..3,1)
    ring = ([(i, 1) for i in range(1, 15)] + [(14, j) for j in range(2, 15)]
            + [(i, 14) for i in range(13, 0, -1)] + [(1, j) for j in range(13, 1, -1)])
    start = ring.index((3, 1))
    d = 3
    cur = (3, 1)
    for step in range(1, laps * len(ring) + 1):
        nxt = ring[(start + step) % len(ring)]
        ddx, ddy = nxt[0] - cur[0], nxt[1] - cur[1]
        nd = {(0, -1): 2, (1, 0): 3, (0, 1): 4, (-1, 0): 5}[(ddx, ddy)]
        if nd != d:
            rounds.append([nd])
            d = nd
        rounds.append([0])
        cur = nxt
    return rounds


# ------------------------------------------------------------------- fuzzer
def random_case(rng, max_rounds=110, p_spawn=0.35, p_turn=0.30, allow_death=True):
    """A random LEGAL game: fruit only on empty cells, one fruit at a time,
    turns never reverse, and the case stops at the losing tick."""
    sx, sy = rng.randrange(N), rng.randrange(N)
    g = M.Snake(sx, sy)
    rounds = [[sx, sy]]
    while len(rounds) < max_rounds:
        roll = rng.random()
        if g.fruit is None and roll < p_spawn:
            free = [(x, y) for x in range(N) for y in range(N) if (x, y) not in g.occ]
            fx, fy = rng.choice(free)
            g.spawn(fx, fy)
            rounds.append([1, fx, fy])
            continue
        if roll < p_spawn + p_turn:
            choices = [d for d in (2, 3, 4, 5)
                       if d != OPPOSITE[g.dir] and d != g.dir]
            if len(g.body) == 1:
                choices = [d for d in (2, 3, 4, 5) if d != g.dir]
            nd = rng.choice(choices)
            g.turn(nd)
            rounds.append([nd])
            continue
        # a tick.  if it loses and we don't want death yet, try to steer away.
        if not allow_death:
            probe = _would_lose(g)
            if probe:
                alts = [d for d in (2, 3, 4, 5)
                        if d != OPPOSITE[g.dir] and d != g.dir]
                rng.shuffle(alts)
                saved = g.dir
                pick = None
                for d in alts:
                    g.dir = d
                    if not _would_lose(g):
                        pick = d
                        break
                g.dir = saved
                if pick is None:
                    break
                g.turn(pick)
                rounds.append([pick])
                continue
        g.tick()
        rounds.append([0])
        if g.over:
            break
    return rounds


def hunter_case(rng, max_rounds=140, max_len_cap=60, near=None, die_at_end=False):
    """A game that ACTUALLY GROWS: fruit is spawned on an empty cell (optionally
    adjacent to the head) and the snake is steered greedily toward it, avoiding
    suicide.  This is what exercises the body FIFO and the collision scan."""
    sx, sy = rng.randrange(N), rng.randrange(N)
    g = M.Snake(sx, sy)
    rounds = [[sx, sy]]

    def safe(d):
        saved, g.dir = g.dir, d
        bad = _would_lose(g)
        g.dir = saved
        return not bad

    while len(rounds) < max_rounds - 2 and len(g.body) < max_len_cap:
        if g.fruit is None:
            hx, hy = g.body[-1]
            if near:
                cand = [(hx + dx, hy + dy) for dx, dy in
                        ((0, -1), (1, 0), (0, 1), (-1, 0))]
            else:
                cand = [(x, y) for x in range(N) for y in range(N)]
            free = [c for c in cand
                    if 0 <= c[0] < N and 0 <= c[1] < N and c not in g.occ]
            if free:
                fx, fy = rng.choice(free)
                g.spawn(fx, fy)
                rounds.append([1, fx, fy])
                continue
        # steer toward the fruit, preferring the axis with the larger gap
        hx, hy = g.body[-1]
        fx, fy = g.fruit if g.fruit else (rng.randrange(N), rng.randrange(N))
        want = []
        if fx > hx:
            want.append(3)
        if fx < hx:
            want.append(5)
        if fy > hy:
            want.append(4)
        if fy < hy:
            want.append(2)
        rng.shuffle(want)
        order = want + [d for d in (2, 3, 4, 5) if d not in want]
        pick = None
        for d in order:
            if len(g.body) > 1 and d == OPPOSITE[g.dir]:
                continue
            if safe(d):
                pick = d
                break
        if pick is None:
            break                                   # trapped: stop before dying
        if pick != g.dir:
            g.turn(pick)
            rounds.append([pick])
        g.tick()
        rounds.append([0])
        if g.over:
            break
    if die_at_end and not g.over:
        # force a losing tick: aim at whichever neighbour kills us
        for d in (2, 3, 4, 5):
            if len(g.body) > 1 and d == OPPOSITE[g.dir]:
                continue
            saved, g.dir = g.dir, d
            if _would_lose(g):
                if d != saved:
                    rounds.append([d])
                g.tick()
                rounds.append([0])
                break
            g.dir = saved
    return rounds


def _would_lose(g):
    hx, hy = g.body[-1]
    dx, dy = DIRS[g.dir]
    nx, ny = hx + dx, hy + dy
    if not (0 <= nx < N and 0 <= ny < N):
        return True
    if g.fruit is not None and (nx, ny) == g.fruit:
        return False
    occ = set(g.occ)
    occ.discard(g.body[0])
    return (nx, ny) in occ


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--man", default=os.path.join(ROOT, "solutions", "snake", "micro4.man"))
    ap.add_argument("--fuzz", type=int, default=120)
    ap.add_argument("--hunt", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20260726)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--only", default=None)
    ap.add_argument("--oracle", action="store_true", help="re-run failures on the wasm oracle")
    ap.add_argument("--cap", type=int, default=15_000_000)
    args = ap.parse_args()

    cases = dict(hand_cases())
    rng = random.Random(args.seed)
    for i in range(args.fuzz):
        for tries in range(50):
            r = random_case(rng, max_rounds=rng.choice([12, 30, 60, 110, 200]),
                            allow_death=(i % 3 != 0))
            if len(r) >= 3:
                break
        cases["fuzz-%03d" % i] = r
    # deliberately long random games that never die -> maximum tick count
    for i in range(8):
        cases["survivor-%02d" % i] = random_case(
            rng, max_rounds=300, p_spawn=0.45, p_turn=0.25, allow_death=False)
    # growth-seeking games: these are the ones that stress the body FIFO,
    # the collision scan and tail-follow in random board shapes.
    for i in range(args.hunt):
        cases["hunt-%03d" % i] = hunter_case(
            rng, max_rounds=rng.choice([40, 92, 130, 180]),
            max_len_cap=rng.choice([8, 20, 45, 60]),
            near=(i % 2 == 0), die_at_end=(i % 3 == 0))

    cases = {k: trim(v) for k, v in cases.items()}
    if args.only:
        cases = {k: v for k, v in cases.items() if args.only in k}

    fails = []
    results = {}

    def work(item):
        name, rounds = item
        try:
            v = run_case(args.man, rounds, args.cap)
        except subprocess.TimeoutExpired:
            v = {"status": "timeout"}
        return name, rounds, v

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = [ex.submit(work, it) for it in cases.items()]
        for f in as_completed(futs):
            name, rounds, v = f.result()
            results[name] = (rounds, v)

    for name in cases:
        rounds, v = results[name]
        ok = v.get("status") == "pass"
        tag = "PASS" if ok else "FAIL"
        info = "K=%d rounds=%d died=%s" % (max_len(rounds), len(rounds), died(rounds))
        print("%s %-26s %-34s tick=%-8s %s" % (
            tag, name, info, v.get("settleTick"),
            "" if ok else (v.get("status", "") + " " + str(v.get("reason", ""))[:160])))
        if not ok:
            fails.append((name, rounds, v))

    print("\n%d/%d passed" % (len(cases) - len(fails), len(cases)))
    if fails:
        out = os.path.join(HERE, "snake_fuzz_failures.json")
        with open(out, "w") as fh:
            json.dump([{"name": n, "rounds": r, "result": v} for n, r, v in fails],
                      fh, indent=1)
        print("failures written to", out)
        if args.oracle:
            print("\n-- oracle re-check --")
            for n, r, v in fails:
                print(" ", n, run_case_oracle(args.man, r, args.cap))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
