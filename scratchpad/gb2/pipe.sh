#!/bin/sh
# loop.sh + evict.py alternated to fixpoint.
set -e
cd /Users/visenbaev/icfpc26
IN=$1; OUT=$2; ITERS=${3:-3}
T=$(mktemp -d)
cp "$IN" $T/a.man
i=0
while [ $i -lt $ITERS ]; do
  i=$((i+1))
  sh scratchpad/gb2/loop.sh $T/a.man $T/b.man 2 >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  python3 scratchpad/gb2/evict.py $T/a.man $T/b.man && mv $T/b.man $T/a.man || true
  python3 tools/walkfold.py squash $T/a.man $T/b.man >/dev/null 2>&1 && mv $T/b.man $T/a.man || true
  echo "=== iter $i: $(python3 tools/grade_fast.py gradebook $T/a.man | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["passed"],"/",d["total"], d["footprint"], round(d["avgTicks"],1), round(d["score"]))')"
done
cp $T/a.man "$OUT"
rm -rf $T
echo "wrote $OUT"
