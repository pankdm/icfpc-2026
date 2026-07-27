"""Load and encode the raw-text dictionary selected by generate_dictionary.py."""
from __future__ import annotations

import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(HERE, "dictionary_words.json")
B2 = 128


def pack128(word: bytes) -> int:
    value = 0
    for index, byte in enumerate(word):
        value += byte * B2 ** index
    return value


def load_catalog(path: str = CATALOG_PATH) -> dict:
    with open(path, encoding="utf-8") as source:
        return json.load(source)


def _replace_nonoverlap(stream, pattern, replacement):
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


def build_encoding(
    data: bytes,
    words: int,
    catalog: dict | None = None,
) -> tuple[list[int], dict[int, int], dict]:
    catalog = catalog or load_catalog()
    minimum = catalog["minimum_words"]
    maximum = catalog["maximum_words"]
    if not minimum <= words <= maximum:
        raise ValueError(f"dictionary words must be in {minimum}..{maximum}")

    actions = [
        action
        for action in catalog["actions"]
        if action["min_words"] <= words
    ]
    direct_words = {
        position: bytes([position + 31])
        for position in range(1, 17)
    }
    escaped_words = {}
    stream = [byte - 31 for byte in data]

    for action in actions:
        word = action["word"].encode("ascii")
        pattern = tuple(byte - 31 for byte in word)
        slot = action["slot"]
        stream = _replace_nonoverlap(stream, pattern, ("ref", slot))
        if action["kind"] == "direct":
            direct_words[slot] = word
        else:
            escaped_words[slot] = word

    ring = {
        position: pack128(word)
        for position, word in direct_words.items()
    }
    ring.update(
        (position, pack128(word))
        for position, word in escaped_words.items()
    )
    if sorted(ring) != list(range(1, words + 1)):
        raise AssertionError((words, sorted(ring)))

    symbols = []
    references = {position: 0 for position in ring}
    for token in stream:
        if isinstance(token, tuple):
            position = token[1]
            references[position] += 1
            if position <= 16:
                symbols.append(position)
            else:
                symbols.extend([catalog["escape"], position])
        elif 1 <= token <= 16:
            # Every occurrence of a repurposed direct character must already
            # have been converted through its escaped identity action.
            expected = bytes([token + 31])
            if direct_words[token] != expected:
                raise AssertionError(
                    f"unescaped displaced direct symbol {token}"
                )
            references[token] += 1
            symbols.append(token)
        elif token in (17, catalog["escape"]):
            raise AssertionError(f"unescaped reserved symbol {token}")
        else:
            symbols.append(token)

    metadata = {
        "catalog": catalog,
        "actions": actions,
        "references": references,
        "words": {
            position: (
                direct_words[position]
                if position <= 16
                else escaped_words[position]
            ).decode("ascii")
            for position in ring
        },
    }
    decoded_values = []
    index = 0
    while index < len(symbols):
        symbol = symbols[index]
        index += 1
        if symbol == catalog["escape"]:
            decoded_values.append(ring[symbols[index]])
            index += 1
        elif symbol <= 16:
            decoded_values.append(ring[symbol])
        else:
            decoded_values.append(symbol + 31)
    decoded = bytearray()
    for value in decoded_values:
        while value:
            value, byte = divmod(value, B2)
            decoded.append(byte)
    if bytes(decoded) != data:
        raise AssertionError("raw dictionary encoding failed round-trip")
    return symbols, ring, metadata
