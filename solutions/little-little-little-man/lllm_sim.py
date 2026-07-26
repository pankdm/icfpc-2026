#!/usr/bin/env python3
"""Executes the lllm_flow.py token graph in Python and checks it against the
validated oracle (lllm_model.py) on every public case.

This is the semantics gate.  Geometry (build_lllm.py) can only ever break
things this cannot see -- pipe rebinding, wall hits, literal direction -- so a
failure here is always a logic bug and a failure there is always a layout bug.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lllm_flow as F
import lllm_model as ref

MASK = (1 << 64) - 1


def s64(v):
    v &= MASK
    return v - (1 << 64) if v >= (1 << 63) else v


class Display(object):
    def __init__(self, w=16, h=16):
        self.w, self.h = w, h
        self.n = w * h
        self.cur = [0] * self.n
        self.nxt = [0] * self.n
        self.cursor = 0
        self.frames = []

    def addr(self, v):
        if not (0 <= v < self.n):
            raise ValueError("display ADDR out of range: %d" % v)
        self.cursor = v

    def data(self, v):
        if not (0 <= v < 16):
            raise ValueError("display DATA out of range: %d" % v)
        self.nxt[self.cursor] = v
        self.cursor = (self.cursor + 1) % self.n

    def swap(self, v):
        self.cur = list(self.nxt)
        self.frames.append(list(self.cur))
        if v == 0:
            self.nxt = [0] * self.n
            self.cursor = 0


class Sim(object):
    def __init__(self, flow, inputs, ring_slots=F.RING_SLOTS, trace=None):
        self.flow = flow
        self.inputs = list(inputs)
        self.ip = 0
        self.A = self.B = self.BP = 0
        self.hold = {h: 0 for h in F.HOLDERS}
        self.open = {}                     # holder -> True while an hr is unpaired
        self.ring = []
        self.ring_slots = ring_slots
        self.disp = Display()
        self.steps = 0
        self.trace = trace

    # ------------------------------------------------------------------
    def run(self, want_frames, limit=40_000_000):
        blocks = self.flow.blocks
        order = self.flow.order
        nxt = {order[i]: order[i + 1] for i in range(len(order) - 1)}
        label = order[0]
        while True:
            toks = blocks[label]
            jump = None
            for tok in toks:
                self.steps += 1
                if self.steps > limit:
                    raise RuntimeError("step limit in block %s" % label)
                jump = self.exec_tok(tok, label)
                if jump is not None:
                    break
                if len(self.disp.frames) >= want_frames:
                    return self.disp.frames
            if len(self.disp.frames) >= want_frames:
                return self.disp.frames
            if jump is None:
                jump = nxt.get(label)
                if jump is None:
                    raise RuntimeError("fell off the end at %s" % label)
            label = jump

    # ------------------------------------------------------------------
    def exec_tok(self, tok, label):
        A, B, BP = self.A, self.B, self.BP
        if isinstance(tok, tuple):
            kind = tok[0]
            if kind == "hr":
                h = tok[1]
                if self.open.get(h):
                    raise RuntimeError("holder %s read twice without a write (%s)"
                                       % (h, label))
                self.open[h] = True
                self.A = self.hold[h]
                return None
            if kind == "hw":
                h = tok[1]
                if not self.open.get(h):
                    raise RuntimeError("holder %s written without a read (%s)"
                                       % (h, label))
                self.open[h] = False
                self.hold[h] = self.A
                return None
            if kind == "lit":
                self.A = tok[1]
                return None
            if kind == "in":
                if not self.inputs:
                    raise RuntimeError("input exhausted at %s" % label)
                self.A = self.inputs.pop(0)
                return None
            if kind == "rr":
                if not self.ring:
                    raise RuntimeError("ring underflow at %s" % label)
                self.A = self.ring.pop(0)
                return None
            if kind == "rs":
                self.ring.append(self.A)
                if len(self.ring) > self.ring_slots:
                    raise RuntimeError("ring overflow at %s" % label)
                return None
            if kind == "da":
                self.disp.addr(self.A)
                return None
            if kind == "dd":
                self.disp.data(self.A)
                return None
            if kind == "ds":
                self.disp.swap(self.A)
                return None
            if kind == "br":
                self.BP = self.A                    # 'b'
                return tok[1] if self.BP > 0 else None
            if kind == "brbp":
                return tok[1] if self.BP > 0 else None
            if kind == "go":
                return tok[1]
            raise RuntimeError("unknown token %r" % (tok,))

        # single-glyph ops
        if tok.isdigit():
            self.A = int(tok)
        elif tok == "M":
            self.B = A
        elif tok == "W":
            self.A, self.B = B, A
        elif tok == "b":
            self.BP = A
        elif tok == "m":
            self.BP = s64(BP - 1)
        elif tok == "]":
            self.BP = BP >> 1
        elif tok == "+":
            self.A = s64(A + B)
        elif tok == "-":
            self.A = s64(A - B)
        elif tok == "*":
            self.A = s64(A * B)
        elif tok == "N":
            self.A = s64(-A)
        elif tok == "%":
            self.A = 0 if B == 0 else s64(A - B * (A // B))
        elif tok == "/":
            if B == 0:
                self.A, self.B = 0, A
            else:
                self.A, self.B = s64(A // B), s64(A - B * (A // B))
        elif tok == "&":
            self.A = s64((A & MASK) & (B & MASK))
        elif tok == "|":
            self.A = s64((A & MASK) | (B & MASK))
        elif tok == "~":
            self.A = s64((A & MASK) ^ (B & MASK))
        elif tok == "{":
            self.A = 0 if not (0 <= B <= 63) else s64(A << B)
        elif tok == "}":
            if B < 0:
                self.A = 0
            elif B > 63:
                self.A = -1 if A < 0 else 0
            else:
                self.A = A >> B
        elif tok in (".", " "):
            pass
        else:
            raise RuntimeError("unknown glyph %r in %s" % (tok, label))
        return None


# ----------------------------------------------------------------------
def run_case(rounds, flow=None, limit=40_000_000):
    """rounds: list of per-round input token lists.  Returns one frame per round."""
    flow = flow or F.build_flow()
    vals = [int(v) for r in rounds for v in r]
    sim = Sim(flow, vals)
    return sim.run(len(rounds), limit=limit), sim


def frame_lines(colours):
    return ["".join("%x" % c for c in colours[y * 16:(y + 1) * 16]) for y in range(16)]


def validate(verbose=True, cases=None):
    spec_path = os.path.join(HERE, "..", "..", "tests",
                             "little-little-little-man.json")
    spec = json.load(open(spec_path))
    flow = F.build_flow()
    ok = bad = 0
    fails = []
    for ci, case in enumerate(spec["publicTestData"]):
        if cases is not None and ci not in cases:
            continue
        rounds = [r["in"] for r in case["rounds"]]
        try:
            frames, sim = run_case(rounds, flow)
        except Exception as exc:  # noqa: BLE001
            fails.append((ci, case.get("name"), "EXC", repr(exc)))
            bad += 1
            if verbose:
                print("case %d %-22r  EXCEPTION %s" % (ci, case.get("name"), exc))
            continue
        exp = [r["frames"][0] for r in case["rounds"]]
        got = [frame_lines(fr) for fr in frames]
        if got == exp:
            ok += 1
            if verbose:
                print("case %d %-22r rounds=%2d  OK   (%d flow-steps)"
                      % (ci, case.get("name"), len(rounds), sim.steps))
        else:
            bad += 1
            first = next(i for i in range(len(exp)) if i >= len(got) or got[i] != exp[i])
            fails.append((ci, case.get("name"), first, (exp[first], got[first])))
            if verbose:
                print("case %d %-22r rounds=%2d  FAIL at round %d"
                      % (ci, case.get("name"), len(rounds), first))
    if verbose:
        print("\n%d/%d public cases reproduce the oracle" % (ok, ok + bad))
        for fl in fails[:1]:
            if fl[2] == "EXC":
                continue
            e, g = fl[3]
            print("-- case %d round %d" % (fl[0], fl[2]))
            for a, b in zip(e, g):
                print("   exp %s   got %s %s" % (a, b, "" if a == b else "<<"))
    return ok, bad, fails


if __name__ == "__main__":
    o, b, _ = validate()
    sys.exit(0 if b == 0 else 1)
