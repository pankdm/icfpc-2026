"""Compare p5v2 vs p6v1 tick counts across shapes; print rows where p6 is worse."""
import json, subprocess, random
REPO = '/Users/visenbaev/icfpc26'
LM = REPO + '/interp/target/release/lm'
A, B = REPO + '/solutions/brackets/p5v2.man', REPO + '/solutions/brackets/p6v1.man'
O = {'(': 40, '[': 91, '{': 123}
Cl = {')': 41, ']': 93, '}': 125}
PAIR = {'(': ')', '[': ']', '{': '}'}


def expect(s):
    st = []
    for i, ch in enumerate(s):
        if ch in O:
            st.append(ch)
        else:
            if not st or PAIR[st[-1]] != ch:
                return i + 1
            st.pop()
    return len(s) + 1 if st else 0


def enc(s):
    return [len(s)] + [O.get(c, Cl.get(c)) for c in s]


def run(prog, rounds):
    inp, exp = [], []
    for s in rounds:
        inp += enc(s)
        exp.append(expect(s))
    r = subprocess.run([LM, '--grade', prog, '--input=' + ' '.join(map(str, inp)),
                        '--expected=' + ' '.join(map(str, exp)), '--cap=200000'],
                       capture_output=True, text=True)
    d = json.loads(r.stdout.strip().split('\n')[-1])
    return d['status'], d['settleTick']


def bal(n, chars='([{'):
    random.seed(n * 7 + len(chars))
    st, out = [], []
    while len(out) < n:
        if st and (len(out) + len(st) >= n or random.random() < 0.5):
            out.append(PAIR[st.pop()])
        else:
            c = random.choice(chars)
            st.append(c)
            out.append(c)
    return ''.join(out)


TESTS = [
    ('empty', ['']),
    ('one open', ['(']),
    ('one close', [')']),
    ('nest32', ['(' * 32 + ')' * 32]),
    ('flat32', ['()' * 32]),
    ('allclose64', [')' * 64]),
    ('allopen64', ['(' * 64]),
    ('bal64 paren', [bal(64, '(')]),
    ('bal64 mixed', [bal(64)]),
    ('bal64 braces', [bal(64, '{')]),
    ('bal64 sq', [bal(64, '[')]),
    ('offense@2 n64', ['()' + '(' * 62]),
    ('offense@1 n64', [')' + '(' * 63]),
    ('mid offense', ['(' * 30 + '}' + '(' * 33]),
    ('10 rounds n6', [bal(6)] * 10),
    ('10 rounds empty', [''] * 10),
    ('10 rounds n1', ['('] * 10),
    ('5 rounds n64', [bal(64)] * 5),
    ('mixed rounds', ['', '(', ')', bal(20), '(((', bal(64), '[]', '']),
    ('20 rounds n2', ['()'] * 20),
]
print('%-18s %8s %8s %7s' % ('case', 'p5v2', 'p6v1', 'ratio'))
for name, rounds in TESTS:
    sa, ta = run(A, rounds)
    sb, tb = run(B, rounds)
    flag = '' if (sa == 'pass' and sb == 'pass') else '  <<%s/%s' % (sa, sb)
    print('%-18s %8d %8d %7.2f%s' % (name, ta, tb, tb / max(ta, 1), flag))
