#!/usr/bin/env python3
"""Greedy dictionary optimizer for history-lesson with ESC-pair phrase refs.

Stream model: base-92 symbols; year boundaries -> 0; ", " -> 13; phrase ref ->
[ESC, k] (2 symbols).  Phrase spellings are pure symbol strings, 3..9 symbols
(one i64 ring entry each).  Cost model in decimal digits (~cells):
  saving(phrase) = 1.964*((m-2)*t) : stream symbols removed
  cost(phrase)   = 1.964*m + 3     : ring entry digits + literal overhead
"""
import math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOL = os.path.join(HERE, "..", "..", "solutions", "history-lesson")
sys.path.insert(0, SOL)
import build_with_year as b

DIG = math.log10(92)

def base_stream():
    data = open(os.path.join(SOL, "icfp-history.txt"), "rb").read()
    # tokenize years + comma but NOT the 'and ' glyph: replicate tokenize minus AND
    syms = []
    i = 0
    expected = b.FIRST_GENERATED_YEAR
    while i < len(data):
        if expected <= b.LAST_GENERATED_YEAR:
            boundary = f"; {expected}: ".encode()
            if data.startswith(boundary, i):
                syms.append(0); i += len(boundary); expected += 1; continue
        if data[i:i+2] == b", ":
            syms.append(13); i += 2; continue
        syms.append(data[i] - 31); i += 1
    return syms

def count_nonoverlap(stream, pat):
    n, m, i, t = len(stream), len(pat), 0, 0
    while i <= n - m:
        if stream[i:i+m] == pat:
            t += 1; i += m
        else:
            i += 1
    return t

def replace_nonoverlap(stream, pat, rep):
    out, i, n, m = [], 0, len(stream), len(pat)
    while i < n:
        if stream[i:i+m] == pat:
            out.extend(rep); i += m
        else:
            out.append(stream[i]); i += 1
    return out

def best_phrase(stream, forbidden):
    # candidate substrings 3..9 syms, all pure (no 0, no ESC refs)
    from collections import Counter
    best = (0, None)
    n = len(stream)
    for m in range(3, 10):
        cnt = Counter()
        for i in range(n - m + 1):
            seg = tuple(stream[i:i+m])
            if any(s in forbidden or s < 1 for s in seg):
                continue
            cnt[seg] += 1
        for seg, c in cnt.items():
            if c < 2:
                continue
            t = count_nonoverlap(stream, list(seg))
            gain = DIG * ((m - 2) * t) - (DIG * m + 3)
            if gain > best[0]:
                best = (gain, list(seg))
    return best

def main():
    ESC = 2
    stream = base_stream()
    print("base symbols:", len(stream), "digits ~", round(len(stream)*DIG))
    forbidden = {0, ESC}
    phrases = []
    while True:
        gain, pat = best_phrase(stream, forbidden)
        if pat is None or gain <= 0:
            break
        k = len(phrases) + 1
        t = count_nonoverlap(stream, pat)
        # refs are atomic tokens -k in the working stream (forbidden in future
        # phrases since <0); expanded to [ESC, k] only at the very end.
        stream = replace_nonoverlap(stream, pat, [-k])
        phrases.append((pat, t, gain))
        text = "".join(chr(s + 31) if 1 <= s < 92 else f"<{s}>" for s in pat)
        print(f"#{k}: {text!r} t={t} m={len(pat)} gain={gain:.0f} -> stream {len(stream)}")
        if len(phrases) >= 60:
            break
    total_table_digits = sum(len(str(b.packed_symbols(p))) for p, _, _ in phrases)
    final_syms = sum(2 if s < 0 else 1 for s in stream)
    print("phrases:", len(phrases))
    print("final stream symbols (refs=2):", final_syms)
    print("stream digits ~", round(final_syms*DIG))
    print("table digits:", total_table_digits)
    print("grand digits ~", round(final_syms*DIG) + total_table_digits)

if __name__ == "__main__":
    main()
