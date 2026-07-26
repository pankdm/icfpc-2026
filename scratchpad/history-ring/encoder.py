#!/usr/bin/env python3
"""Grammar encoder for history-lesson ring-dictionary build.

Stream alphabet (base B1 >= 92):
  0            year boundary marker ("; YYYY: ", 2000..2026)
  1..91        shifted ASCII (byte-31); 13 doubles as the ", " token
  ESC=29, k    pair phrase ref -> ring1 position k (k chosen >= first_pair_pos)
  small singles: unused shifted values {2,4,5,6,7,8,11,12,16} -> ring1 position v
  ext singles: values 92..B1-1 -> ring1 position v-92+17

Ring1 entries are packed base-128 raw-ASCII strings (LSB first, <= 9 symbols).
Identity entries at small positions map v -> v+31.  Position 13 -> ", ".
Passthrough (D1) adds 31 to ordinary symbols 17..91.

Decode chain (simulated in verify()):
  chunks -> divmod B1 -> D1 -> L1 -> year -> divmod 128 -> bytes
"""
from __future__ import annotations
import math, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = open(os.path.join(HERE, "..", "..", "solutions", "history-lesson",
                         "icfp-history.txt"), "rb").read()

ESC = 29
STOLEN = (8,)              # apostrophe: 1 occurrence, worth a single slot
SMALL_FREE = [2, 4, 5, 6, 7, 11, 12, 16] + list(STOLEN)
FIRST_YEAR, LAST_YEAR = 2000, 2026
B2 = 128                   # spelling/packing base for raw ASCII
DIG1 = None                # set per B1


def tokenize(data: bytes) -> list[int]:
    """0 = year boundary, 13 = ', ', else shifted byte.  Stolen values are
    emitted as byte tokens too (they will be phrase-forced later)."""
    toks, i, year = [], 0, FIRST_YEAR
    while i < len(data):
        if year <= LAST_YEAR:
            b = f"; {year}: ".encode()
            if data.startswith(b, i):
                toks.append(0); i += len(b); year += 1; continue
        if data[i:i+2] == b", ":
            toks.append(13); i += 2; continue
        toks.append(data[i] - 31); i += 1
    assert year == LAST_YEAR + 1
    return toks


def spell(tok: int) -> bytes:
    """Raw bytes a single token expands to."""
    if tok == 13:
        return b", "
    return bytes([tok + 31])


def pack128(bs: bytes) -> int:
    v = 0
    for i, c in enumerate(bs):
        v += c * (B2 ** i)
    assert v < 2**63
    return v


def count_nonoverlap(stream, pat):
    n, m, i, t = len(stream), len(pat), 0, 0
    while i <= n - m:
        if tuple(stream[i:i+m]) == pat:
            t += 1; i += m
        else:
            i += 1
    return t


def replace_nonoverlap(stream, pat, rep):
    out, i, n, m = [], 0, len(stream), len(pat)
    while i < n:
        if tuple(stream[i:i+m]) == pat:
            out.extend(rep); i += m
        else:
            out.append(stream[i]); i += 1
    return out


def phrase_bytes(pat) -> bytes:
    return b"".join(spell(t) for t in pat)


def choose_phrases(stream, n_singles, dig1, max_pairs=70, verbose=False):
    """Greedy: each round pick the best candidate under its best remaining
    slot type (single saves (m-1)t, pair saves (m-2)t).  Refs are atomic
    negative tokens; phrases may not contain 0, ESC, stolen or refs."""
    forbidden = set(STOLEN) | {0, ESC}
    singles_left = n_singles
    n_small = len(SMALL_FREE)
    pairs_left = max_pairs
    phrases = []          # (pat, is_single) in pick order
    # forced: stolen values must round-trip via a pair phrase
    for v in STOLEN:
        stream = replace_nonoverlap(stream, (v,), [-len(phrases) - 1])
        phrases.append(((v,), False))
        pairs_left -= 1
    while True:
        n = len(stream)
        cnt = {}
        for m in range(2, 10):
            local = Counter()
            for i in range(n - m + 1):
                seg = tuple(stream[i:i+m])
                if any((s in forbidden) or s < 1 for s in seg):
                    continue
                if len(phrase_bytes(seg)) > 9:
                    continue
                local[seg] += 1
            for seg, c in local.items():
                if c >= 2:
                    cnt[seg] = c
        best = (1e-9, None, None)
        for seg, _ in cnt.items():
            m = len(seg)
            t = count_nonoverlap(stream, seg)
            if t < 2:
                continue
            table_cost = len(str(pack128(phrase_bytes(seg)))) + 3
            if singles_left:
                # extended-base slots (beyond the free small values) already
                # cost ~8 digits across the whole stream via the larger base;
                # that shows up in the measured totals per B1, but bias the
                # greedy so it only takes ext slots for clearly-worth phrases.
                used_singles = sum(1 for _, s in phrases if s)
                ext_penalty = 0 if used_singles < n_small else 8
                gain = dig1 * (m - 1) * t - table_cost - ext_penalty
                if gain > best[0]:
                    best = (gain, seg, True)
            if pairs_left:
                gain = dig1 * (m - 2) * t - table_cost
                if gain > best[0]:
                    best = (gain, seg, False)
        if best[1] is None:
            break
        _, seg, single = best
        if single:
            singles_left -= 1
        else:
            pairs_left -= 1
        stream = replace_nonoverlap(stream, seg, [-len(phrases) - 1])
        phrases.append((seg, single))
        if verbose:
            print(f"  {'S' if single else 'P'} {phrase_bytes(seg)!r} "
                  f"t={count_nonoverlap(stream, (-len(phrases),)) } gain={best[0]:.0f}")
    return stream, phrases


