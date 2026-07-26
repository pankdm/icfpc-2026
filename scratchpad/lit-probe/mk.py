#!/usr/bin/env python3
"""Regenerate the literal-semantics probes. `python3 run.py <probe>.man` grades one against
the oracle AND the Rust engine and prints MATCH/DIVERGE; all 19 match as of 2026-07-26."""
import os
from gen import build, col

HERE = os.path.dirname(os.path.abspath(__file__))


def raw(name, lines):
    with open(os.path.join(HERE, name + '.man'), 'w') as f:
        f.write('\n'.join(lines) + '\n')

# p2: horizontal literal `12`, man crosses its CLOSING backtick going south.
#     cx=3 must be the closing tick: row = "  `12`"? -> place literal so col3='`'
build('p2_cross_close_h', ['`12`'.rjust(4)])       # cols 0..3 => '`','1','2','`', col3 = closing

# p2b: man crosses the OPENING backtick of a horizontal literal going south
build('p2b_cross_open_h', ['   `12`'])              # col3 = opening tick

# p3: plain vertical literal, expect 12
build('p3_vert_ok', col('`12`'))

# p4: column: invalid span (.), then a valid literal below
build('p4_vert_after_bad', col('`.`') + col('`12`'))

# p5: same but only 3 ticks: bad span then a dangling tick pair
build('p5_vert_bad_then_pair', col('`.`12`'))

# p6: empty vertical literal after setting A=7
build('p6_vert_empty', col('7` `'))

# p7: single unpaired backtick
build('p7_lone_tick', col('7`'))

# p8: vertical literal whose span holds spaces between digits
build('p8_vert_spaces', col('`1 2`'))

# p9: two independent horizontal literals sharing a column (classic false pair):
#     the man crosses the second row's tick going south.
build('p9_h_pair_sharecol', ['   `1`', '   `2`'])

# p10: three vertical ticks: '`','1','`','2','`'  (consecutive pairing => (0,2) lit "1",
#      leftover tick at 4 -> paired horizontally? no -> ?)
build('p10_vert_three', col('`1`2`'))

# p14: two vertical literals sharing a row, junk between them horizontally
build('p14_v_share_junk', ['   ` M `', '   1   2', '   `   `'])

# p15: row where the first tick is a vertical-literal opener and cannot pair horizontally
build('p15_h_skip', ['   ` M `2`', '   1', '   `'])

# p16: same, but the "skipped" tick has no vertical partner either
build('p16_h_skip_nopartner', ['   ` M `2`'])

# p17: one literal per ROOM on the same row -- must NOT pair across the wall between them
raw('p17_two_rooms', ['+----+ +----+',
                      '|@`  | |`   |',
                      '| 1  | |2   |',
                      '| `  | |`   |',
                      '+----+ +----+'])

# p19: man walking EAST across the digit of a VERTICAL literal -> executes it (A = 5)
raw('p19_cross_v_digit', ['+-+', '|O|', '+-+', '  ^', '  ^',
                          '+-------+',
                          '|  `    |',
                          '|@ 5  sH|',
                          '|  `    |',
                          '+-------+'])
