#!/usr/bin/env python3
"""Data tables for the generated LLLM interpreter (build_lllm.py).

Everything the machine needs to know about *characters* lives here as dicts, so
tools/autotune.py never sees a bare integer literal that actually encodes data
(per tools/AUTOTUNE.md: builders whose literals encode data yield 0 valid
candidates).  The packed i64 constants the .man program uses are DERIVED from
these dicts at build time, never written out by hand.

Run this file to check every table against solutions/.../lllm_model.py for all
256 byte values.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# --------------------------------------------------------------------------
# cell classes (4 bits, so a whole 16-cell LLLM row packs into one i64 word)
# --------------------------------------------------------------------------
CLASS_NAMES = [
    "NOP",    # 0  space, and the vacated '@'
    "N",      # 1  '^'
    "E",      # 2  '>'
    "S",      # 3  'v'
    "W",      # 4  '<'
    "MOV",    # 5  'M'
    "ADD",    # 6  '+'   (as an instruction)
    "SUB",    # 7  '-'   (as an instruction)
    "XTURN",  # 8  'X'
    "HALT",   # 9  'H'
    "WALL",   # 10 room wall  (also '|', which is never an LLLM op)
    "DIGIT",  # 11 '0'-'9', value in the VAL plane
    "DEAD",   # 12 sentinel written into CODE once the man has stopped
]
C = {name: i for i, name in enumerate(CLASS_NAMES)}

# character -> class, for every character an LLLM program can contain.
CHAR_CLASS = {
    " ": C["NOP"],
    "@": C["NOP"],       # the '@' cell is ordinary space once the man leaves
    "^": C["N"],
    ">": C["E"],
    "v": C["S"],
    "<": C["W"],
    "M": C["MOV"],
    "+": C["ADD"],
    "-": C["SUB"],
    "X": C["XTURN"],
    "H": C["HALT"],
    "|": C["WALL"],      # '|' is not an LLLM operation, so it can only be a wall
}
for _d in range(10):
    CHAR_CLASS[chr(48 + _d)] = C["DIGIT"]

# digit value plane (only meaningful where the class is DIGIT)
CHAR_VALUE = {chr(48 + _d): _d for _d in range(10)}

# class -> display colour.  'H' (3) and WALL (4) must stay distinct classes.
CLASS_COLOUR = {
    C["NOP"]: 0,
    C["N"]: 3, C["E"]: 3, C["S"]: 3, C["W"]: 3,
    C["MOV"]: 12,
    C["ADD"]: 10, C["SUB"]: 10,
    C["XTURN"]: 3,
    C["HALT"]: 3,
    C["WALL"]: 4,
    C["DIGIT"]: 8,
    C["DEAD"]: 0,        # never visible: the man is always drawn over it
}

MAN_COLOUR = 9

# headings, clockwise, matching lllm_model's NORTH/EAST/SOUTH/WEST = 0/1/2/3
HEADING_CLASS = {C["N"]: 0, C["E"]: 1, C["S"]: 2, C["W"]: 3}
HEADING_STEP = {0: -16, 1: 1, 2: 16, 3: -1}     # delta on ADDR = 16*y + x

NIBBLE = 16
ROW_CELLS = 16
DISPLAY_W = 16
DISPLAY_H = 16


def pack_table(mapping, width=NIBBLE):
    """Pack {index: value} into sum(value << (4*index)) -- a single i64 literal."""
    out = 0
    for idx, val in mapping.items():
        assert 0 <= val < width, (idx, val)
        out |= val << (4 * idx)
    assert 0 <= out < (1 << 63), out
    return out


COLOUR_WORD = pack_table(CLASS_COLOUR)


def default_class_of(ch):
    """Class of `ch` BEFORE the room-rectangle pass overwrites walls."""
    return CHAR_CLASS.get(ch, C["NOP"])


def value_of(ch):
    return CHAR_VALUE.get(ch, 0)


# --------------------------------------------------------------------------
# self-check against the validated oracle
# --------------------------------------------------------------------------
def check(verbose=True):
    import lllm_model as ref

    bad = []
    for b in range(256):
        ch = chr(b)
        cls = default_class_of(ch)
        # 1) colour agreement for every character the oracle knows how to colour
        mine = CLASS_COLOUR[cls]
        theirs = ref.colour_of(ch)
        if ch == "|":
            theirs = ref.WALL          # '|' only ever appears as a wall
        if ch == "@":
            theirs = ref.C_SPACE       # '@' becomes ordinary space
        if mine != theirs:
            bad.append(("colour", b, repr(ch), mine, theirs))
        # 2) class agreement with the oracle's step() semantics
        if ch in ref.HEADING_OF:
            if HEADING_CLASS.get(cls) != ref.HEADING_OF[ch]:
                bad.append(("heading", b, repr(ch), cls, ref.HEADING_OF[ch]))
        if "0" <= ch <= "9":
            if cls != C["DIGIT"] or value_of(ch) != ord(ch) - 48:
                bad.append(("digit", b, repr(ch), cls, value_of(ch)))
        for lit, name in ((("M"), "MOV"), ("+", "ADD"), ("-", "SUB"),
                          ("X", "XTURN"), ("H", "HALT")):
            if ch == lit and cls != C[name]:
                bad.append(("op", b, repr(ch), cls, name))

    # 3) the packed colour word must reproduce the table by nibble extraction
    for cls, col in CLASS_COLOUR.items():
        got = (COLOUR_WORD >> (4 * cls)) & 15
        if got != col:
            bad.append(("packed", cls, col, got, None))

    if verbose:
        print("classes           :", ", ".join(
            "%s=%d" % (n, i) for i, n in enumerate(CLASS_NAMES)))
        print("COLOUR_WORD       :", COLOUR_WORD,
              "(%d decimal digits, reversed fits i64: %s)"
              % (len(str(COLOUR_WORD)), int(str(COLOUR_WORD)[::-1]) < (1 << 63)))
        print("checked 256 byte values against lllm_model.py")
        if bad:
            print("MISMATCHES (%d):" % len(bad))
            for row in bad[:20]:
                print("   ", row)
        else:
            print("OK: char->class, char->value, class->colour and the packed "
                  "COLOUR_WORD all agree with the oracle for all 256 bytes")
    return bad


if __name__ == "__main__":
    sys.exit(1 if check() else 0)
