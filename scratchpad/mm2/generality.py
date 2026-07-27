#!/usr/bin/env python3
"""matmul mm2 generality sweep: the corners of the (N,M,K) box plus extreme values.
16x16x2 is the one that matters most -- N*M = 256 fills the A queue while K = 2 drains
it fastest, so it is where an undersized A serpentine would deadlock."""
import json, os, random, subprocess, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LM = os.path.join(REPO, 'interp', 'target', 'release', 'lm')
MAN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    REPO, 'solutions', 'matmul', 'matmul-mm2b.man')


def mm(N, M, K, A, B):
    return [sum(A[i * M + m] * B[m * K + j] for m in range(M))
            for i in range(N) for j in range(K)]


def run(N, M, K, A, B, cap=2000000):
    inp = ' '.join(map(str, [N, M, K] + A + B))
    exp = ' '.join(map(str, mm(N, M, K, A, B)))
    o = subprocess.run([LM, '--grade', MAN, f'--input={inp}', f'--expected={exp}',
                        f'--cap={cap}'], capture_output=True, text=True)
    return json.loads(o.stdout.strip().splitlines()[-1])


if __name__ == '__main__':
    random.seed(7)
    bad = 0
    for (N, M, K) in [(2, 2, 16), (16, 16, 2), (16, 2, 2), (2, 16, 2), (16, 16, 16),
                      (3, 5, 7), (2, 2, 2), (16, 2, 16), (2, 16, 16)]:
        A = [random.randint(-9, 9) for _ in range(N * M)]
        B = [random.randint(-9, 9) for _ in range(M * K)]
        j = run(N, M, K, A, B)
        print(f"{N}x{M}x{K}: {j['status']} {j.get('settleTick', '')}")
        bad += j['status'] != 'pass'
    j = run(2, 2, 2, [10**9] * 4, [10**9] * 4, cap=200000)
    print('1e9 magnitudes:', j['status'])
    bad += j['status'] != 'pass'
    print('FAILURES:', bad)
