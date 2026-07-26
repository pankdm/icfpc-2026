#!/usr/bin/env python3
"""Dynamic-programming optimizer for variable-width History Lesson feeders.

The feeder is walked in two-row boustrophedon bands.  Littleman's literal
parser also pairs backticks vertically, so both rows in a band must put their
backticks in exactly the same columns.  Different bands are independent and
may use different slot widths.

For a band containing chunks C0..C(2*n-1), the eastbound row holds C0..C(n-1)
and the westbound row holds the rest in reverse physical order.  Its digit
cost is therefore

    sum(max(digits(C[j]), digits(C[2*n-1-j]))) for j in range(n))

plus three cells per slot (two backticks and one send) and five fixed feeder
cells.  ``_paired_cost`` is an interval DP which removes those outer paired
chunks and recurses inward.  A second shortest-path DP splits the complete
symbol stream into minimum-band feasible intervals.

The final band may contain dummy zero literals.  They preserve vertical
backtick pairing but have no send instruction.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable


I64_MAX = 2**63 - 1


@dataclass(frozen=True)
class Chunk:
    start: int
    end: int
    value: int
    digits: int


@dataclass(frozen=True)
class Band:
    """One east/west row pair.

    ``top`` and ``bottom`` are in traversal order.  ``None`` entries are
    unsent dummy literals in the final band.
    """

    widths: tuple[int, ...]
    top: tuple[Chunk | None, ...]
    bottom: tuple[Chunk | None, ...]

    @property
    def chunks(self) -> tuple[Chunk, ...]:
        return tuple(c for c in self.top + self.bottom if c is not None)

    @property
    def required_width(self) -> int:
        return 5 + sum(width + 3 for width in self.widths)


class FeederOptimizer:
    def __init__(
        self,
        symbols: list[int],
        width: int,
        *,
        base: int = 92,
        max_symbols: int | None = None,
        max_slots: int | None = None,
    ) -> None:
        self.symbols = symbols
        self.nsymbols = len(symbols)
        self.width = width
        self.base = base
        self.max_symbols = max_symbols or self._safe_symbol_limit()
        # A slot needs at least one digit plus its two ticks and send cell.
        self.max_slots = max_slots or (width - 5) // 4
        self._lower_bounds = self._build_lower_bounds()
        self.outgoing = [self._chunks_from(i) for i in range(self.nsymbols)]
        self.incoming: list[list[Chunk]] = [[] for _ in range(self.nsymbols + 1)]
        for chunks in self.outgoing:
            for chunk in chunks:
                self.incoming[chunk.end].append(chunk)
        self._paired_choice: dict[tuple[int, int, int], tuple[Chunk, Chunk]] = {}
        self._plain_choice: dict[tuple[int, int, int], Chunk] = {}

    def _build_lower_bounds(self) -> list[list[int]]:
        """Value-independent lower bound for paired digit cost by symbol span."""
        impossible = self.nsymbols + 1
        result = [[impossible] * (2 * self.max_slots * self.max_symbols + 1)
                  for _ in range(self.max_slots + 1)]
        result[0][0] = 0
        min_digits = [0] + [
            len(str(self.base ** (count - 1)))
            for count in range(1, self.max_symbols + 1)
        ]
        pair_options: dict[int, int] = {}
        for left in range(1, self.max_symbols + 1):
            for right in range(1, self.max_symbols + 1):
                span = left + right
                cost = max(min_digits[left], min_digits[right])
                pair_options[span] = min(pair_options.get(span, impossible), cost)
        for slots in range(1, self.max_slots + 1):
            for old_span, old_cost in enumerate(result[slots - 1]):
                if old_cost == impossible:
                    continue
                for added_span, added_cost in pair_options.items():
                    result[slots][old_span + added_span] = min(
                        result[slots][old_span + added_span],
                        old_cost + added_cost,
                    )
        return result

    def _safe_symbol_limit(self) -> int:
        count = 1
        while self.base ** (count + 1) < 2**63:
            count += 1
        return count

    def _chunks_from(self, start: int) -> list[Chunk]:
        result: list[Chunk] = []
        value = 0
        power = 1
        limit = min(self.nsymbols, start + self.max_symbols)
        for end in range(start + 1, limit + 1):
            symbol = self.symbols[end - 1]
            value += symbol * power
            power *= self.base
            # A most-significant zero is lost by the repeated /92 decoder.
            if symbol == 0:
                continue
            spelling = str(value)
            if value <= I64_MAX and int(spelling[::-1]) <= I64_MAX:
                result.append(Chunk(start, end, value, len(spelling)))
        return result

    @lru_cache(maxsize=None)
    def _paired_cost(self, start: int, end: int, slots: int) -> int | None:
        """Minimum digit cells for exactly ``2*slots`` nested-paired chunks."""
        if slots == 0:
            return 0 if start == end else None
        span = end - start
        if span < 2 * slots or span > 2 * slots * self.max_symbols:
            return None
        if self._lower_bounds[slots][span] > self._capacity(slots):
            return None

        best: int | None = None
        best_pair: tuple[Chunk, Chunk] | None = None
        for first in self.outgoing[start]:
            if first.end >= end:
                break
            for last in self.incoming[end]:
                if last.start < first.end:
                    continue
                middle = self._paired_cost(first.end, last.start, slots - 1)
                if middle is None:
                    continue
                cost = max(first.digits, last.digits) + middle
                if best is None or cost < best:
                    best = cost
                    best_pair = (first, last)
        if best_pair is not None:
            self._paired_choice[(start, end, slots)] = best_pair
        return best

    @lru_cache(maxsize=None)
    def _plain_cost(self, start: int, end: int, chunks: int) -> int | None:
        """Minimum sum of digit widths for an unpaired chunk prefix."""
        if chunks == 0:
            return 0 if start == end else None
        span = end - start
        if span < chunks or span > chunks * self.max_symbols:
            return None
        best: int | None = None
        best_chunk: Chunk | None = None
        for chunk in self.outgoing[start]:
            rest = self._plain_cost(chunk.end, end, chunks - 1)
            if rest is None:
                continue
            cost = chunk.digits + rest
            if best is None or cost < best:
                best = cost
                best_chunk = chunk
        if best_chunk is not None:
            self._plain_choice[(start, end, chunks)] = best_chunk
        return best

    def _paired_chunks(self, start: int, end: int, slots: int) -> list[Chunk]:
        if slots == 0:
            return []
        first, last = self._paired_choice[(start, end, slots)]
        return [
            first,
            *self._paired_chunks(first.end, last.start, slots - 1),
            last,
        ]

    def _plain_chunks(self, start: int, end: int, chunks: int) -> list[Chunk]:
        result: list[Chunk] = []
        while chunks:
            chunk = self._plain_choice[(start, end, chunks)]
            result.append(chunk)
            start = chunk.end
            chunks -= 1
        return result

    def _capacity(self, slots: int) -> int:
        return self.width - 5 - 3 * slots

    def _full_transitions(self, start: int) -> Iterable[tuple[int, int, int]]:
        """Yield (end, slots, digit-cost) for complete two-row bands."""
        for slots in range(1, self.max_slots + 1):
            capacity = self._capacity(slots)
            if capacity < slots:
                continue
            lo = start + 2 * slots
            hi = min(self.nsymbols, start + 2 * slots * self.max_symbols)
            for end in range(lo, hi + 1):
                cost = self._paired_cost(start, end, slots)
                if cost is not None and cost <= capacity:
                    yield end, slots, cost

    def _final_band(self, start: int) -> tuple[int, int, list[Chunk | None]] | None:
        """Return (slots, digit-cost, padded chunks) for the final partial band."""
        best: tuple[int, int, list[Chunk | None]] | None = None
        for slots in range(1, self.max_slots + 1):
            capacity = self._capacity(slots)
            if capacity < slots:
                continue

            # ``dummy`` is the number of absent chunks at the end of traversal.
            for dummy in range(0, 2 * slots):
                actual = 2 * slots - dummy
                if not actual <= self.nsymbols - start <= actual * self.max_symbols:
                    continue
                if dummy < slots:
                    # The first ``dummy`` top chunks pair with final dummies;
                    # the remaining interval consists of ordinary nested pairs.
                    paired_slots = slots - dummy
                    for boundary in range(
                        start + dummy,
                        min(self.nsymbols, start + dummy * self.max_symbols) + 1,
                    ):
                        prefix = self._plain_cost(start, boundary, dummy)
                        paired = self._paired_cost(boundary, self.nsymbols, paired_slots)
                        if prefix is None or paired is None:
                            continue
                        cost = prefix + paired
                        if cost > capacity:
                            continue
                        chunks = (
                            self._plain_chunks(start, boundary, dummy)
                            + self._paired_chunks(boundary, self.nsymbols, paired_slots)
                            + [None] * dummy
                        )
                        candidate = (slots, cost, chunks)
                        if best is None or (cost, slots) < (best[1], best[0]):
                            best = candidate
                else:
                    # All actual chunks are on the top row.  Remaining top
                    # slots and the complete bottom row are dummy literals.
                    prefix = self._plain_cost(start, self.nsymbols, actual)
                    if prefix is None:
                        continue
                    cost = prefix + (slots - actual)
                    if cost > capacity:
                        continue
                    chunks = (
                        self._plain_chunks(start, self.nsymbols, actual)
                        + [None] * dummy
                    )
                    candidate = (slots, cost, chunks)
                    if best is None or (cost, slots) < (best[1], best[0]):
                        best = candidate
        return best

    @staticmethod
    def _make_band(slots: int, chunks: list[Chunk | None]) -> Band:
        assert len(chunks) == 2 * slots
        top = tuple(chunks[:slots])
        bottom = tuple(chunks[slots:])
        widths = tuple(
            max(
                top[j].digits if top[j] is not None else 1,
                bottom[slots - 1 - j].digits
                if bottom[slots - 1 - j] is not None
                else 1,
            )
            for j in range(slots)
        )
        return Band(widths, top, bottom)

    def optimize(self) -> list[Band]:
        """Return a minimum-row feeder plan, breaking ties by used digit cells."""
        infinity = self.nsymbols + 1
        bands = [infinity] * (self.nsymbols + 1)
        used = [infinity * infinity] * (self.nsymbols + 1)
        parent: list[tuple[int, int] | None] = [None] * (self.nsymbols + 1)
        bands[0] = 0
        used[0] = 0

        final: tuple[int, int, int, list[Chunk | None]] | None = None
        for start in range(self.nsymbols):
            if bands[start] == infinity:
                continue

            partial = self._final_band(start)
            if partial is not None:
                slots, cost, chunks = partial
                candidate = (bands[start] + 1, used[start] + cost, start, chunks)
                if final is None or candidate[:2] < final[:2]:
                    final = candidate

            for end, slots, cost in self._full_transitions(start):
                if end == self.nsymbols:
                    chunks = self._paired_chunks(start, end, slots)
                    candidate = (bands[start] + 1, used[start] + cost, start, chunks)
                    if final is None or candidate[:2] < final[:2]:
                        final = candidate
                    continue
                candidate = (bands[start] + 1, used[start] + cost)
                if candidate < (bands[end], used[end]):
                    bands[end], used[end] = candidate
                    parent[end] = (start, slots)

        if final is None:
            raise ValueError(
                f"no feeder plan fits width={self.width}, max_slots={self.max_slots}"
            )

        _, _, final_start, final_chunks = final
        reversed_bands: list[Band] = []
        end = final_start
        while end:
            previous, slots = parent[end]  # type: ignore[misc]
            chunks = self._paired_chunks(previous, end, slots)
            reversed_bands.append(self._make_band(slots, chunks))
            end = previous
        result = list(reversed(reversed_bands))
        result.append(self._make_band(len(final_chunks) // 2, final_chunks))
        assert [c.start for band in result for c in band.chunks] == [
            0,
            *[c.end for band in result for c in band.chunks][:-1],
        ]
        assert result[-1].chunks[-1].end == self.nsymbols
        assert all(band.required_width <= self.width for band in result)
        return result


def optimize_feeder(
    symbols: list[int],
    width: int,
    *,
    base: int = 92,
    max_symbols: int | None = None,
    max_slots: int | None = None,
) -> list[Band]:
    return FeederOptimizer(
        symbols,
        width,
        base=base,
        max_symbols=max_symbols,
        max_slots=max_slots,
    ).optimize()


def _load_builder():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "build_ring.py")
    spec = importlib.util.spec_from_file_location("history_ring_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("width", nargs="*", type=int, default=[82, 83])
    parser.add_argument(
        "--max-slots",
        type=int,
        help="optional search cap; by default try every slot count that fits",
    )
    args = parser.parse_args()

    builder = _load_builder()
    symbols, _, _ = builder.build_encoding()
    print(f"symbols={len(symbols)}")
    for width in args.width:
        plan = optimize_feeder(symbols, width, max_slots=args.max_slots)
        chunks = [chunk for band in plan for chunk in band.chunks]
        slot_hist: dict[int, int] = {}
        for band in plan:
            slot_hist[len(band.widths)] = slot_hist.get(len(band.widths), 0) + 1
        print(
            f"width={width}: rows={2 * len(plan)} bands={len(plan)} "
            f"chunks={len(chunks)} max_used={max(b.required_width for b in plan)} "
            f"slots={slot_hist}"
        )


if __name__ == "__main__":
    main()
