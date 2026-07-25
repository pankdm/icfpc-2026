# Reverse a List — compact Y-delay proof of concept

This prototype uses forked men as list storage.  It has one incoming pipe, one
outgoing pipe, no storage pipes, one shared worker racetrack, and a small
master loop; it is not the previous 16-way unrolled layout.

Files:

- `solutions/reverse-a-list/y_delay_build.py` — coordinate builder
- `solutions/reverse-a-list/y-delay-poc.man` — generated solution
- `scratchpad/reverse_y_delay_poc.py` — original fixed-three mechanism probe
- `scratchpad/reverse_y_delay_trace.js` — tick/event trace for that probe

## Mechanism

The master reads `n` into BP and consumes values one at a time.  After reading
a non-final value, it decrements BP and forks at the same `Y` cell every time.
The clone retains the value in A and inherits the remaining BP, then joins a
single shared racetrack.  The track contains `a` at its entrance and `m` on
its top leg, so a worker with BP=`k` makes exactly `k` laps before it exits.

The master reaches the next fork every 20 ticks.  The shared loop takes 34
ticks.  Consequently each later worker exits 14 ticks earlier than its
predecessor, emitting values in reverse order.  The phase repeats after
17 workers (`34 / gcd(34, 20)`), which is beyond the maximum 15 active clones;
workers therefore never collide on the shared loop.

The final input value is not forked.  After decrementing BP to zero, the master
sends that value directly through the same outgoing pipe, then returns to the
count read.  This keeps the peak population to 15 clones plus the master,
which fits the observed 16-runner limit.

## Validation

Reference WASM oracle:

- Public cases: **8/8 pass**
- Random stress: **300/300 pass**
- Stress covers 1–3 rounds, all `n=1..16`, zero, repeats, arbitrary signed
  values, and ±1,000,000.
- `n=16`: output `16..1`, settling at tick 542 with no collision.

Current measurements:

- footprint: 27×25, box 729
- average public ticks: 455.0
- local score: 331,695

The remaining external risk is grader acceptance of `Y`; local oracle support
is confirmed, but the server's `split_released` gate remains untested.
