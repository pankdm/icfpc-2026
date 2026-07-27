# Packed six-tick memory proof of concept

`packed-memory-6.man` demonstrates a complete memory implementation with one command
accepted every six ticks. It is intentionally large (`325x122`) and is meant as a
correctness and timing prototype rather than a submission candidate.

## Encoding

Let `M = 9 << 18`.

```text
payload = -1          for READ
payload = value + M   for WRITE
packed  = payload * 100 + addr
```

Addresses are striped across four megablocks:

```text
block = addr % 4
local = addr / 4
```

The first megablock division is by four:

```text
packed / 4 -> main = payload * 25 + local, offhand = block
```

After filtering, the second division is by 25:

```text
main / 25 -> main = payload, offhand = local
```

The parser's deliberately wasteful packing path swaps `addr` and `payload`, then
executes 100 additions. This avoids needing a third arithmetic register and is an
obvious target for replacement.

## Six-tick stages

- The parser reads an operation, splits immediately, and consumes the remaining raw
  tokens before the continuation reads the next operation six ticks later.
- The fanout receiver splits a broadcast job every six ticks.
- Every megablock receiver preserves constant four, splits a job, filters by block,
  divides by 25, and routes through a five-bit tree.
- The tree has 32 leaves. Only local IDs 0 through 24 are reachable from valid input;
  seven memory workers are intentionally unused.
- Every memory worker uses:

```text
>rvrYWsH
^WX ^
```

  Writes update offhand and return to `r` in six ticks. Reads split: the continuation
  returns to `r` in six ticks while the output copy sends the saved value.
- The collector similarly splits result handling from its six-tick receive loop and
  subtracts `M` in the output copy.

All accepted block-filter routes and all routing-tree leaves have equal latency, so
read results preserve request order without carrying an explicit sequence number.

## Zero-initialized right-side variant

Generate `packed-memory-6-right-zero.man` with:

```text
python3 packed_memory_6.py --compact-right
```

This variant leaves each memory worker's offhand at its natural zero value. The collector
uses `X` to send an untouched zero or subtract `M` from a written value; both branches send
with equal latency. Its worker rooms have `10x65` interiors and its collector has a two-row
interior. The original proof of concept remains the default generator output.

Add `--direct-fanout` to generate the stable working file `memory-6tick-sync.man`. Both parser paths
then use `S` to broadcast directly to the four megablocks. This removes the separate fanout
room and eight layout rows while retaining the six-tick command cadence.

The broadcast is a synchronization requirement, not just routing overhead. Every left-side
receiver must consume one job every six ticks, including jobs intended for other blocks. If the
parser divides by four and sends only to the selected block, the other receivers stop doing work
and their synchronized split/request schedule no longer matches the global stream. Keep the
broadcast-and-reject stage unless those receivers are redesigned to tolerate sparse traffic.
