#!/bin/sh
# Re-run the walkfold row-reclamation loop on a (widened) gradebook grid.
# usage: gb_fold.sh <in.man> <out.man> [iters]
set -e
cd /Users/visenbaev/icfpc26
W="python3 tools/walkfold.py"
IN=$1; OUT=$2; ITERS=${3:-6}
T=$(mktemp -d)
cp "$IN" $T/a.man
i=0
while [ $i -lt $ITERS ]; do
  i=$((i+1))
  $W lift   $T/a.man $T/b.man --rounds 40 --limit 1 --show 0 >/dev/null && mv $T/b.man $T/a.man
  $W norm   $T/a.man $T/b.man >/dev/null && mv $T/b.man $T/a.man
  $W pull   $T/a.man $T/b.man --rounds 40 --limit 1 >/dev/null && mv $T/b.man $T/a.man
  $W fuse   $T/a.man $T/b.man --rounds 40 --limit 1 >/dev/null && mv $T/b.man $T/a.man
  $W squash $T/a.man $T/b.man >/dev/null && mv $T/b.man $T/a.man
  echo "--- iter $i: $(python3 tools/grade_fast.py gradebook $T/a.man | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["passed"],"/",d["total"], d["footprint"], round(d["avgTicks"],1), round(d["score"]))')"
done
cp $T/a.man "$OUT"
rm -rf $T
echo "wrote $OUT"
