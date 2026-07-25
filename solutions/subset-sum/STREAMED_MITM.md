# Streamed MITM direction

The current machine still reconstructs a subset sum inside every exhaustive
worker loop. Layout work can improve that family by tens of percent, but cannot
close a roughly 200x score gap.

## Proposed architecture

Split the input into at most ten left values and exactly ten right values.

1. Create 1024 fixed right-mask comparator workers.
2. During initialization, each worker consumes the ten right values once and
   stores `target - right_sum` in its off hand.
3. A small left engine emits `(left_mask, left_sum)` pairs in descending mask
   order.
4. Broadcast each pair to every comparator. A comparator only executes a
   constant-size equality loop; it never reconstructs a subset sum.
5. Comparators send only on a match. A balanced, equal-latency priority tree
   forwards the first match. Temporal order chooses the largest left mask;
   reading order chooses the largest right mask among simultaneous matches.
6. Reuse a compact reconstruction tail after obtaining the full mask.

The left engine does not need random-access integer memory. Ten tiny value rooms
hold the left values in backpacks. For each descending mask, the controller
broadcasts the mask; value room `i` returns either its stored value or zero, and
a ten-input addition tree produces `left_sum`. The controller then broadcasts
the mask and sum pair to the comparators.

## Comparator state

- off hand: fixed `target - right_sum`
- backpack: current left mask
- main hand: streamed left sum / comparison result

The hot loop is conceptually `r(mask), b, r(sum), -, X`. The zero branch builds
`(left_mask << 10) | right_mask` and sends it; nonzero branches return directly
to the two reads. No zero result needs to be sent.

## Why this can reach the leading range

For n=20 there are 1024 streamed left masks. At roughly 15-25 ticks per mask,
the search finishes in about 15k-27k ticks instead of millions. With ordinary
rooms, a 200-250 cell side gives a rough 0.6B-1.7B range. Packing comparator
lanes more aggressively—or using `Y` after confirming grader availability—can
plausibly cross below 500M.

The next implementation milestone is one initialized comparator plus a
ten-value contribution tree, followed by a 16-comparator end-to-end prototype.
