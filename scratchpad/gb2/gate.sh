#!/bin/sh
# Full submission gate for a gradebook candidate.
# usage: gate.sh <file.man>
cd /Users/visenbaev/icfpc26
M=$1
echo "== manlint"
python3 s4/tools/manlint.py "$M" 2>&1 | tail -5
echo "== rust public"
python3 tools/grade_fast.py gradebook "$M" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["passed"],"/",d["total"], d["footprint"], round(d["avgTicks"],1), round(d["score"]))'
echo "== oracle public"
node tools/grade.js gradebook "$M" 2>&1 | tail -12
for S in gradebook gradebook-align; do
  echo "== stress $S"
  node tools/grade_json.js gradebook "$M" --cases tests/stress/$S.json 2>&1 | tail -1 | python3 -c 'import sys,json; d=json.loads(sys.stdin.read().strip()); print(d["passed"],"/",d["total"]); [print("  FAIL",r["name"],r.get("status"),r.get("reason")) for r in d["results"] if r["status"]!="pass"]'
done
