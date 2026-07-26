#!/usr/bin/env python3
"""peep.py — strength reduction / peephole SUPEROPTIMIZATION of register-op runs.

The optimizing compiler's middle end. `tools/lift.py` recovers the basic blocks of a
`.man` program; this pass takes every maximal straight run of REGISTER-ONLY instruction
cells inside those blocks and asks a superoptimizer for the SHORTEST instruction string
with exactly the same effect on (A, B, BP). Historically the biggest hand-found wins in
this repo were exactly this shape — the brackets bit-op classifier (1.75x) and the tcp
`w & X` gadget (1.49x) — so it is worth doing mechanically.

Three things make it safe enough to run unattended:

  1. THE SEMANTICS MODEL IS ORACLE-VALIDATED.  A peephole pass built on guessed semantics
     is worse than none, so `--validate` fuzzes the Python model in this file against the
     reference interpreter (`sim/harness.js`): it builds a one-room .man per random op
     string, steps the real machine to `H`, and compares the machine's own a/b/backpack
     against the model.  Run it before trusting anything else here.

  2. EQUIVALENCE IS CHECKED ON ALL THREE REGISTERS over a large adversarial state set
     (0, +-1, small ints, powers of two, +-2^63, shift boundaries 0/63/64, random 64-bit
     values).  A rewrite that fixes A but clobbers BP is wrong, and this catches it.

  3. EVERY CANDIDATE IS GRADE-GATED on the real oracle exactly like tools/polish.py:
     accepted only if it still passes every public case and does not raise the score.
     The input .man is never modified; output goes to `<name>-peep.man`.

A shorter run does NOT by itself save ticks — the man still walks the same cells, the
freed ones just become blanks (a no-op). What it buys is FREE CELLS, which is the raw
material for `tools/fold.py` / `tools/place.py`, and, when the freed cells happen to line
up, a deletable blank row/column (`--compact`) which does shrink the box and the walk.

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
        self.best: dict[tuple, str] = {}
        ident = tuple(self.states)
        self.best[ident] = ""
        frontier = {ident: ""}
        total = 1
        for d in range(1, depth + 1):
            nxt: dict[tuple, str] = {}
            for sig, s in frontier.items():
                for op in alphabet:
                    nsig = tuple(_step(op, *st) for st in sig)
                    if nsig in self.best or nsig in nxt:
                        continue
                    nxt[nsig] = s + op
            for sig, s in nxt.items():
                self.best[sig] = s
            frontier = nxt
            total += len(nxt)
            if not quiet:
                print(f"   depth {d}: {len(nxt):>8,} new behaviours "
                      f"({total:,} total)", flush=True)

    def signature(self, s: str) -> tuple:
        return tuple(run_ops(s, st) for st in self.states)

    def lookup(self, s: str) -> str | None:
        """The shortest known string with the same behaviour on the sample, if shorter."""
        cand = self.best.get(self.signature(s))
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
    return "\n".join(rows) + ("\n" if trailing_nl else "")


def pad_rows(rows: list[str]) -> list[str]:
    w = max((len(r) for r in rows), default=0)
    return [r.ljust(w) for r in rows]


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


def traversal_map(rows: list[str], rooms: list[dict]) -> tuple[dict, dict]:
    """cell -> set of headings it is entered with, and cell -> set of predecessor cells.

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
                stack.append((nxt, d))     # a copy is born on the side cell, same heading
                stack.append((nxt, nd))    # ...and be conservative about its heading too
        for nd in outs:
            nxt = (x + nd[0], y + nd[1])
            preds.setdefault(nxt, set()).add(pos)
            stack.append((nxt, nd))
    return heads, preds


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
    __slots__ = ("cells", "text", "man", "dirn")

    def __init__(self, cells, text, man, dirn):
        self.cells, self.text, self.man, self.dirn = cells, text, man, dirn

    def __repr__(self):
        return f"Run(man{self.man} {self.cells[0]}->{self.cells[-1]} {self.text!r})"


