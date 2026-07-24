# ICFP Contest 2026 — littleman

Tooling and a fast local interpreter for the 2026 contest's **littleman** (`.man`) language —
a 2D ASCII grid esolang (little men `@` walking rooms, hands/backpack, pipes, LM-75 display).

## Layout

- **`interp/`** — a fast reimplementation of the reference interpreter in Rust (crate `littleman`,
  binary `lm`). Semantics are pinned to the reference by differential testing.
  - Build: `cd interp && cargo build --release`
  - Test: `cargo test`
- **`sim/`** — the reference interpreter used as an **oracle**: the organizers' `littleman.wasm`
  (Go→WASM) driven headless in Node. Fetch it first (it is gitignored):
  - `bash sim/fetch-oracle.sh`
  - `harness.js` boots the wasm and exposes `newSession / load / step / stepN / …`.
  - `node sim/difftest.js` runs the Rust engine against the oracle and reports divergences.
  - `trace.js`, `grid.js`, and the `run*.js` / `scan_swap.js` / `swapsearch.js` scripts are the
    experiment harnesses used to reverse-engineer semantics.
- **`docs/`** — reverse-engineered semantics.
  - `multi-man-interactions.md` — how multiple little men interact (fork `Y`, collision, reaping,
    walls, lockstep), all confirmed against the oracle.

## Interpreter status

Milestone 1 (validated byte-for-byte vs. the oracle): rooms, men, movement, all non-pipe
instructions (arithmetic with floored div/mod + i64 wrapping, hands, backpack, `X`, directions,
`H`, digits), `Y` fork, man↔man collision, wall faults (both timings), reaping.

TODO: pipes (`s S r R U q` + capacity/timing), IO rooms, LM-75 display, numeric literals,
round gating; then a fuzzer to pin remaining edge cases; then a pyo3 binding for a Python
search loop.
