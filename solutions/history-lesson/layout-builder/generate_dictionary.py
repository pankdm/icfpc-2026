#!/usr/bin/env python3
"""Generate the raw-text History Lesson dictionary catalog.

Unlike the older ring builders, this encoder does not replace years with
markers and does not reserve a combined `", "` token. It searches phrases
directly in the final output bytes. The generated JSON separates semantic
phrase priority from the layout builder's physical ring ordering.
"""
from __future__ import annotations

import json
import math
import os
from collections import Counter


HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.dirname(HERE)
TEXT_PATH = os.path.join(HISTORY_DIR, "icfp-history.txt")
OUTPUT_PATH = os.path.join(HERE, "dictionary_words.json")

B1 = 92
B2 = 128
ESC = 29
# The first nine are absent in the raw stream (slot 8 is restored through an
# escape). Slot 13 becomes free after the first selected phrase consumes every
# comma as part of `", "`, so it is deliberately selected last.
DIRECT_PHRASE_SLOTS = [2, 4, 5, 6, 7, 8, 11, 12, 16, 13]
MAX_WORDS = 91


def pack128(word: bytes) -> int:
    value = 0
    for index, byte in enumerate(word):
        value += byte * B2 ** index
    return value


def fits_literal(word: bytes) -> bool:
    value = pack128(word)
    spelling = str(value)
    return (
        0 < value < 2 ** 63
        and int(spelling[::-1]) < 2 ** 63
        and len(spelling) <= 18
    )


def replace_nonoverlap(stream, pattern, replacement):
    output = []
    index = 0
    size = len(pattern)
    while index < len(stream):
        if tuple(stream[index:index + size]) == pattern:
            output.append(replacement)
            index += size
        else:
            output.append(stream[index])
            index += 1
    return output


def count_nonoverlap(stream, pattern) -> int:
    count = 0
    index = 0
    size = len(pattern)
    while index <= len(stream) - size:
        if tuple(stream[index:index + size]) == pattern:
            count += 1
            index += size
        else:
            index += 1
    return count


def candidates(stream, minimum_length: int):
    found = {}
    for size in range(minimum_length, 10):
        counts = Counter(
            tuple(stream[index:index + size])
            for index in range(len(stream) - size + 1)
            if all(isinstance(token, int) for token in stream[index:index + size])
        )
        for pattern, overlapping_count in counts.items():
            if overlapping_count < 2:
                continue
            word = bytes(token + 31 for token in pattern)
            if fits_literal(word):
                found[pattern] = count_nonoverlap(stream, pattern)
    return found


def choose_dictionary(data: bytes):
    stream = [byte - 31 for byte in data]
    # Bare 17 is reserved by DISP. Apostrophe (symbol 8) is displaced only
    # when budget >=18 so its direct slot can hold a phrase.
    actions = [
        {
            "kind": "escaped",
            "slot": 17,
            "word": "0",
            "min_words": 17,
            "reason": "bare symbol 17 is reserved",
        },
        {
            "kind": "escaped",
            "slot": 18,
            "word": "'",
            "min_words": 18,
            "reason": "restore direct slot 8 when it is used by a phrase",
        },
    ]
    stream = replace_nonoverlap(stream, (17,), ("ref", 17))
    stream = replace_nonoverlap(stream, (8,), ("ref", 18))

    digit_weight = math.log10(B1)

    # Direct phrases do not increase the ring size: they occupy direct slots
    # whose source characters are absent, except slot 8 whose apostrophe is
    # restored through escaped slot 18. Pick them occurrence-first, replacing
    # the residual stream after every choice before recounting candidates.
    for slot in DIRECT_PHRASE_SLOTS:
        if count_nonoverlap(stream, (slot,)):
            raise ValueError(
                f"cannot repurpose direct slot {slot}: raw symbol remains"
            )
        best = None
        for pattern, occurrences in candidates(stream, 2).items():
            word = bytes(token + 31 for token in pattern)
            table_cost = len(str(pack128(word))) + 3
            symbol_saving = (len(pattern) - 1) * occurrences
            source_cell_gain = digit_weight * symbol_saving - table_cost
            key = (
                occurrences,
                symbol_saving,
                source_cell_gain,
                -len(str(pack128(word))),
                len(pattern),
                word,
            )
            if source_cell_gain > 0 and (best is None or key > best[0]):
                best = (
                    key,
                    pattern,
                    occurrences,
                    word,
                    source_cell_gain,
                    symbol_saving,
                )
        if best is None:
            raise ValueError(f"no beneficial direct phrase for slot {slot}")
        _, pattern, occurrences, word, source_cell_gain, symbol_saving = best
        actions.append({
            "kind": "direct",
            "slot": slot,
            "word": word.decode("ascii"),
            "min_words": 18 if slot == 8 else 17,
            "occurrences_at_selection": occurrences,
            "symbol_saving": symbol_saving,
            "source_cell_gain": round(source_cell_gain, 6),
            "selection_basis": "highest residual occurrence count",
        })
        stream = replace_nonoverlap(stream, pattern, ("ref", slot))

    # Escaped phrases cost two stream symbols. Recompute the residual stream
    # after every choice and rank current candidates by occurrence count
    # first. Symbol saving and literal size are only tie-breakers.
    next_escaped_slot = 19
    while next_escaped_slot <= MAX_WORDS:
        best = None
        for pattern, occurrences in candidates(stream, 3).items():
            saving = (len(pattern) - 2) * occurrences
            if saving <= 0:
                continue
            word = bytes(token + 31 for token in pattern)
            table_cost = len(str(pack128(word))) + 3
            source_cell_gain = digit_weight * saving - table_cost
            key = (
                occurrences,
                saving,
                source_cell_gain,
                -len(str(pack128(word))),
                len(pattern),
                word,
            )
            if best is None or key > best[0]:
                best = (
                    key,
                    pattern,
                    occurrences,
                    word,
                    source_cell_gain,
                )
        if best is None:
            break
        _, pattern, occurrences, word, source_cell_gain = best
        slot = next_escaped_slot
        next_escaped_slot += 1
        actions.append({
            "kind": "escaped",
            "slot": slot,
            "word": word.decode("ascii"),
            "min_words": slot,
            "occurrences_at_selection": occurrences,
            "symbol_saving": (len(pattern) - 2) * occurrences,
            "source_cell_gain": round(source_cell_gain, 6),
            "selection_basis": "highest residual occurrence count",
        })
        stream = replace_nonoverlap(stream, pattern, ("ref", slot))

    return {
        "version": 2,
        "source": "../icfp-history.txt",
        "encoding": "raw ASCII bytes shifted by 31; no year mapping",
        "base": B1,
        "escape": ESC,
        "minimum_words": 17,
        "maximum_words": next_escaped_slot - 1,
        "actions": actions,
    }


def main() -> None:
    with open(TEXT_PATH, "rb") as source:
        catalog = choose_dictionary(source.read())
    with open(OUTPUT_PATH, "w", encoding="utf-8") as output:
        json.dump(catalog, output, indent=2, ensure_ascii=True)
        output.write("\n")
    direct = sum(action["kind"] == "direct" for action in catalog["actions"])
    escaped = sum(action["kind"] == "escaped" for action in catalog["actions"])
    print(
        f"wrote {OUTPUT_PATH}: {direct} direct phrases, "
        f"{escaped} escaped entries, budgets "
        f"{catalog['minimum_words']}..{catalog['maximum_words']}"
    )


if __name__ == "__main__":
    main()