def extract_runs(rows: list[str], ir: dict, verbose: bool = False) -> tuple[list[Run], dict]:
    """Maximal straight runs of register-only cells, from lift.py's basic blocks."""
    rooms = ir.get("rooms") or []
    heads, preds = traversal_map(rows, rooms)
    lits = literal_cells(rows)
    # A cell claimed by more than one man's blocks is shared: leave it alone.
    owners: dict[tuple, int] = {}
    for mi, man in enumerate(ir["men"]):
        for blk in man["blocks"]:
            for (x, y), _ch in blk:
                owners[(x, y)] = owners.get((x, y), 0) + 1

    runs: list[Run] = []
    stats = {"blocks": 0, "cells": 0, "runs": 0, "rejected_shared": 0,
             "rejected_literal": 0, "rejected_multihead": 0, "rejected_joined": 0}
    for mi, man in enumerate(ir["men"]):
        for blk in man["blocks"]:
            stats["blocks"] += 1
            cur: list[tuple[tuple[int, int], str]] = []
            seq: list[list] = []
            for (x, y), ch in blk:
                pos = (x, y)
                stats["cells"] += 1
                ok = ch in RUN_GLYPHS
                if ok and pos in lits:
                    stats["rejected_literal"] += 1
                    ok = False
                if ok and owners.get(pos, 0) != 1:
                    stats["rejected_shared"] += 1
                    ok = False
                if ok and len(heads.get(pos, ())) != 1:
                    stats["rejected_multihead"] += 1
                    ok = False
                if ok and cur:
                    px, py = cur[-1][0]
                    step = (x - px, y - py)
                    if step not in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        seq.append(cur)
                        cur = []
                    elif preds.get(pos, set()) - {(px, py)}:
                        # somebody else can enter this cell: the run must break here
                        stats["rejected_joined"] += 1
                        seq.append(cur)
                        cur = []
                if ok:
                    cur.append((pos, ch))
                else:
                    if cur:
                        seq.append(cur)
                    cur = []
            if cur:
                seq.append(cur)
            for run in seq:
                if len(run) < 2:
                    continue
                cells = [p for p, _ in run]
                text = "".join(c for _, c in run)
                d = (cells[1][0] - cells[0][0], cells[1][1] - cells[0][1])
                runs.append(Run(cells, text, mi, d))
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
    """Splice the shorter string into the run's cells; the freed cells become blanks."""
    new = list(rows)
    filled = cand.ljust(ln) if align == "end" else cand.rjust(ln)
    for k, ch in enumerate(filled):
        x, y = r.cells[i + k]
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
    print("== identities (each LHS is replaced by the strictly shorter RHS)")
    seen = set()
    shown = 0
    for sig, short in sorted(table.best.items(), key=lambda kv: len(kv[1])):
        pass
    # enumerate short strings and report the interesting collisions
    cands = []
    for ln in (2, 3):
        stack = [""]
        for _ in range(ln):
            stack = [s + op for s in stack for op in ALPHABET]
        for s in stack:
            r = table.lookup(s)
            if r is not None and equivalent(s, r, states):
                cands.append((len(s) - len(r), s, r))
    cands.sort(key=lambda t: (-t[0], t[1]))
    for gain, s, r in cands:
        key = (s, r)
        if key in seen:
            continue
        seen.add(key)
        print(f"   {s!r:>8}  ==  {r!r:<8}  (saves {gain} cell{'s' if gain > 1 else ''})")
        shown += 1
        if shown >= top:
            break
    print(f"   ... {len(cands)} shortenings of length<=3 strings in total")


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
    runs, stats = extract_runs(rows, ir, args.verbose)
    n_cells = sum(len(r.cells) for r in runs)
    print(f"   lift: {len(ir['men'])} men, {stats['blocks']} blocks, {stats['cells']} block cells")
    print(f"   register-only runs: {len(runs)} covering {n_cells} cells "
          f"(rejected: {stats['rejected_literal']} literal, {stats['rejected_shared']} shared, "
          f"{stats['rejected_multihead']} multi-heading, {stats['rejected_joined']} joined)")
    if args.verbose:
        for r in runs:
            print(f"      man{r.man} {r.cells[0]} dir{r.dirn} {r.text!r}")

    print(f"   building superoptimizer table to depth {args.depth} "
          f"(verification set: {len(states)} states)")
    t0 = time.time()
    table = Table(args.depth)
    print(f"   table built in {time.time() - t0:.1f}s")

    rw = find_rewrites(runs, table, states, args.verbose)
    print(f"   shortenings found: {len(rw)} run(s), {sum(x[4] for x in rw)} cell(s) freed")
    for r, i, ln, cand, gain in rw:
        print(f"      man{r.man} @{r.cells[i]} dir{r.dirn}: {r.text[i:i+ln]!r} -> {cand!r} "
              f"(-{gain})   [run {r.text!r}]")
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
        texts = [render(apply_rewrite(rows, *x[:4], align=args.align), trailing_nl)
                 for x in rw]
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
