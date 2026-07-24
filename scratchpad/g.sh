#!/bin/zsh
f=$1
python3 solutions/sort-numbers/$2 2>&1 | tail -3
node tools/grade.js sort-numbers $f 2>&1 | tail -12
