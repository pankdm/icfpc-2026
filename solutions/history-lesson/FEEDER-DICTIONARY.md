# History Lesson feeder/dictionary trade-offs

This note treats dictionary design as an **encoding-only** problem.  Its
objective is to reduce the number of packed literals sent by the feeder.
Dictionary-room geometry, ring capacity, preload size, and tick cost are
deliberately out of scope; packing a proposed encoding into a smaller program
is a separate step.

The figures below are exploratory results from the checked-in text and
`build_ring.py`, not claims that the current 82x82 layout can accommodate the
corresponding dictionary.

## Baseline and terminology

The current encoder produces:

- 2,042 physical base-92 symbols;
- 35 ring positions, numbered 1 through 35;
- 304 feeder literals in the current width-82 paired-row plan;
- a minimum of 228 literals if the same symbol stream is partitioned only by
  the literal validity rules, without row-width or paired-column constraints.

The last figure is the useful baseline for dictionary-only work.  A signed
64-bit base-92 literal holds at most nine symbols, so the unattainable
counting lower bound is `ceil(2042 / 9) = 227`.  The exact minimum is one
higher because:

- a chunk may not end in symbol zero (the repeated `/92` decoder would lose
  that most-significant zero);
- the decimal spelling of every literal must fit signed i64 both forward and
  backward.

The physical 304-literal count is intentionally not used to judge dictionary
choices here.  The paired-row feeder optimizer is allowed to choose more,
shorter chunks to fit a band.  Packing will be reconsidered after choosing a
better encoding.

## Can we add more dictionary words?

Yes.  The current selector stops because it charges every phrase for its P1
preload literal and send cell.  That is the wrong stopping rule when the only
objective under consideration is feeder chunk count.

The current reference forms are:

- positions 1 through 16: one-symbol direct references;
- positions 17 through 91: two-symbol `[ESC, position]` references, where
  `ESC = 29`.

All nine direct positions that are free for phrases are already assigned.
The escape dictionary currently ends at position 35, leaving **56 additional
positions (36 through 91)** under the existing base-92 protocol.

For an escape reference, replacing a phrase of `m` stream tokens occurring
`t` non-overlapping times saves `(m - 2) * t` symbols.  Once dictionary storage
is excluded from this stage of the optimization, every recurring phrase of
at least three tokens has positive encoding value.  Two-token phrases do not
reduce the stream when referenced through an escape pair.

Two greedy measurements establish the size of the opportunity:

| Encoding experiment | Symbols | Minimum valid i64 chunks |
| --- | ---: | ---: |
| Current checked-in encoding | 2,042 | 228 |
| Keep current assignments; fill all 56 unused escape positions | 1,814 | 202 |
| Reassign all direct and escape phrases for symbol reduction | 1,775 | 198 |

The append-only experiment first selected phrases such as `iotis, `,
`Baltim`, `, Italy`, `ystem`, `s Vyt`, and `modul`.  These are examples, not a
stable proposed dictionary: phrase overlap makes the result dependent on
selection order.

The 198-chunk result is a greedy estimate, not a proven optimum.  It does show
that “add more words” is worth pursuing before changing the runtime protocol:
under the current one-word entry format, the estimated opportunity is about
30 feeder literals.

### Implemented width-81 step

`candidates/81x82.man` implements the first three extra escape entries:
`Baltim`, `, Italy`, and `iotis, `.  They are the unique tied leaders under
the immediate symbol-saving objective, at eight symbols saved apiece.

This changes the measured encoding as follows:

| Encoding | Symbols | Standalone minimum chunks | Paired feeder |
| --- | ---: | ---: | ---: |
| Original 82-column build | 2,042 | 228 | 304 literals / 62 rows |
| Three added entries | 2,018 | 225 | 294 literals / 62 rows at width 81 |

Only one of the three phrases was necessary for the width-81 DP to find a
62-row plan.  All three fit in the relocated constant/pump rows and provide
additional boundary slack without changing the room height.

## Can dictionary words be bigger?

### Within the current runtime: only up to one packed i64

Each ring entry currently expands to one positive integer containing raw ASCII
in little-endian base 128.  This imposes an absolute limit of nine ASCII bytes,
and the forward/reversed decimal-literal checks can reject some values below
that limit.  `choose_phrases()` already searches phrases up to nine bytes.
The longest phrases selected by the checked-in cost model are eight bytes, so
the existing result is not capped merely because the search forgot longer
one-word candidates.

