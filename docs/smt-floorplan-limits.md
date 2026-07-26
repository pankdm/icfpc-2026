# SMT floorplanning is exhausted on LLM, LLLM and Snake (measured 2026-07-26)

`tools/smtplace.py` was run against the three **live** Semester-4 builds (the ones
recovered by `submissions.py --download` in `bc50cb5`, not the stale in-git variants).
**All three produced no verified improvement.** Do not re-run this sweep.

| target | live box | smtplace result | best M ever proposed |
|---|---|---|---|
| Snake `live-156x191` | 156x191 / 36,481 | **UNSAT** (gap<=2 extra<=8, and again at gap<=1 extra<=24) | 189 |
| LLLM `live-215x221`  | 215x221 / 48,841 | **UNSAT** (gap<=2 extra<=8) | 218 |
| LLM  `live-394x921`  | 394x921 / 848,241 | iteration cap, 20/20 routing_fail | 906 |

Every rejection was the same shape: Z3 finds a tighter envelope, `place.py` cannot route
one specific pipe into it (snake pipe 5, LLLM pipe 4, LLM pipe 12).

## Why — the box lives inside ONE room, not between rooms

`smtplace` moves **rigid** rooms; it cannot shrink one. Each of these programs is a single
monolithic controller room plus a handful of satellites:

| target | room0 | envelope | room0 share | repack ceiling |
|---|---|---|---|---|
| LLM  | **347x876** | 394x921 | 84% of area | 876^2 = 767,376 -> **1.10x** |
| LLLM | **215x163** | 215x221 | 74% | 215^2 = 46,225 -> **1.06x** |
| Snake | 149x140 | 156x191 | 70% | 156^2 = 24,336 -> 1.5x |

`max(w,h) >= 876` for LLM no matter where the other six rooms go, so the *entire* prize
is 1.10x — and that ceiling assumes every satellite tucks into the 47-column margin,
which the routing failures show it cannot. Snake's 1.5x looks better on paper but needs
91.7% envelope fill with corridor clearance; Z3 never got below M=189.

**Rule of thumb: check `room0_area / envelope_area` before reaching for smtplace.** Above
~70% the tool has nothing to work with. It won pathfinder (321x306 -> 276x284) precisely
because pathfinder's area was spread across many mid-sized rooms.

## Where the LLM lever actually is

LLM's 876 rows are boustrophedon **controller op-rows, one block per row**. That is
`tools/smtrows.py`'s problem (Z3-optimal multi-op-per-row packing; it won snake
313x205 -> 302x205). The blocker is that `smtrows` is written against `stateflow`, while
LLM's controller is `tools/boustro.py` — a different placement model, so this is a port,
not an invocation.

Bound the prize before starting: per `CLAUDE.md`, overriding every port band to the full
op range (infinite replicas, zero routing cost) takes the LLM controller only 994 -> 588
rows. So a realistic packing win is ~2x box, not the 5.5x the 394-vs-921 aspect ratio
suggests.

## Also corrected here

`CLAUDE.md` claims the submitted program text "is not retrievable from anywhere". That is
**false**: `python3 tools/submissions.py --download <dir>` recovers the exact submitted
bytes for every problem through the dashboard cookie. Six live champions existed nowhere
in git until `bc50cb5`.
