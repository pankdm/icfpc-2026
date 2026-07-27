# icfpc-2026
ICFPC 2026

- [Problem description](PROBLEM.md)
- [Littleman interpreter](interpreter/README.md)
- [`Y` split semantics](https://icfpcontest2026.com/split) — supported by both interpreters in this repository

## Solution recordings

Screen recordings of solutions running, captured on the final day (2026-07-27).

| recording | what it shows |
|---|---|
| [Reverse a List — champion](docs/videos/reverse-a-list-champion.mov) | our top **Reverse a List** solution ([`sweep-live-a0ee52e1.man`](solutions/reverse-a-list/sweep-live-a0ee52e1.man)), server score 13,764 |
| [Memory — champion](docs/videos/memory-champion.mov) | our top **Memory** solution ([`mem-sweep1.man`](solutions/memory/mem-sweep1.man)), server score 5,753,682 |
| [Memory — alternative](docs/videos/memory-alternative.mov) | an alternative **Memory** construction, kept for comparison |

## Best Brackets solution

The strongest Brackets candidate in this repository is
[`solutions/brackets/p5v2.man`](solutions/brackets/p5v2.man).  Its source builder is
[`solutions/brackets/p5_build.py`](solutions/brackets/p5_build.py).  Commit `0189f41`
records the validated result: a 17×17 scored footprint, 263.0 average ticks on the nine
local cases, and 340 fuzz cases passed.  This improves on the prior 18×17 `p5v1` layout;
the older `stack6.man` is not the champion.
