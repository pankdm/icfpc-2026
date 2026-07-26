#!/bin/sh
# Rebuild solutions/gradebook/gradebook-walkfold.man from gradebook-placed.man.
#
# Two kinds of step, both driven by tools/walkfold.py:
#   patch  — a hand-designed CYCLE re-layout. The automatic lifter refuses these on
#            purpose: their turn glyphs are MERGE points (a loop's back edge lands on
#            them), and sliding a merge silently detaches the flow that joins there.
#            Each patch keeps the executed instruction sequence identical and only moves
#            where the cells sit; every `r`/`s` stays inside its pipe band.
#   lift/norm/squash — the mechanical passes. `lift` runs to fixpoint after each patch
#            because a patch frees cells the next round of lifting can use.
#
# ORDER MATTERS: patch coordinates are absolute, and `squash` DELETES rows, so it runs
# only once every patch has been applied.
#
# Gates after every step: tools/pipecheck.py, tools/emit.py --roundtrip,
# tools/grade.js (7/7 public), tools/grade_json.js --cases tests/stress/gradebook.json.
set -e
cd "$(dirname "$0")/../../.."
W="python3 tools/walkfold.py"
D=solutions/gradebook
P=$D/walkfold
T=$(mktemp -d)

lift_fix() {                       # $1 = file, lifted in place
  $W lift "$1" "$T/l.man" --rounds 40 --limit 1 --show 0 >/dev/null
  mv "$T/l.man" "$1"
}

cp $D/gradebook-placed.man $T/a.man
$W patch $T/a.man $P/p1.json $T/b.man >/dev/null && mv $T/b.man $T/a.man   # belt-align loop
lift_fix $T/a.man
$W patch $T/a.man $P/p2.json $T/b.man >/dev/null && mv $T/b.man $T/a.man   # two scan loops
lift_fix $T/a.man
$W patch $T/a.man $P/p3.json $T/b.man >/dev/null && mv $T/b.man $T/a.man   # roster loop A
$W patch $T/a.man $P/p4.json $T/b.man >/dev/null && mv $T/b.man $T/a.man   # roster loop B
lift_fix $T/a.man

for i in 1 2 3; do                 # only now may rows disappear
  $W norm   $T/a.man $T/b.man >/dev/null
  $W squash $T/b.man $T/a.man >/dev/null
  lift_fix $T/a.man
done

cp $T/a.man $D/gradebook-walkfold.man
rm -rf $T
echo "wrote $D/gradebook-walkfold.man"
node tools/grade.js gradebook $D/gradebook-walkfold.man | tail -3
