# Reverse a List — fixed-16 fork-ring proof of concept

This prototype implements the fixed-capacity design directly. It always forks
exactly 16 workers, uses one shared countdown ring, and has only one outgoing
pipe. It deliberately favors a clear timing proof over score optimization.

Files:

- `solutions/reverse-a-list/y_fixed16_ring_build.py` — coordinate builder
- `solutions/reverse-a-list/y-fixed16-ring-poc.man` — generated solution

## Mechanism

The master reads `n`, retains it in B, and puts `16-n` in BP.

First it forks `16-n` padding workers. A padding worker carries A=0 and its
current BP value. The master then restores `n` from B and forks `n` real
workers, one per input value. Real values are biased by `2^21`, so they are
always positive while zero remains an unambiguous padding marker.

All 16 workers enter the same racetrack. A worker born with BP=`k` makes `k`
laps, decrementing BP once per lap. This makes later real inputs exit before
earlier inputs. At the exit:

- A=0 is padding and halts;
- A>0 is real, removes the bias, sends through the sole outgoing pipe, and
  halts.

After its final fork, the master enters a separate tiny 12-tick loop for 100
laps. This compact cooldown replaces an unrolled delay and prevents a new
round from starting while high-count padding workers are still on the shared
ring.

## Validation

The checked-in public fixture was run through the local reference WASM oracle:

- public cases: **8/8 pass**
- deterministic randomized cases: **300/300 pass**
- randomized coverage: 1–3 rounds, `n=1..16`, and values across the full
  allowed signed range
- tick-by-tick peak population: **17** live entities, the master plus all
  **16** forked workers
- boundary cases: `n=1` settles at tick 491; `n=16` settles at tick 1151

Current proof-of-concept measurements:

- footprint: 49×31, box 2401
- average public ticks: 3247.5
- local score: 7,797,247.5

The cooldown is intentionally conservative. Tightening that count and folding
the routing are straightforward later optimization targets.