def assign(stream, phrases, b1):
    """Assign ring positions/values.  Returns final symbol stream and ring1
    table (position -> packed value)."""
    singles = [i for i, (p, s) in enumerate(phrases) if s]
    pairs = [i for i, (p, s) in enumerate(phrases) if not s]
    # order singles by frequency descending is irrelevant; slots equivalent.
    small_slots = sorted(SMALL_FREE)
    ext_slots = list(range(92, b1))
    slot_of = {}
    ring = {}
    n_ext = len(singles) - len(small_slots)
    it_small = iter(small_slots)
    it_ext = iter(ext_slots)
    for i in singles:
        # prefer small slots first
        try:
            v = next(it_small)
            pos = v
        except StopIteration:
            v = next(it_ext)
            pos = v - 92 + 17
        slot_of[i] = ("single", v, pos)
        ring[pos] = pack128(phrase_bytes(phrases[i][0]))
    first_pair_pos = 17 + max(0, len(singles) - len(small_slots))
    for j, i in enumerate(pairs):
        pos = first_pair_pos + j
        assert pos <= b1 - 1, "pair position exceeds symbol range"
        slot_of[i] = ("pair", pos, pos)
        ring[pos] = pack128(phrase_bytes(phrases[i][0]))
    # identities for used small values (incl 13 -> ', ')
    for v in range(1, 17):
        if v in ring:
            continue
        if v in SMALL_FREE:
            ring[v] = 9  # placeholder, never referenced (single digit: cheap)
        else:
            ring[v] = pack128(spell(v))
    # fill any position gaps with placeholder
    maxpos = max(ring)
    for p in range(1, maxpos + 1):
        ring.setdefault(p, 9)
    # final stream
    out = []
    for t in stream:
        if t >= 0:
            out.append(t)
        else:
            kind, v, pos = slot_of[-t - 1]
            if kind == "single":
                out.append(v)
            else:
                out.extend([ESC, pos])
    return out, ring


def pack_chunks(symbols, b1, digit_widths):
    maxsym = 1
    while (b1 ** (maxsym + 1)) < 2**63:
        maxsym += 1
    chunks, i = [], 0
    while i < len(symbols):
        row, slot = divmod(len(chunks), len(digit_widths))
        phys = slot if row % 2 == 0 else len(digit_widths) - 1 - slot
        maxd = digit_widths[phys]
        for count in range(min(maxsym, len(symbols) - i), 0, -1):
            if symbols[i + count - 1] == 0:
                continue
            v = sum(symbols[i + j] * b1**j for j in range(count))
            if v < 2**63 and len(str(v)) <= maxd:
                chunks.append(v); i += count
                break
        else:
            raise ValueError(f"cannot chunk at {i}")
    return chunks


def year_packed(year):
    return pack128(f"; {year}: ".encode())


def verify(chunks, ring, b1, data=TEXT):
    """Simulate the full decode pipeline."""
    # decoder
    syms = []
    for c in chunks:
        while c:
            c, r = divmod(c, b1)
            syms.append(r)
    # D1 + L1
    mid = []
    i = 0
    while i < len(syms):
        v = syms[i]; i += 1
        if v == 0:
            mid.append(0)
        elif v == ESC:
            k = syms[i]; i += 1
            mid.append(ring[k])
        elif v <= 16:
            mid.append(ring[v])
        elif v >= 92:
            mid.append(ring[v - 92 + 17])
        else:
            mid.append(v + 31)
    # year machine
    out_vals = []
    year = FIRST_YEAR
    B = year_packed(FIRST_YEAR)
    bp = 10
    STEP = B2 ** 5
    CORR = B2 ** 4 - 10 * B2 ** 5
    for v in mid:
        if v > 0:
            out_vals.append(v)
        else:
            out_vals.append(B)
            B += STEP
            bp -= 1
            if bp == 0:
                B += CORR
                bp = 10
    # unpack 128
    out = bytearray()
    for v in out_vals:
        while v:
            v, r = divmod(v, B2)
            out.append(r)
    return bytes(out) == data, bytes(out)


def build_encoding(b1, digit_widths, verbose=False):
    dig1 = math.log10(b1)
    stream0 = tokenize(TEXT)
    n_singles = len(SMALL_FREE) + (b1 - 92)
    stream, phrases = choose_phrases(stream0, n_singles, dig1, verbose=verbose)
    symbols, ring = assign(stream, phrases, b1)
    chunks = pack_chunks(symbols, b1, digit_widths)
    ok, out = verify(chunks, ring, b1)
    return dict(ok=ok, symbols=symbols, ring=ring, chunks=chunks,
                phrases=phrases, stream_digits=sum(len(str(c)) for c in chunks),
                table_digits=sum(len(str(v)) for v in ring.values()),
                nring=max(ring))


def main():
    for b1 in (92, 96, 100, 104, 110):
        r = build_encoding(b1, (18, 18, 18, 18))
        n_chunks = len(r["chunks"])
        stream_cells = r["stream_digits"] + 3 * n_chunks
        table_cells = r["table_digits"] + 3 * len(r["ring"])
        print(f"B1={b1}: ok={r['ok']} syms={len(r['symbols'])} "
              f"chunks={n_chunks} streamdig={r['stream_digits']} "
              f"tabledig={r['table_digits']} ring={r['nring']} "
              f"cells~{stream_cells + table_cells} "
              f"(stream {stream_cells} + table {table_cells}) "
              f"phrases={len(r['phrases'])}")


if __name__ == "__main__":
    main()
