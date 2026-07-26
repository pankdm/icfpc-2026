#!/usr/bin/env python3
"""peep.py — strength reduction / peephole SUPEROPTIMIZATION of register-op runs.

The optimizing compiler's middle end. `tools/lift.py` recovers the basic blocks of a
`.man` program; this pass takes every run of REGISTER-ONLY instruction cells along a
man's path and asks a superoptimizer for the SHORTEST instruction string with exactly the
same effect on (A, B, BP). Historically the biggest hand-found wins in this repo were
exactly this shape — the brackets bit-op classifier (1.75x) and the tcp `w & X` gadget
(1.49x) — so it is worth doing mechanically.

A run is not limited to one straight line. Turn glyphs have no effect on the registers, so
a run CHAINS THROUGH them: the turns stay pinned exactly where they are (the path, the
tick count and the walls are untouched) and only the op cells between them are rewritten.
That is what lets the pass see `...M` `>` `1...` as the single string `M1` and collapse it.

Four things make it safe enough to run unattended:

  1. THE SEMANTICS MODEL IS ORACLE-VALIDATED.  A peephole pass built on guessed semantics
     is worse than none, so `--validate` fuzzes the Python model in this file against the
     reference interpreter (`sim/harness.js`): it builds a one-room .man per random op
     string, steps the real machine to `H`, and compares the machine's own a/b/backpack
     against the model.  Run it before trusting anything else here.

  2. EQUIVALENCE IS CHECKED ON ALL THREE REGISTERS over a large adversarial state set
     (0, +-1, small ints, powers of two, +-2^63, shift boundaries 0/63/64, random 64-bit
     values).  A rewrite that fixes A but clobbers BP is wrong, and this catches it.

  3. THE ROOM/PIPE TOPOLOGY MUST NOT MOVE. `+`, `-` and `|` are ordinary instructions
     inside a room, so a rewrite could in principle re-shape a room or invent a pipe;
     every candidate is re-analysed by the reference loader and refused if its rooms or
     pipes differ from the baseline's.

  4. EVERY CANDIDATE IS GRADE-GATED on the real oracle exactly like tools/polish.py:
     accepted only if it still passes every public case and does not raise the score.
     The input .man is never modified; output goes to `<name>-peep.man`.

Note that (2) is the load-bearing check, not (4). On sudoku-validity the naive rewrite at
the site this pass found (just delete the redundant-looking cell) still passes 6/6 public
cases while being plainly wrong on the registers — the public suite would have waved it
through. Only the equivalence proof stops it.

A shorter run does NOT by itself save ticks — the man still walks the same cells, the
freed ones just become blanks (a no-op). What it buys is FREE CELLS, which is the raw
material for `tools/fold.py` / `tools/place.py`, and, when the freed cells happen to line
up, a deletable blank row/column (`--compact`) which does shrink the box and the walk.
So the usual outcome is a score-neutral, verified rewrite: the file is only written when
the score strictly drops, unless you pass `--allow-equal` to keep the freed cells.

  python3 tools/peep.py --validate                     oracle-check the semantics model
  python3 tools/peep.py --identities                   print the identity catalogue
  python3 tools/peep.py <slug> <file.man> --dry-run    scan + report rewrites, no grading
  python3 tools/peep.py <slug> <file.man>              scan, splice, grade-gate, write
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GRADER = REPO / "tools" / "grade_json.js"
LIFT = REPO / "tools" / "lift.py"

MASK = (1 << 64) - 1
MIN64 = -(1 << 63)
MAX64 = (1 << 63) - 1


def w64(v: int) -> int:
    """Wrap to signed 64-bit, the way every littleman register does."""
    v &= MASK
    return v - (1 << 64) if v >> 63 else v


# ---------------------------------------------------------------- the semantics model
#
# Register-only instruction set (PROBLEM.md "Instruction Set").  Everything that touches
# geometry (> < ^ v V X d a x Y H), the pipes (s S r R U q) or a literal (`) is excluded:
# this pass only ever rewrites straight-line, side-effect-free arithmetic.
#
# State is the triple (A, B, BP).  Corner cases that are easy to guess wrong and that the
# oracle fuzz in `--validate` pins down:
#   '%'  takes the DIVISOR's sign (Python's % already does) and yields 0 when B == 0.
#   '/'  is FLOORED division: quotient -> A, remainder -> B.  When B == 0 it gives A = 0
#        and leaves the DIVIDEND in B — i.e. a one-cell "B := A, A := 0".
#   '{'  yields 0 unless 0 <= B <= 63.   '}' yields 0 when B < 0 and SIGN-FILLS when B > 63.
#   ']'  is an arithmetic (sign-preserving) right shift of BP by one.
#   'N'  negates A; N(-2^63) wraps back to -2^63.

NOP_GLYPHS = " ."
DIGITS = "0123456789"
REG_OPS = DIGITS + "MWbm]+-*%/N&|~{}"     # every op this pass understands, minus the nops
ALPHABET = REG_OPS                        # search alphabet (no nops: they never shorten)
RUN_GLYPHS = set(REG_OPS) | set(NOP_GLYPHS)


def _step(op: str, a: int, b: int, p: int) -> tuple[int, int, int]:
    if op in DIGITS:
        return int(op), b, p
    if op == "M":
        return a, a, p
    if op == "W":
        return b, a, p
    if op == "b":
        return a, b, a
    if op == "m":
        return a, b, w64(p - 1)
    if op == "]":
        return a, b, p >> 1                       # Python >> is already arithmetic
    if op == "+":
        return w64(a + b), b, p
    if op == "-":
        return w64(a - b), b, p
    if op == "*":
        return w64(a * b), b, p
    if op == "%":
        return (0 if b == 0 else w64(a % b)), b, p
    if op == "/":
        if b == 0:
            return 0, a, p                        # A := 0, B keeps the dividend
        return w64(a // b), w64(a - (a // b) * b), p
    if op == "N":
        return w64(-a), b, p
    if op == "&":
        return w64((a & MASK) & (b & MASK)), b, p
    if op == "|":
        return w64((a & MASK) | (b & MASK)), b, p
    if op == "~":
        return w64((a & MASK) ^ (b & MASK)), b, p
    if op == "{":
        return (w64(a << b) if 0 <= b <= 63 else 0), b, p
    if op == "}":
        if b < 0:
            return 0, b, p
        return (a >> b) if b <= 63 else (a >> 63), b, p
    if op in NOP_GLYPHS:
        return a, b, p
    raise ValueError(f"not a register-only op: {op!r}")


def run_ops(s: str, state: tuple[int, int, int]) -> tuple[int, int, int]:
    a, b, p = state
    for op in s:
        a, b, p = _step(op, a, b, p)
    return a, b, p


# ---------------------------------------------------------------- the oracle bridge

ORACLE_JS = r"""
const { boot } = require(process.argv[1] + '/sim/harness.js');
const progs = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
(async () => {
  const w = await boot();
  const out = [];
  for (const s of progs) {
    const body = '|@' + s + 'H';
    const width = body.length + 1;
    const bar = '+' + '-'.repeat(width - 2) + '+';
    const pad = ' '.repeat(width - body.length - 1);
    const rows = [bar, '|' + ' '.repeat(width - 2) + '|', body + pad + '|',
                  '|' + ' '.repeat(width - 2) + '|', bar];
    const sess = w.newSession();
    let j;
    try { j = JSON.parse(w.load(sess, rows, '', '', '')); }
    catch (e) { out.push({ error: String(e) }); w.closeSession(sess); continue; }
    if (j.type === 'error') { out.push({ error: j.message }); w.closeSession(sess); continue; }
    let n = 0, r = null;
    while (!j.halted && n < s.length + 8) {
      j = JSON.parse(w.step(sess));
      if (j.type === 'error') { j = { fatalErr: j.message }; break; }
      n++;
    }
    if (j.fatalErr) out.push({ error: j.fatalErr });
    else if (j.fatal) out.push({ error: 'fatal:' + JSON.stringify(j.fatal) });
    else {
      r = (j.entities && j.entities.runners && j.entities.runners[0]) || null;
      out.push(r ? { a: r.a, b: r.b, bp: r.backpack, halted: !!r.halted } : { error: 'no runner' });
    }
    w.closeSession(sess);
  }
  // process.exit() truncates a large async stdout write, so hand the answer back in a file
  require('fs').writeFileSync(process.argv[3], JSON.stringify(out));
  process.exit(0);
})().catch(e => {
  require('fs').writeFileSync(process.argv[3], JSON.stringify({ error: String(e) }));
  process.exit(1);
});
"""


def oracle_run(programs: list[str]) -> list[dict]:
    """Run each op string on the REAL interpreter; return its final a/b/backpack."""
    fd_in, tmp_in = tempfile.mkstemp(suffix=".json")
    fd_out, tmp_out = tempfile.mkstemp(suffix=".json")
    os.close(fd_out)
    try:
        with os.fdopen(fd_in, "w") as fh:
            json.dump(programs, fh)
        p = subprocess.run(["node", "-e", ORACLE_JS, str(REPO), tmp_in, tmp_out],
                           cwd=str(REPO), capture_output=True, text=True, timeout=3600)
        raw = Path(tmp_out).read_text() if os.path.getsize(tmp_out) else ""
        if not raw:
            raise RuntimeError(f"oracle produced no output: {(p.stderr or p.stdout)[:300]}")
        res = json.loads(raw)
        if isinstance(res, dict):
            raise RuntimeError(f"oracle error: {res.get('error')}")
        return res
    finally:
        for t in (tmp_in, tmp_out):
            try:
                os.unlink(t)
            except OSError:
                pass


# ---------------------------------------------------------------- validation

# Prefixes that drive the machine into adversarial register states using nothing but
# register ops (the machine always starts at (0,0,0), so extreme states have to be built).
SEED_PREFIXES = [
    "",              # 0,0,0
    "1M",            # A=1 B=1
    "1N",            # A=-1
    "1NM",           # A=-1 B=-1
    "1M6bmm",        # small BP
    "16M{",          # A = 1<<6  (B=6)
    "1M9M{",         # shift by 9
    "163M{",         # B=63 -> A = -2^63
    "163M{N",        # -(-2^63) wraps
    "163M{1-",       # ...
    "163M{M1W-",     # 2^63-1 territory
    "163M{9-",
    "163M{M~",
    "164M{",         # shift out of range -> 0
    "9M9*M9*M9*",    # 9^4 in A, B chain
    "7M8*3+M",
    "163M{Mb",       # BP = -2^63
    "163M{M1-b]",
    "5M3/",          # / leaves remainder in B
    "5M0W/",
    "1N63M}",        # }
    "163M{63M}",
    "8M3%",
    "8N M3N%",
    # A B strictly outside 0..63 has to be BUILT: a bare "64" is two digit ops ('6' then
    # '4'), not the number 64.  These prefixes are what exercise '{' / '}' out of range
    # and the '}' sign-fill — without them the fuzz silently never tests B > 63.
    "8M*M",          # A=64  B=64
    "8M*M1N",        # A=-1  B=64   -> '}' must SIGN-FILL to -1
    "8M*MNM",        # A=-64 B=-64  -> '}' and '{' must both give 0
    "8M*M1+M",       # A=65  B=65
    "8M*M1+M1N",     # A=-1  B=65
    "9M*M1N",        # A=-1  B=81
    "8M*M63M}",
    "8M*M1N63-M",
    # the 64-bit corners.  "8M*M1W-M1" leaves A=1, B=63, so the next '{' is exactly
    # 1<<63 = -2^63 — the only way to reach MIN64, and the only way the wrap in 'N' and
    # the overflow in '*' ever get exercised.
    "8M*M1W-M1",       # A=1      B=63
    "8M*M1W-M1{",      # A=-2^63  B=63
    "8M*M1W-M1{M",     # A=-2^63  B=-2^63
    "8M*M1W-M1{MN",
    "8M*M1W-M1{M1W-",  # A=2^63-1 B=1
    "8M*M1W-M1{M1W-M",
    "8M*M1W-M1{M1W-M1N",
    "8M*M1W-M1{M1NW",  # A=-2^63 B=-1  -> the '/' quotient-overflow corner
    "8M*M1W-M1{b",     # BP=-2^63      -> the 'm' / ']' backpack corners
    "8M*M1W-M1{M1W-b",
]


def validate(n_random: int = 900, seed: int = 12345, verbose: bool = False) -> int:
    """Fuzz the Python model against the reference interpreter. Returns exit status."""
    rnd = random.Random(seed)
    progs: list[str] = []
    # 1. every single op, and every ordered pair — exhaustive at the lengths that matter
    for pre in SEED_PREFIXES:
        for op in REG_OPS:
            progs.append(pre + op)
    for a in REG_OPS:
        for b in REG_OPS:
            progs.append(a + b)
    # 2. adversarial prefixes followed by random tails
    for _ in range(n_random):
        pre = rnd.choice(SEED_PREFIXES)
        tail = "".join(rnd.choice(REG_OPS + "  ..") for _ in range(rnd.randint(1, 10)))
        progs.append(pre + tail)
    progs = list(dict.fromkeys(progs))

    print(f"== validate: {len(progs)} op strings vs the reference interpreter")
    t0 = time.time()
    got = oracle_run(progs)
    bad, errs = [], 0
    for s, r in zip(progs, got):
        if "error" in r:
            errs += 1
            continue
        want = run_ops(s, (0, 0, 0))
        have = (int(r["a"]), int(r["b"]), int(r["bp"]))
        if want != have:
            bad.append((s, want, have))
    print(f"   {len(progs) - errs - len(bad)}/{len(progs) - errs} agree "
          f"({errs} skipped as load/run errors) in {time.time() - t0:.1f}s")
    if bad:
        print(f"   MISMATCH on {len(bad)} strings — the model is WRONG, do not use it:")
        for s, want, have in bad[:25]:
            print(f"     {s!r}: model {want}  oracle {have}")
        return 1
    print("   OK — the Python model reproduces the reference interpreter exactly on every")
    print("        string tried, on all three registers (A, B, BP).")
    return 0


# ---------------------------------------------------------------- state sets

def _interesting_values() -> list[int]:
    vs = [0, 1, -1, 2, -2, 3, -3, 4, 5, 7, 8, 10, 16, 31, 32, 63, 64, 65,
          -7, -8, -10, -16, -63, -64, -65, 100, -100,
          255, 256, 1023, 1 << 20, -(1 << 20), 1 << 31, -(1 << 31), (1 << 31) - 1,
          1 << 32, -(1 << 32), 1 << 62, -(1 << 62), MAX64, MIN64, MIN64 + 1, MAX64 - 1,
          0x5555555555555555, w64(0xAAAAAAAAAAAAAAAA), w64(0x0F0F0F0F0F0F0F0F),
          w64(0xFFFFFFFF00000000), 0xFFFFFFFF, 6148914691236517205]
    return vs


def make_states(n_random: int, seed: int) -> list[tuple[int, int, int]]:
    """(A, B, BP) samples: adversarial corners first, then random 64-bit noise."""
    rnd = random.Random(seed)
    vals = _interesting_values()
    st: list[tuple[int, int, int]] = []
    # B drives every shift/divide corner case, so sweep it hard against a few As.
    for b in vals:
        for a in (0, 1, -1, 7, -7, MAX64, MIN64, 0x5555555555555555):
            st.append((a, b, 3))
    for a in vals:
        st.append((a, 1, -1))
        st.append((a, -1, 0))
        st.append((a, 0, a))
    for _ in range(n_random):
        st.append((w64(rnd.getrandbits(64)), rnd.choice(
            [w64(rnd.getrandbits(64)), rnd.randint(-70, 70), rnd.choice(vals)]),
            w64(rnd.getrandbits(64))))
    return list(dict.fromkeys(st))


def sig_states(seed: int = 7) -> list[tuple[int, int, int]]:
    """The small state vector used to key the superoptimizer table (32 states)."""
    rnd = random.Random(seed)
    base = [(0, 0, 0), (1, 1, 1), (-1, -1, -1), (7, 3, 5), (-7, 3, -5), (7, -3, 5),
            (MIN64, -1, 0), (MAX64, 2, 1), (0, 63, 0), (1, 63, 2), (-1, 64, 3),
            (5, 0, 9), (0, 5, -9), (123456789, 1000, 17), (-123456789, -1000, -17),
            (0x5555555555555555, 4, 8), (MIN64, 63, MIN64), (MAX64, -64, MAX64),
            (2, 65, 1), (-2, -65, -1), (1 << 40, 40, 40), (3, 3, 3)]
    while len(base) < 32:
        base.append((w64(rnd.getrandbits(64)), rnd.choice([w64(rnd.getrandbits(64)),
                     rnd.randint(-70, 70)]), w64(rnd.getrandbits(64))))
    return base


# ---------------------------------------------------------------- the superoptimizer

class Table:
    """Shortest-string-per-behaviour table, built by exhaustive enumeration.

    Behaviour is keyed by the effect on a fixed vector of sample states, so two strings
    collide only if they agree on all 32 of them; a match is always RE-VERIFIED on the
    big adversarial state set before it is allowed anywhere near the grid. Equivalence
    classes are collapsed at every level (two prefixes that agree on the sample agree on
    the sample under any extension), which is what keeps depth 4-5 tractable.
    """

    def __init__(self, depth: int, alphabet: str = ALPHABET, quiet: bool = False):
        self.states = sig_states()
        self.depth = depth
        # keyed by HASH of the signature, not the signature itself: at depth 5 the table
        # holds >1M behaviours and the full 32-state signatures would not fit in memory.
        # A hash collision can only ever propose a bad rewrite, and `equivalent()` on the
        # big state set plus the oracle grade-gate both stand behind it.
        self.best: dict[int, str] = {}
        ident = tuple(self.states)
        self.best[hash(ident)] = ""
        frontier = [(ident, "")]
        total = 1
        for d in range(1, depth + 1):
            last = d == depth           # the deepest level is never extended: keep no sigs
            nxt: list[tuple[tuple, str]] = []
            fresh = 0
            for sig, s in frontier:
                for op in alphabet:
                    nsig = tuple(_step(op, *st) for st in sig)
                    h = hash(nsig)
                    if h in self.best:
                        continue
                    self.best[h] = s + op
                    fresh += 1
                    if not last:
                        nxt.append((nsig, s + op))
            frontier = nxt
            total += fresh
            if not quiet:
                print(f"   depth {d}: {fresh:>9,} new behaviours "
                      f"({total:,} total)", flush=True)

    def signature(self, s: str) -> tuple:
        return tuple(run_ops(s, st) for st in self.states)

    def lookup(self, s: str) -> str | None:
        """The shortest known string with the same behaviour on the sample, if shorter."""
        cand = self.best.get(hash(self.signature(s)))
        if cand is None or len(cand) >= len(s):
            return None
        return cand


def equivalent(a: str, b: str, states: list[tuple[int, int, int]]) -> bool:
    """Full-strength check: identical (A, B, BP) on every sampled state."""
    for st in states:
        if run_ops(a, st) != run_ops(b, st):
            return False
    return True


# ---------------------------------------------------------------- grid + lift

def read_grid(path: Path) -> tuple[list[str], bool]:
    text = path.read_text(encoding="utf-8").replace("\r", "")
    trailing_nl = text.endswith("\n")
    rows = text.split("\n")
    if trailing_nl:
        rows.pop()
    return rows, trailing_nl


def render(rows: list[str], trailing_nl: bool) -> str:
    # trailing blanks are never content (the loader pads short lines anyway), and stripping
    # them keeps the diff against the input readable
    return "\n".join(r.rstrip() for r in rows) + ("\n" if trailing_nl else "")


def pad_rows(rows: list[str]) -> list[str]:
    w = max((len(r) for r in rows), default=0)
    return [r.ljust(w) for r in rows]


ANALYZE_JS = r"""
const { boot } = require(process.argv[1] + '/sim/harness.js');
const grids = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
(async () => {
  const w = await boot();
  const out = grids.map(rows => { try { return w.analyze(rows); }
                                  catch (e) { return JSON.stringify({ error: String(e) }); } });
  require('fs').writeFileSync(process.argv[3], JSON.stringify(out));
  process.exit(0);
})().catch(e => {
  require('fs').writeFileSync(process.argv[3], JSON.stringify([String(e)]));
  process.exit(1);
});
"""


def topologies(grids: list[list[str]]) -> list[str]:
    """The reference loader's room/pipe view of each grid, as a comparable string.

    `+`, `-` and `|` are ordinary instructions inside a room, so blanking one (or writing
    one into a freed cell) could in principle re-shape a room or invent a pipe. Any
    candidate whose topology differs from the baseline's is refused outright rather than
    left to the public tests, which might not notice.
    """
    fd_in, tmp_in = tempfile.mkstemp(suffix=".json")
    fd_out, tmp_out = tempfile.mkstemp(suffix=".json")
    os.close(fd_out)
    try:
        with os.fdopen(fd_in, "w") as fh:
            json.dump(grids, fh)
        p = subprocess.run(["node", "-e", ANALYZE_JS, str(REPO), tmp_in, tmp_out],
                           cwd=str(REPO), capture_output=True, text=True, timeout=1800)
        raw = Path(tmp_out).read_text() if os.path.getsize(tmp_out) else ""
        if not raw:
            raise RuntimeError(f"analyze failed: {(p.stderr or p.stdout)[:300]}")
        out = json.loads(raw)
        res = []
        for t in out:
            d = json.loads(t) if isinstance(t, str) else t
            res.append(json.dumps([d.get("rooms"), d.get("pipes"), d.get("type"),
                                   d.get("message")], sort_keys=True))
        return res
    finally:
        for t in (tmp_in, tmp_out):
            try:
                os.unlink(t)
            except OSError:
                pass


def lift_json(path: Path) -> dict:
    p = subprocess.run([sys.executable, str(LIFT), str(path), "--json"],
                       cwd=str(REPO), capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError(f"lift failed: {(p.stderr or p.stdout)[:300]}")
    return json.loads(p.stdout.strip().splitlines()[-1])


# --- extra safety: a Y-aware walk of our own -------------------------------------

TURNS = {">": (1, 0), "<": (-1, 0), "^": (0, -1), "v": (0, 1), "V": (0, 1)}
BRANCH = set("Xdax")
CW = {(1, 0): (0, 1), (0, 1): (-1, 0), (-1, 0): (0, -1), (0, -1): (1, 0)}
CCW = {v: k for k, v in CW.items()}


def traversal_map(rows: list[str], rooms: list[dict]) -> tuple[dict, dict, dict]:
    """cell -> headings it is entered with, cell -> predecessors, cell -> successors.

    Same movement rules as lift.py, plus the two extra men a `Y` spawns beside itself —
    lift.py only walks from `@`, so a grid containing `Y` has paths it never sees. A run
    is only safe to rewrite when every cell of it is entered on exactly one heading and
    every cell but the first has exactly one predecessor (nobody jumps into the middle).
    """
    h = len(rows)

    def at(x, y):
        return rows[y][x] if 0 <= y < h and 0 <= x < len(rows[y]) else " "

    def inside(x, y):
        for r in rooms:
            (x0, y0), (x1, y1) = r["min"], r["max"]
            if x0 < x < x1 and y0 < y < y1:
                return True
        return False

    heads: dict[tuple, set] = {}
    preds: dict[tuple, set] = {}
    succs: dict[tuple, set] = {}
    stack = [((x, y), (1, 0)) for y in range(h) for x in range(len(rows[y]))
             if rows[y][x] == "@"]
    seen = set()
    while stack:
        pos, d = stack.pop()
        if (pos, d) in seen:
            continue
        seen.add((pos, d))
        x, y = pos
        heads.setdefault(pos, set()).add(d)
        if not inside(x, y):
            continue
        ch = at(x, y)
        if ch == "H":
            continue
        if ch in TURNS:
            outs = [TURNS[ch]]
        elif ch in BRANCH:
            outs = [d, CW[d], CCW[d]]
        else:
            outs = [d]
        if ch == "Y":                      # the two copies start beside Y, keeping heading
            for nd in (CW[d], CCW[d]):
                nxt = (x + nd[0], y + nd[1])
                preds.setdefault(nxt, set()).add(pos)
                succs.setdefault(pos, set()).add(nxt)
                stack.append((nxt, d))     # a copy is born on the side cell, same heading
                stack.append((nxt, nd))    # ...and be conservative about its heading too
        for nd in outs:
            nxt = (x + nd[0], y + nd[1])
            preds.setdefault(nxt, set()).add(pos)
            succs.setdefault(pos, set()).add(nxt)
            stack.append((nxt, nd))
    return heads, preds, succs


# ---------------------------------------------------------------- literal cells

def literal_cells(rows: list[str]) -> set[tuple[int, int]]:
    """Every cell that could belong to a `...` literal — never touch one of these.

    Conservative on purpose: a backtick pairs horizontally AND vertically, so mark the
    backticks plus every cell between two backticks in the same row or the same column.
    """
    bad: set[tuple[int, int]] = set()
    h = len(rows)
    w = max((len(r) for r in rows), default=0)
    for y in range(h):
        xs = [x for x, ch in enumerate(rows[y]) if ch == "`"]
        for i in range(len(xs)):
            bad.add((xs[i], y))
            for j in range(i + 1, len(xs)):
                for x in range(xs[i], xs[j] + 1):
                    bad.add((x, y))
    for x in range(w):
        ys = [y for y in range(h) if x < len(rows[y]) and rows[y][x] == "`"]
        for i in range(len(ys)):
            bad.add((x, ys[i]))
            for j in range(i + 1, len(ys)):
                for y in range(ys[i], ys[j] + 1):
                    bad.add((x, y))
    return bad


# ---------------------------------------------------------------- run extraction

class Run:
    """A rewritable stretch of a man's path.

    `slots` are the cells that hold register ops (or blanks, which are free slots); the
    turn glyphs that may sit between them are PINNED and never move, so the path — and
    therefore the tick count and the room geometry — is bit-for-bit unchanged. `text` is
    the op string the machine actually executes along the stretch, i.e. the slots' glyphs
    concatenated in traversal order with the turns skipped, because a turn has no effect
    on (A, B, BP).

    Straight runs are the special case with no pinned turns; allowing the turns is what
    lets the pass see `...M` `>` `M...` as the string `MM` and collapse it.
    """

    __slots__ = ("slots", "text", "pinned", "head")

    def __init__(self, slots, text, pinned, head):
        self.slots, self.text, self.pinned, self.head = slots, text, pinned, head

    def __repr__(self):
        return f"Run({self.head} {self.text!r} +{len(self.pinned)} turns)"


def extract_runs(rows: list[str], ir: dict, chains: bool = True,
                 verbose: bool = False) -> tuple[list[Run], dict]:
    """Maximal rewritable stretches of every man's path.

    A cell may join a stretch only if it is an ordinary register op / blank / turn glyph
    inside a room, is entered on exactly ONE heading, is not part of a literal, and — for
    every cell after the first — has exactly ONE predecessor, so that nobody can jump into
    the middle of a stretch with different registers.  Branches (X d a x), pipe ops, `Y`,
    `H`, `@` and literals all terminate a stretch; they are never touched.
    """
    rows = pad_rows(rows)
    rooms = ir.get("rooms") or []
    heads, preds, succs = traversal_map(rows, rooms)
    lits = literal_cells(rows)
    lifted_ops = set()
    for man in ir["men"]:
        for k in man["op_cells"]:
            x, y = k.split(",")
            lifted_ops.add((int(x), int(y)))

    def glyph(pos):
        x, y = pos
        return rows[y][x] if 0 <= y < len(rows) and 0 <= x < len(rows[y]) else " "

    stats = {"visited": len(heads), "eligible": 0, "runs": 0, "slots": 0,
             "not_lifted": 0, "reject_glyph": 0, "reject_literal": 0,
             "reject_multihead": 0, "reject_fanout": 0}

    def eligible(pos):
        ch = glyph(pos)
        if ch not in RUN_GLYPHS and not (chains and ch in TURNS):
            stats["reject_glyph"] += 1
            return False
        if pos in lits:
            stats["reject_literal"] += 1
            return False
        if len(heads.get(pos, ())) != 1:
            stats["reject_multihead"] += 1
            return False
        if len(succs.get(pos, ())) != 1:
            stats["reject_fanout"] += 1
            return False
        return True

    elig = {p for p in heads if eligible(p)}
    stats["eligible"] = len(elig)

    # chain heads: an eligible cell whose single predecessor is not an eligible cell that
    # flows only into it (i.e. anything that can be entered from elsewhere starts a chain)
    def linked(a, b):
        return a in elig and b in elig and succs.get(a) == {b} and preds.get(b) == {a}

    runs: list[Run] = []
    used: set = set()
    for pos in sorted(elig, key=lambda p: (p[1], p[0])):
        if pos in used:
            continue
        prev = next(iter(preds.get(pos, ())), None)
        if prev is not None and linked(prev, pos) and prev not in used:
            continue                       # not a head; it will be reached from `prev`
        chain, cur = [], pos
        while cur is not None and cur not in used:
            used.add(cur)
            chain.append(cur)
            nxt = next(iter(succs.get(cur, ())), None)
            cur = nxt if (nxt is not None and linked(cur, nxt) and nxt not in used) else None
        slots = [c for c in chain if glyph(c) not in TURNS]
        pinned = [c for c in chain if glyph(c) in TURNS]
        text = "".join(glyph(c) for c in slots)
        if len(slots) < 2 or text.strip() == "":
            continue
        stats["not_lifted"] += sum(1 for c in slots
                                   if glyph(c) in REG_OPS and c not in lifted_ops)
        stats["slots"] += len(slots)
        runs.append(Run(slots, text, pinned, chain[0]))
    stats["runs"] = len(runs)
    return runs, stats


# ---------------------------------------------------------------- rewriting

def windows(n: int):
    """(start, length) of every contiguous window, longest first."""
    for ln in range(n, 1, -1):
        for i in range(0, n - ln + 1):
            yield i, ln


def find_rewrites(runs: list[Run], table: Table, states, verbose=False):
    """For every run, the best (largest cells-freed) verified shortening, if any.

    Windows are scanned longest-first and the winner is the one that frees the most
    cells; a signature hit is only a candidate until it survives `equivalent()` on the
    full adversarial state set, which is what rules out 32-state coincidences.
    """
    out = []
    for r in runs:
        best = None
        for i, ln in windows(len(r.text)):
            win = r.text[i:i + ln]
            if win.strip() == "":
                continue
            cand = table.lookup(win)
            if cand is None:
                continue
            if not equivalent(win, cand, states):
                if verbose:
                    print(f"      (signature match {win!r} -> {cand!r} failed full "
                          f"verification — rejected)")
                continue
            # The gain that matters is CELLS FREED, not characters dropped: a window that
            # already contains blanks (blanks are no-ops) gains nothing by sliding its ops
            # to one end.  Only glyphs that stop being printed are worth anything, since
            # they are what fold.py / place.py and the bounding box actually see.
            gain = sum(1 for c in win if c != " ") - len(cand)
            if gain > 0 and (best is None or gain > best[3]):
                best = (i, ln, cand, gain)
        if best:
            i, ln, cand, gain = best
            out.append((r, i, ln, cand, gain))
    return out


def apply_rewrite(rows: list[str], r: Run, i: int, ln: int, cand: str,
                  align: str = "end") -> list[str]:
    """Splice the shorter string into the window's slots; freed slots become blanks.

    Only the slot cells change. Pinned turn glyphs stay exactly where they are, so the
    man's path, his tick count and the room walls are untouched — a blank is a no-op he
    walks over, and the freed cells are what fold.py / place.py get to reclaim.
    """
    new = list(rows)
    filled = cand.ljust(ln) if align == "end" else cand.rjust(ln)
    for k, ch in enumerate(filled):
        x, y = r.slots[i + k]
        row = new[y].ljust(max(len(new[y]), x + 1))
        new[y] = row[:x] + ch + row[x + 1:]
    return new


# ---------------------------------------------------------------- grading

class Grader:
    def __init__(self, slug, cap, cases, workdir, jobs=8):
        self.slug, self.cap, self.cases, self.workdir, self.jobs = slug, cap, cases, workdir, jobs
        self.cache: dict[str, dict] = {}
        self.calls = 0

    def _run(self, text: str) -> dict:
        fd, tmp = tempfile.mkstemp(suffix=".man", dir=self.workdir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            cmd = ["node", str(GRADER), self.slug, tmp, "--failfast"]
            if self.cap:
                cmd += ["--cap", str(self.cap)]
            if self.cases:
                cmd += ["--cases", str(self.cases)]
            p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=3600)
            line = ""
            for ln in p.stdout.splitlines():
                ln = ln.strip()
                if ln.startswith("{"):
                    line = ln
            if not line:
                return {"error": (p.stderr or p.stdout or "no output").strip()[:200]}
            return json.loads(line)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def grade(self, text: str) -> dict:
        if text not in self.cache:
            self.calls += 1
            self.cache[text] = self._run(text)
        return self.cache[text]

    def grade_many(self, texts: list[str]) -> list[dict]:
        uniq = list(dict.fromkeys(t for t in texts if t not in self.cache))
        if uniq:
            self.calls += len(uniq)
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
                for t, r in zip(uniq, ex.map(self._run, uniq)):
                    self.cache[t] = r
        return [self.cache[t] for t in texts]


def ok(res: dict) -> bool:
    return (isinstance(res, dict) and "error" not in res and res.get("score") is not None
            and res.get("total") and res.get("passed") == res.get("total"))


def fmt(res: dict) -> str:
    fp = res.get("footprint") or {}
    at = res.get("avgTicks")
    return (f"{fp.get('w')}x{fp.get('h')} box {fp.get('box')} "
            f"avgTicks {at if at is None else round(at, 2)} score {res['score']:,.0f}")


def atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        u = os.umask(0)
        os.umask(u)
        os.chmod(tmp, 0o644 & ~u)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- compaction

def blank_line_deletions(rows: list[str]) -> list[tuple[str, int]]:
    """Interior rows/columns that are now entirely blank — deleting one shrinks the box."""
    w = max((len(r) for r in rows), default=0)
    out = []
    for i, r in enumerate(rows):
        if r.strip() == "":
            out.append(("row", i))
    for c in range(w):
        if all((r[c] if c < len(r) else " ") == " " for r in rows):
            out.append(("col", c))
    return out


def drop(rows: list[str], dr: set[int], dc: set[int]) -> list[str]:
    out = []
    for i, row in enumerate(rows):
        if i in dr:
            continue
        out.append("".join(ch for c, ch in enumerate(row) if c not in dc) if dc else row)
    return out


# ---------------------------------------------------------------- identities

def identity_report(table: Table, states, top: int = 40) -> None:
    """Human-readable strength-reduction identities the table proves."""
    print("== identities: every op string of length 2-3 that a SHORTER string replaces")
    print("   (verified on the full adversarial state set, on all three registers)")
    cands = []
    for ln in (2, 3):
        stack = [""]
        for _ in range(ln):
            stack = [s + op for s in stack for op in ALPHABET]
        for s in stack:
            r = table.lookup(s)
            if r is not None and equivalent(s, r, states):
                cands.append((len(s) - len(r), s, r))
    def is_subseq(short: str, long: str) -> bool:
        it = iter(long)
        return all(c in it for c in short)

    # Most shortenings are structural — a dead store ('05' == '5') or a cancellation
    # ('WW' == '', '+-' == '') — and you can see those by deleting characters. The ones
    # worth knowing are where the replacement uses a DIFFERENT op: real strength reduction.
    dead = [(g, s, r) for g, s, r in cands if is_subseq(r, s)]
    real = [(g, s, r) for g, s, r in cands if not is_subseq(r, s)]
    print(f"\n   {len(dead)} are structural (dead store / cancellation: the RHS is the LHS "
          f"with cells deleted)")
    print(f"   {len(real)} are genuine strength reductions — the RHS uses a different op:")
    by_gain: dict[int, list] = {}
    for gain, s, r in real:
        by_gain.setdefault(gain, []).append((s, r))
    for gain in sorted(by_gain, reverse=True):
        group = by_gain[gain]
        print(f"\n   -- saves {gain} cell{'s' if gain > 1 else ''}: {len(group)} identities")
        for s, r in group[:top]:
            print(f"      {s!r:>7}  ==  {r!r}")
        if len(group) > top:
            print(f"      ... and {len(group) - top} more")
    print(f"\n   {len(cands)} shortenings among the "
          f"{len(ALPHABET) ** 2 + len(ALPHABET) ** 3:,} strings of length 2-3")


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--validate", action="store_true",
                    help="fuzz the semantics model against the reference interpreter")
    ap.add_argument("--identities", action="store_true", help="print the identity catalogue")
    ap.add_argument("--depth", type=int, default=4, help="max replacement length (default 4)")
    ap.add_argument("--states", type=int, default=400,
                    help="random states added to the adversarial verification set")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--cases", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--align", choices=["end", "start"], default="end",
                    help="put the freed blank cells at the end (default) or start of the run")
    ap.add_argument("--no-chains", action="store_true",
                    help="only rewrite straight runs; do not chain across turn glyphs")
    ap.add_argument("--no-compact", action="store_true",
                    help="do not try to delete rows/columns the rewrites blanked out")
    ap.add_argument("--allow-equal", action="store_true",
                    help="also write the file when the score merely ties (frees cells for "
                         "fold.py / place.py without a score win)")
    ap.add_argument("--dry-run", action="store_true", help="scan and report; never grade or write")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.validate:
        return validate()

    states = make_states(args.states, seed=99)
    if args.identities:
        print(f"== building superoptimizer table to depth {args.depth}")
        t = Table(args.depth)
        identity_report(t, states)
        return 0

    if not args.slug or not args.file:
        ap.error("need <slug> <file.man> (or --validate / --identities)")
    src = Path(args.file).resolve()
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 2
    out = Path(args.out).resolve() if args.out else src.with_name(src.stem + "-peep.man")
    if out == src:
        print("refusing to overwrite the input file", file=sys.stderr)
        return 2

    rows, trailing_nl = read_grid(src)
    rows = pad_rows(rows)
    print(f"== peep {src.name}  [{args.slug}]")
    ir = lift_json(src)
    n_blocks = sum(len(m["blocks"]) for m in ir["men"])
    runs, stats = extract_runs(rows, ir, chains=not args.no_chains, verbose=args.verbose)
    n_slots = sum(len(r.slots) for r in runs)
    n_ops = sum(sum(1 for c in r.text if c != " ") for r in runs)
    print(f"   lift: {len(ir['men'])} men, {n_blocks} blocks, "
          f"{sum(m['ops'] for m in ir['men'])} instruction cells")
    print(f"   rewritable runs: {len(runs)} ({n_slots} slots, {n_ops} live ops"
          f"{'' if args.no_chains else ', turns pinned in place'})")
    print(f"   cells refused: {stats['reject_literal']} literal, "
          f"{stats['reject_multihead']} multi-heading, {stats['reject_fanout']} branching, "
          f"{stats['reject_glyph']} non-register")
    if stats["not_lifted"]:
        print(f"   note: {stats['not_lifted']} op cell(s) in these runs are NOT in lift.py's "
              f"op set (expected only for grids with `Y`)")
    if args.verbose:
        for r in runs:
            print(f"      {r.head} {r.text!r}"
                  + (f"  [{len(r.pinned)} pinned turns]" if r.pinned else ""))

    print(f"   building superoptimizer table to depth {args.depth} "
          f"(verification set: {len(states)} states)")
    t0 = time.time()
    table = Table(args.depth)
    print(f"   table built in {time.time() - t0:.1f}s")

    rw = find_rewrites(runs, table, states, args.verbose)
    print(f"   shortenings found: {len(rw)} run(s), {sum(x[4] for x in rw)} cell(s) freed")
    for r, i, ln, cand, gain in rw:
        print(f"      {r.slots[i]}: {r.text[i:i+ln]!r} -> {cand!r} "
              f"(-{gain} cells)   [run {r.text!r}]")
    if not rw:
        print("   NOTHING TO DO: every register-op run is already as short as the "
              f"superoptimizer can prove (depth {args.depth}).")
        return 0
    if args.dry_run:
        print("   --dry-run: nothing graded, nothing written")
        return 0

    with tempfile.TemporaryDirectory(prefix="peep-") as workdir:
        base_g = Grader(args.slug, None, args.cases, workdir, args.jobs)
        base = base_g.grade(render(rows, trailing_nl))
        if not ok(base):
            print(f"   BASELINE DOES NOT PASS: {json.dumps(base)[:300]}")
            return 1
        print(f"   baseline: {fmt(base)}  ({base['passed']}/{base['total']} public)")
        worst = max((r.get("settleTick") or 0) for r in base.get("results", [])) or 0
        cap = args.cap if args.cap is not None else max(1000, worst * 4)
        g = Grader(args.slug, cap or None, args.cases, workdir, args.jobs)
        g.cache[render(rows, trailing_nl)] = base

        # screen every rewrite on its own, in parallel
        grids = [apply_rewrite(rows, *x[:4], align=args.align) for x in rw]
        texts = [render(gr, trailing_nl) for gr in grids]
        topo = topologies([rows] + grids)
        for x, t in zip(rw, topo[1:]):
            if t != topo[0]:
                print(f"      x rejected {x[3]!r}: it changes the room/pipe topology")
        rw = [x for x, t in zip(rw, topo[1:]) if t == topo[0]]
        texts = [t for t, tp in zip(texts, topo[1:]) if tp == topo[0]]
        if not rw:
            print("   every candidate changed the room/pipe topology; nothing to do")
            return 0
        res = g.grade_many(texts)
        good = []
        for x, r in zip(rw, res):
            if ok(r) and r["score"] <= base["score"]:
                good.append(x)
            else:
                why = r.get("error") or (f"{r.get('passed')}/{r.get('total')}"
                                         if r.get("score") is None else f"score {r['score']:,.0f}")
                print(f"      x rejected {x[0].text[x[1]:x[1]+x[2]]!r} -> {x[3]!r}: {why}")
        print(f"   {len(good)}/{len(rw)} rewrite(s) survive the oracle individually")

        # apply cumulatively, re-grading every step (two good rewrites can interact)
        cur = rows
        best = base
        applied = []
        for x in good:
            cand = apply_rewrite(cur, *x[:4], align=args.align)
            if topologies([cand])[0] != topo[0]:
                print(f"      x cumulative re-apply of {x[3]!r} changes the topology")
                continue
            r = g.grade(render(cand, trailing_nl))
            if ok(r) and r["score"] <= best["score"]:
                cur, best = cand, r
                applied.append(x)
            elif args.verbose:
                print(f"      x cumulative re-apply rejected {x[3]!r}")
        print(f"   applied {len(applied)} rewrite(s): {fmt(best)}")

        # optional: turn the freed cells into a smaller box
        if not args.no_compact and applied:
            base_dels = set(blank_line_deletions(rows))
            newly = [d for d in blank_line_deletions(cur) if d not in base_dels]
            if newly:
                print(f"   compact: {len(newly)} newly blank line(s) {newly}")
                dr, dc = set(), set()
                for kind, idx in newly:
                    ndr = dr | ({idx} if kind == "row" else set())
                    ndc = dc | (set() if kind == "row" else {idx})
                    cand = drop(cur, ndr, ndc)
                    r = g.grade(render(cand, trailing_nl))
                    if ok(r) and r["score"] < best["score"]:
                        dr, dc, best = ndr, ndc, r
                        print(f"      + delete {kind} {idx}: {fmt(r)}")
                    elif args.verbose:
                        print(f"      x delete {kind} {idx}: "
                              f"{r.get('error') or r.get('score')}")
                if dr or dc:
                    cur = drop(cur, dr, dc)
            else:
                print("   compact: the freed cells do not line up into a blank row/column")

        print()
        print("== report")
        print(f"   before: {fmt(base)}")
        print(f"   after : {fmt(best)}")
        if best["score"] < base["score"]:
            atomic_write(out, render(cur, trailing_nl))
            print(f"   score {base['score']:,.0f} -> {best['score']:,.0f} "
                  f"({100 * (1 - best['score'] / base['score']):.2f}% better)")
            print(f"   wrote {out}")
            print(f"   verify: node tools/grade.js {args.slug} {out}")
        elif applied and args.allow_equal:
            atomic_write(out, render(cur, trailing_nl))
            print(f"   score unchanged; wrote {out} anyway (--allow-equal) — "
                  f"{sum(x[4] for x in applied)} freed cells for fold.py / place.py")
        elif applied:
            print(f"   {len(applied)} rewrite(s) verified and score-neutral "
                  f"({sum(x[4] for x in applied)} cells freed) but the score did not drop; "
                  f"nothing written (use --allow-equal to keep them).")
        else:
            print("   no rewrite survived the oracle; nothing written.")
        print(f"   {g.calls + base_g.calls} candidate gradings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
