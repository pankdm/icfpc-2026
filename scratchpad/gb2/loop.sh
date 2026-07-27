#!/bin/sh
# Full row-reclamation loop: walkfold passes + reroute, repeated to fixpoint.
# usage: loop.sh <in.man> <out.man> [iters]
set -e
cd /Users/visenbaev/icfpc26
W="python3 tools/walkfold.py"
IN=$1; OUT=$2; ITERS=${3:-4}
T=$(mktemp -d)
cp "$IN" $T/a.man
i=0
while [ $i -lt $ITERS ]; do
  i=$((i+1))
  $W lift   $T/a.man $T/b.man --rounds 40 --limit 1 >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  $W norm   $T/a.man $T/b.man >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  $W pull   $T/a.man $T/b.man --rounds 40 --limit 1 >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  $W fuse   $T/a.man $T/b.man --rounds 40 --limit 1 >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  $W squash $T/a.man $T/b.man >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  python3 tools/reroute.py $T/a.man $T/b.man >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  $W squash $T/a.man $T/b.man >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  echo "--- iter $i: $(python3 tools/grade_fast.py gradebook $T/a.man | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["passed"],"/",d["total"], d["footprint"], round(d["avgTicks"],1), round(d["score"]))')"
done
cp $T/a.man "$OUT"
rm -rf $T
echo "wrote $OUT"
