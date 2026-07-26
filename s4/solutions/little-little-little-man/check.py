"""Frame-exact validation of the LLLM op-stream against the 10 public cases (VM only).

Also reports emitted op count and executed VM ops per case -- the two numbers the
score is made of (area ~ emitted ops, ticks ~ executed ops).

  python3 check.py            # validate + report
  python3 check.py --quiet    # totals only
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lllm_build as B
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


def run(ops, tc, cap=200_000_000):
    inputs = []
    for rnd in tc["rounds"]:
        inputs.extend(int(x) for x in rnd["in"])
    vm = VM(inputs)
    vm.run(ops, max_ticks=cap)
    got = [[''.join(HEX[f[y * 16 + x]] for x in range(16)) for y in range(16)]
           for f in vm.frames]
    exp = [r["frames"][0] for r in tc["rounds"]]
    return got, exp, vm.ticks


def main():
    quiet = "--quiet" in sys.argv
    ops = B.build()
    emitted = flat(ops)
    tot = 0
    bad = 0
    rows = []
    for tc in SPEC["publicTestData"]:
        got, exp, n = run(ops, tc)
        ok = got == exp
        if not ok:
            bad += 1
            if not quiet:
                for i, (g, e) in enumerate(zip(got, exp)):
                    if g != e:
                        print(f"  {tc['name']}: first bad frame {i}")
                        for a, b in zip(g, e):
                            print("   got", a, "exp", b, "" if a == b else "<--")
                        break
                if len(got) != len(exp):
                    print(f"  {tc['name']}: frame count {len(got)} vs {len(exp)}")
        tot += n
        rows.append((tc["name"], n, ok))
    if not quiet:
        for name, n, ok in rows:
            print(f"{name:22s} {n:10d} {'ok' if ok else 'FAIL'}")
    avg = tot / len(rows)
    print(f"emitted={emitted}  avg_vmops={avg:.0f}  pass={len(rows)-bad}/{len(rows)}")
    # score model: box side ~ sqrt(area), ticks ~ 1.6 * vmops (measured on reflow3)
    print(f"model: box~{emitted}*1.854 area, ticks~{avg*1.599:.0f}")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
