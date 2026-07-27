#!/usr/bin/env python3
"""Binding risk for the brackets reshape: measured to be ZERO.

The worry was that collapsing C from 4 interior rows to 3 (or M from 11 to 10
wide) would silently re-bind its pipe ops, since r/s/q take the NEAREST
attachment. Enumerating the champion's actual pipes shows there is nothing to
re-bind: every room has exactly ONE incoming and ONE outgoing pipe, so
_nearest_pipe has no choice to make and geometry cannot change the outcome.

    total pipes 4
    room 0 (M): 1 out, 1 in      room 1 (P): 1 out, 1 in
    room 3 (C): 1 out (-> M), 1 in (<- I)
    room 4 (I): 1 out            room 2 (O): 1 in

C's five pipe ops -- s(2,1) q(7,1) s(8,1) q(7,4) s(8,4) -- therefore all bind
to the same two attachments no matter where C's walls move.
"""
import json, subprocess, sys

REPO = '/Users/visenbaev/icfpc26'
man = sys.argv[1] if len(sys.argv) > 1 else REPO + '/solutions/brackets/p6v1.man'
out = subprocess.run([REPO + '/interp/target/release/lm', man, '--inspect=1',
                      '--input=()', '--expected=1'],
                     capture_output=True, text=True).stdout
ps = json.loads(out).get('pipes') or []
from collections import Counter
inc, outg = Counter(), Counter()
for p in ps:
    outg[p.get('srcRoom')] += 1
    inc[p.get('dstRoom')] += 1
bad = [r for r in set(list(inc) + list(outg)) if inc[r] > 1 or outg[r] > 1]
print(f'{len(ps)} pipes; rooms with >1 attachment in either direction: {bad or "NONE"}')
print('=> re-binding under reshape is impossible' if not bad
      else '=> reshape MUST re-verify bindings for those rooms')
