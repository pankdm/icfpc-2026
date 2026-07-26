"""Measure the LLLM op-stream: emitted ops and executed ops per phase, per public case."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lllm_build as B
import vm as VMM

REPO = "/Users/visenbaev/icfpc26"
SPEC = json.load(open(os.path.join(REPO, "tests", "little-little-little-man.json")))


def flat(o):
    n = 0
    for x in o:
        if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
            n += flat(x[1])
        else:
            n += 1
    return n


def phase_sizes():
    out = {}
    for name, fn in [("fill", B.emit_fill), ("render", B.emit_render),
                     ("fetch", B.emit_fetch), ("tick", B.emit_tick)]:
        a = B.Asm()
        fn(a)
        out[name] = flat(a.ops)
    return out


def case_inputs(tc):
    vals = []
    for rnd in tc["rounds"]:
        vals.extend(int(x) for x in rnd["in"])
    return vals


class Counting(VMM.VM):
    """count executed primitives, split by belt/other"""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.n = 0
        self.nstate = 0
        self.ncells = 0
        self.ncmd = 0

    def _exec(self, ops, max_ticks):
        return super()._exec(ops, max_ticks)


def run_case(ops, tc):
    inp = case_inputs(tc)
    v = Counting(inp)
    # patch counters via monkey-patching of _exec is messy; count by wrapping char dispatch
    orig = VMM.VM._exec

    def counted(self, oplist, max_ticks):
        for op in oplist:
            self.ticks += 1
            if self.ticks > max_ticks:
                raise RuntimeError("tick cap")
            if isinstance(op, tuple):
                tag = op[0]
                if tag == '#':
                    self.A = VMM.s64(op[1])
                elif tag == 'BPLOOP':
                    self.BP = self.A
                    while True:
                        counted(self, op[1], max_ticks)
                        self.BP = VMM.s64(self.BP - 1)
                        if not (self.BP > 0):
                            break
                elif tag == 'FOREVER':
                    while True:
                        if counted(self, op[1], max_ticks) == 'STOP':
                            return
                elif tag == 'LOOPX':
                    while True:
                        r = counted(self, op[1], max_ticks)
                        if r == 'STOP':
                            return 'STOP'
                        if not (self.A > 0):
                            break
                continue
            self.n += 1
            if op in ('r', 's'):
                self.nstate += 1
            elif op in ('rc', 'sc'):
                self.ncells += 1
            elif op == 'cmd':
                self.ncmd += 1
            r = orig(self, [op], max_ticks)
            if r == 'STOP':
                return 'STOP'
        return None

    counted(v, ops, 100_000_000)
    return v


if __name__ == '__main__':
    ps = phase_sizes()
    ops = B.build()
    print("ring slots:", len(B.STATE))
    print("emitted (flat) ops:", flat(ops))
    print("phase sizes (flat ops):", ps)
    print()
    tot = 0
    rows = []
    for tc in SPEC["publicTestData"]:
        v = run_case(ops, tc)
        rows.append((tc["name"], v.n, v.nstate, v.ncells, v.ncmd, len(tc["rounds"])))
        tot += v.n
    print(f"{'case':22s} {'vmops':>10s} {'state':>10s} {'cells':>10s} {'cmd':>7s} {'rnds':>5s}")
    for r in rows:
        print(f"{r[0]:22s} {r[1]:10d} {r[2]:10d} {r[3]:10d} {r[4]:7d} {r[5]:5d}")
    print(f"{'TOTAL':22s} {tot:10d}")
    print("avg vmops/case", tot / len(rows))
