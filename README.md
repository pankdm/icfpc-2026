# icfpc-2026
ICFPC 2026

- [Problem description](PROBLEM.md)
- [Littleman interpreter](interpreter/README.md)
- [`Y` split semantics](https://icfpcontest2026.com/split) — supported by both interpreters in this repository

## Best Brackets solution

The strongest Brackets candidate in this repository is
[`solutions/brackets/p5v2.man`](solutions/brackets/p5v2.man).  Its source builder is
[`solutions/brackets/p5_build.py`](solutions/brackets/p5_build.py).  Commit `0189f41`
records the validated result: a 17×17 scored footprint, 263.0 average ticks on the nine
local cases, and 340 fuzz cases passed.  This improves on the prior 18×17 `p5v1` layout;
the older `stack6.man` is not the champion.
