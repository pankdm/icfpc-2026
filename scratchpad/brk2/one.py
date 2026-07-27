import json, subprocess, sys
sys.path.insert(0, '/Users/visenbaev/icfpc26/scratchpad/brk2')
from stress import enc, expect, bal, LM
prog = sys.argv[1]
rounds = eval(sys.argv[2])
inp, exp = [], []
for s in rounds:
    inp += enc(s)
    exp.append(expect(s))
r = subprocess.run([LM, '--grade', prog, '--input=' + ' '.join(map(str, inp)),
                    '--expected=' + ' '.join(map(str, exp)), '--cap=100000'],
                   capture_output=True, text=True)
print('expected', exp)
print(r.stdout.strip()[:600])
