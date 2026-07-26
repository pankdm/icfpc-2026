"""Dynamic VM-op attribution per phase for the v2 op stream.

Wraps each phase emitter with a marker op so the VM can attribute executed ops.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lllm_build2 as B
import vm as VMM

SPEC = json.load(open(os.path.join(HERE, "..", "..", "tests",
                                   "little-little-little-man.json")))
PHASES = ['fill', 'fetch', 'step', 'render', 'other']


def flat(o):
    n = 0
    for x in o:
        if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
            n += flat(x[1])
        else:
            n += 1
    return n


def tag(name):
    """wrap a phase emitter so its ops carry a marker"""
    fn = getattr(B, 'emit_' + name)

    def wrapped(a, *args, **kw):
        a.ops.append(('MARK', name, 1))
        fn(a, *args, **kw)
        a.ops.append(('MARK', name, -1))
    return wrapped


def main():
    for p in ('fill', 'fetch', 'step', 'render'):
        setattr(B, 'emit_' + p, tag(p))
    ops = B.build()
    print("emitted (excl. marks):", flat(ops) - 8)

    counts = {p: 0 for p in PHASES}
    stack = []

    orig = VMM.VM._exec

    def ex(self, oplist, max_ticks):
        for op in oplist:
            if isinstance(op, tuple) and op[0] == 'MARK':
                if op[2] > 0:
                    stack.append(op[1])
                else:
                    stack.pop()
                continue
            self.ticks += 1
            key = stack[-1] if stack else 'other'
            if isinstance(op, tuple):
                t = op[0]
                if t == '#':
                    self.A = VMM.s64(op[1])
                    counts[key] += 1
                elif t == 'BPLOOP':
                    self.BP = self.A
                    while True:
                        ex(self, op[1], max_ticks)
                        self.BP = VMM.s64(self.BP - 1)
                        if not (self.BP > 0):
                            break
                elif t == 'FOREVER':
                    while True:
                        if ex(self, op[1], max_ticks) == 'STOP':
                            return
                elif t == 'LOOPX':
                    while True:
                        if ex(self, op[1], max_ticks) == 'STOP':
                            return 'STOP'
                        if not (self.A > 0):
                            break
                continue
            counts[key] += 1
            if orig(self, [op], max_ticks) == 'STOP':
                return 'STOP'
        return None

    tot = 0
    for tc in SPEC["publicTestData"]:
        inputs = []
        for rnd in tc["rounds"]:
            inputs.extend(int(x) for x in rnd["in"])
        vm = VMM.VM(inputs, swap_preserve=True)
        before = dict(counts)
        ex(vm, ops, 100_000_000)
        n = sum(counts[k] - before[k] for k in counts)
        tot += n
        print(f"  {tc['name']:22s} {n:9d}")
    print(f"avg {tot/10:.0f}")
    for p in PHASES:
        print(f"  {p:8s} {counts[p]/10:10.0f}  {100*counts[p]/tot:5.1f}%")


if __name__ == '__main__':
    main()
