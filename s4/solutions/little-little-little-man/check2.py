"""Validate an LLLM op-stream module against the 10 public cases (VM only).

  python3 check2.py [module]      default lllm_build2
"""
import importlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vm import VM

SPEC = json.load(open(os.path.join(HERE, "..", "..", "tests",
                                   "little-little-little-man.json")))
HEX = "0123456789abcdef"


def flat(o):
    n = 0
    for x in o:
        if isinstance(x, tuple) and x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
            n += flat(x[1])
        else:
            n += 1
    return n


def check_digits(o):
    bad = set()
    for x in o:
        if isinstance(x, tuple):
            if x[0] in ('BPLOOP', 'LOOPX', 'FOREVER'):
                bad |= check_digits(x[1])
            elif x[0] == '#' and not (0 <= x[1] <= 9):
                bad.add(x[1])
    return bad


def run(ops, tc, cap=100_000_000):
    inputs = []
    for rnd in tc["rounds"]:
        inputs.extend(int(x) for x in rnd["in"])
    vm = VM(inputs, swap_preserve=True)
    vm.run(ops, max_ticks=cap)
    got = [[''.join(HEX[f[y * 16 + x]] for x in range(16)) for y in range(16)]
           for f in vm.frames]
    exp = [r["frames"][0] for r in tc["rounds"]]
    return got, exp, vm.ticks


def main():
    mod = importlib.import_module(sys.argv[1] if len(sys.argv) > 1
                                 else 'lllm_build2')
    ops = mod.build()
    emitted = flat(ops)
    bad = check_digits(ops)
    if bad:
        print("!! multi-digit constants emitted (despine clobbers B):", bad)
    tot = 0
    fails = 0
    for tc in SPEC["publicTestData"]:
        try:
            got, exp, n = run(ops, tc)
        except Exception as exc:
            print(f"{tc['name']:22s} ERROR {type(exc).__name__}: {exc}")
            fails += 1
            continue
        ok = got == exp
        tot += n
        print(f"{tc['name']:22s} {n:10d} {'ok' if ok else 'FAIL'}")
        if not ok:
            fails += 1
            if len(got) != len(exp):
                print(f"   frames {len(got)} vs {len(exp)}")
            for i, (g, e) in enumerate(zip(got, exp)):
                if g != e:
                    print(f"   first bad frame {i}")
                    for a, b in zip(g, e):
                        print("    got", a, "exp", b, "" if a == b else "<--")
                    break
    avg = tot / len(SPEC["publicTestData"])
    print(f"emitted={emitted}  avg_vmops={avg:.0f}  "
          f"pass={len(SPEC['publicTestData'])-fails}/{len(SPEC['publicTestData'])}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
