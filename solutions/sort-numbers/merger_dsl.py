"""Reusable STREAM-MERGER cell for the sort-numbers merge-sort architecture.

PHASE-1 SPIKE RESULT (oracle-validated):
  * merger cell footprint : 26 x 24  (max dim 26 -> footprint score 676)
  * throughput            : 46 ticks / merged element (exact linear fit;
                            fixed overhead ~78 ticks), dominated by the return-bus
                            travel per element (a compact re-layout would roughly
                            halve both width and ticks/elem).
  * registers             : uses A and B only -> the BACKPACK (BP) is entirely FREE.
                            (So an in-merger merge-countdown is possible; but per the
                            chosen architecture the controller counts merges and the
                            merger stays pure.)

=================================================================================
REGISTER PRESSURE — how the merger merges two heads with only A and B (no park pipe)
=================================================================================
Registers: A, B, BP. Key facts pinned from interp/src/lib.rs:
  - `s` sends A WITHOUT clobbering A ; `r`/`R`/`U` receive INTO A ; `M`:B=A ; `W`:swap.
  - literals load into A only ; there is NO BP->A read (BP is a write-only counter).
So during a compare you seem to need 3 live values (head_a, head_b, and the diff that
`-` writes into A). The trick: `-` computes A=a-b but LEAVES B=b, and a = diff + b is
RECOVERABLE by `+`. So we never have to stash a head anywhere — arithmetic rebuilds it.

Loop invariant at the top:  A = head_a , B = head_b.
  '-'                 -> A = a-b , B = b (kept)
  'X' (enter East)    -> three-way by sign of the difference:
    A<0  CCW=North  LT (a<b): emit a, refill A-side
                    '+ s r(A)'            [ +: A = diff+b = a ; s: emit ; r: new head_a ]
    A>0  CW=South   GT (a>b): emit b, refill B-side
                    'W s + M r(B) W'      [ W:A=b,B=diff ; s:emit b ; +:A=b+diff=a ;
                                            M:B=a ; r:A=new b ; W:A=a,B=new b ]
    A==0 East       EQ (a==b): sentinel test, then emit one copy + refill B-side
                    'W M `30000` W - X'   [ brings common to A&B, loads +INF, compares ]
       REAL (A<0)   '+ M s r(B) W'        emit common, keep A=common(=head_a), new head_b
       DONE (A==0)  both heads are the +INF sentinel -> merge of this pair is complete

STRICT branches never emit the sentinel (in LT, a<b<=+INF so a is real; symmetric in GT);
only the EQ branch can hit both-sentinel, so the +INF test lives only there (rare = cheap).

SENTINEL / DELIMITER = 30000 (> max biased value 20001) so it sorts as +INF and is never
emitted until both runs are exhausted. Bias real values by +10001 (range 1..20001) so all
data is positive and distinguishable from the sentinel.

DONE behaviour is a build-time choice:
  * standalone spike  : crash into a wall (merge output already settled) — see merger.py.
  * REUSABLE (this)   : emit ONE delimiter (30000) to OUTPUT, then RE-PRIME (read the next
                        run pair). One cell then merges an endless stream of run-pairs,
                        each merged run terminated by a 30000 delimiter. VALIDATED with
                        feeders emitting several sentinel-separated runs:
                        [2,5]|[1,3]->[1,2,3,5], DELIM, [4,6,8]|[7]->[4,6,7,8], DELIM ...

=================================================================================
FULL-SORTER ARCHITECTURE (single delimited ring + this merger) — design
=================================================================================
MAIN RING: one FIFO ring (pipe + relay room) holding all values grouped into sorted
"chunks" separated by a 30000 delimiter. Initially n size-1 chunks. The whole sort =
"merge the front two chunks" done n-1 times; the FIFO run-queue self-schedules into
level-by-level bottom-up merge -> O(n log n), no L, no passes, no odd-run special case.

Two stations sit inline on the ring:  MERGER  and  CONTROLLER.
  MERGER (this cell): reads its two input pipes IN_A, IN_B (fed by the controller from
    the two front chunks) and writes merged run + delimiter back to the ring. Pure.
  CONTROLLER (the remaining build): once per round it (1) reads n from input, reads n
    values, biases +10001, deposits n size-1 chunks into the ring; per merge it (2)
    splits the two front chunks from the ring into IN_A / IN_B (copy values until the
    30000 delimiter, then forward a 30000 terminator to that input); (3) counts n-1
    merges via a BP countdown and on the last one routes the final chunk to OUTPUT
    (unbias -10001) instead of the ring; then loops for the next round. No control
    pipes are needed (round-gating + blocking on empty inputs provides all sync).
  SIZING: IN_A, IN_B pipes each >= n cells (else controller blocks staging one while the
  merger blocks reading the other -> deadlock); main ring ~2n cells.

STATUS: the merger cell + its autonomous looping are VALIDATED on the oracle. The
controller (ring dispatch state-machine + bias/unbias + round loop) is designed but not
yet assembled/routed; that is the remaining work to land the full sorter.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'tools'))
import layout as L

SENT = 30000   # delimiter / +INF sentinel


def place_merger(P):
    """Place the REUSABLE looping merger man+ops into layout ``P`` (room (12,0,26,24)).
    IN_A attaches on the west wall (dst (11,9)), IN_B on the east wall (dst (38,9)),
    OUTPUT on the south wall (single outgoing). r-selection is by column (center 24.5):
    A-refills sit left of center, B-refills right. Caller draws the three pipes."""
    P.room(12, 0, 26, 24)
    # PRIME / re-prime injected via col15 (climbed from below):
    P.put(14, 21, '@'); P.put(15, 21, '^')
    P.put(15, 3, '>'); P.put(16, 3, 'r'); P.put(18, 3, 'M'); P.put(31, 3, 'r'); P.put(32, 3, 'W')
    P.put(33, 3, '^'); P.put(33, 1, '<')
    P.put(13, 1, 'v'); P.put(13, 9, '>')
    P.put(16, 9, '-'); P.put(17, 9, 'X')                 # HUB
    # LT (A<0 CCW=N)
    P.put(17, 8, '+'); P.put(17, 7, 's'); P.put(17, 6, 'r'); P.put(17, 1, '<')
    # GT (A>0 CW=S)
    P.put(17, 10, 'W'); P.put(17, 11, 's'); P.put(17, 12, '+'); P.put(17, 13, 'M')
    P.put(17, 20, '>'); P.put(26, 20, 'r'); P.put(27, 20, 'W'); P.put(28, 20, '^'); P.put(28, 1, '<')
    # EQ (A==0 straight E) — sentinel test with vertical +INF literal on col30
    P.put(18, 9, 'W'); P.put(19, 9, 'M'); P.put(30, 9, 'v')
    lit = '`%d`' % SENT
    for i, ch in enumerate(lit):
        P.put(30, 10 + i, ch)
    P.put(30, 17, 'W'); P.put(30, 18, '-'); P.put(30, 19, 'X')
    # REAL (A<0 CCW=E)
    P.put(31, 19, '+'); P.put(32, 19, 'M'); P.put(33, 19, 's'); P.put(34, 19, 'r'); P.put(35, 19, 'W')
    P.put(36, 19, '^'); P.put(36, 1, '<')
    # DONE (A==0 straight S): emit delimiter, re-prime via col15
    P.put(30, 20, 'W'); P.put(30, 21, 's'); P.put(30, 22, '<'); P.put(15, 22, '^')
    return P


def feeder(P, x0, y0, runs, side):
    """Test feeder: emits each run in ``runs`` followed by a SENT delimiter, then
    infinite SENT. Emit column = x0+2. (For validating the merger in isolation.)"""
    col = x0 + 2
    P.put(x0 + 1, y0 + 1, '@'); P.put(col, y0 + 1, 'v')
    r = y0 + 2
    seq = []
    for run in runs:
        seq += list(run) + [SENT]
    for v in seq:
        s = str(v)
        P.put(col, r, '`')
        for i, ch in enumerate(s):
            P.put(col, r + 1 + i, ch)
        P.put(col, r + 1 + len(s), '`'); P.put(col, r + 2 + len(s), 's')
        r = r + 3 + len(s)
    sr = r + 1
    P.put(col, sr - 1, 'v')
    ls = str(SENT); P.put(col, sr, '`')
    for i, ch in enumerate(ls):
        P.put(col, sr + 1 + i, ch)
    end = sr + 1 + len(ls)
    P.put(col, end, '`'); P.put(col, end + 1, 's')
    P.put(col, end + 2, '<'); P.put(col - 1, end + 2, '^'); P.put(col - 1, sr - 1, '>')
    P.room(x0, y0, 6, (end + 2) - y0 + 2)


def build_merger_rig(runsA, runsB):
    """Merger cell wired to two literal feeders + an O room, for oracle validation."""
    P = L.Layout()
    place_merger(P)
    feeder(P, 0, 7, runsA, 'A'); feeder(P, 45, 7, runsB, 'B')
    P.output_room(21, 26)
    for x in range(6, 12):
        P.put(x, 9, '>')                 # IN_A pipe
    for x in range(38, 45):
        P.put(x, 9, '<')                 # IN_B pipe
    P.put(22, 24, 'v'); P.put(22, 25, 'v')   # OUT pipe
    return P


if __name__ == '__main__':
    P = build_merger_rig([[2, 5], [4, 6, 8]], [[1, 3], [7]])
    print(P.render())
    print('rig footprint', P.footprint())
    only = L.Layout(); place_merger(only)
    print('MERGER CELL footprint (w,h,score):', only.footprint())