Thus:

- selecting different phrases up to nine bytes requires no decoder change;
- expanding a reference to more than nine bytes requires a protocol change.

### Multiword entries are feasible

A larger logical dictionary word can be represented by two or more packed
base-128 payload integers while keeping its feeder reference at one direct
symbol or one two-symbol escape reference.  The dictionary lookup must then
know how many payload words belong to the entry.  Plausible representations
include:

- a continuation tag on each non-final payload;
- a length word followed by that many payloads;
- a separate metadata table giving the payload count for each dictionary
  position.

Whichever representation is chosen, it must preserve payload order and leave
the ring in its canonical order after lookup.  The present DISP path sends one
selected ring value directly toward UNPACK, so it cannot emit a multiword
entry without such a change.

An encoding-only greedy experiment allowed one reference to expand to as many
as two valid packed i64 payloads.  With a full dictionary reassignment it
estimated:

| Entry model | Symbols | Minimum valid i64 chunks |
| --- | ---: | ---: |
| One payload i64 per reference | 1,775 | 198 |
| Up to two payload i64s per reference | 1,751 | 195 |

This is only a three-chunk improvement over filling and reassigning the
ordinary dictionary.  Interestingly, the benefit did not require selected
phrases longer than nine bytes: splitting also admits short phrases whose
single packed decimal literal fails the reverse-i64 check.  Longer phrases
were considered by the greedy search but lost to combinations of shorter,
more reusable phrases.

The estimate assumes that a multiword entry still costs exactly one dictionary
reference in the feeder.  It intentionally does not charge for metadata,
additional ring words, dispatcher instructions, space, or ticks.

### Recursive dictionary entries are a different protocol

The current ring contains packed raw ASCII, not sequences of dictionary
symbols.  Its output goes to UNPACK rather than back through DISP, so entries
cannot be composed from other entries.  A hierarchical dictionary could
represent much larger logical phrases, but it would need another expansion
stage or a feedback path into the dispatcher.  Treat that as a separate
architecture, not as a larger value in the current table.

## Encoding trade-offs that remain

### Direct references versus escape references

A direct reference costs one symbol and an escape reference costs two.
The nine phrase-capable direct symbols should go to phrases with the largest
marginal reduction after overlap is resolved.  The checked-in assignment was
chosen using preload-cell cost, so it is not necessarily the best assignment
for feeder chunks.

### Symbol count versus exact chunk count

Fewer symbols usually means fewer chunks, but the relationship is discrete.
Roughly nine saved symbols buy one chunk; a smaller saving can still buy a
chunk when it repairs an unfortunate zero or reverse-decimal boundary, and a
larger saving can fail to buy one.  Candidate dictionaries should therefore
be ranked by the exact minimum-chunk dynamic program, with symbol count only
as a tie-breaker.

### Phrase overlap

Long phrases can displace shorter phrases, while shorter phrases can be reused
across more contexts.  Greedy replacement is evidence of headroom, not an
optimal selection algorithm.  A serious search should include remove/swap
moves over the whole dictionary and recompute exact chunk count after each
move.

### Fixed alphabet assumptions

The measurements above preserve all of the current dispatch conventions:

- base 92;
- `0` is the stateful year marker;
- `29` is ESC;
- positions 1 through 16 are direct lookups;
- bare `17` is not allowed and its raw spelling is handled through the ring;
- escape targets are positions 17 through 91.

Changing the alphabet or classifier may expose more direct codes or pack more
symbols per i64, but it invalidates these measurements and should be evaluated
as a separate encoding architecture.

## Assumptions to preserve in the next experiment

1. Optimize exact standalone feeder-literal count first.
2. Ignore ticks and all dictionary/layout geometry during this phase.
3. Preserve the current base-92 reference protocol for the first experiment.
4. Fill and globally reassign the existing one-word dictionary before adding
   multiword expansion machinery.
5. Treat phrase references as atomic and non-recursive.
6. Verify every candidate by decoding it back to `icfp-history.txt`.
7. Use the exact i64, reverse-decimal, and terminal-zero rules when counting
   chunks; `ceil(symbols / 9)` is only a lower bound.

The recommended sequence is therefore:

1. build an exact chunk-count dictionary optimizer using all positions through
   91;
2. search swaps/reassignments around the 198-chunk greedy result;
3. only then prototype two-payload entries, whose measured incremental target
   is about three more chunks;
4. hand the chosen encoding to the separate feeder-packing/layout pass.
