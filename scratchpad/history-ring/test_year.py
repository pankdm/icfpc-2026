#!/usr/bin/env python3
"""Roomsim test for the fresh year room design (base-128 constants)."""
from roomsim import run

B2 = 128


def pack128(bs):
    v = 0
    for i, c in enumerate(bs):
        v += c * (B2 ** i)
    return v


INIT = pack128(b"; 2000: ")
STEP = B2 ** 5
CORR = B2 ** 4 - 10 * B2 ** 5   # negative
ACORR = abs(CORR)


def year_rows():
    d_init = str(INIT)
    assert len(d_init) == 17, len(d_init)
    d_step = str(STEP)
    assert len(d_step) == 11
    d_corr = str(ACORR)
    assert len(d_corr) == 12
    W = 27
    row0 = "@`" + d_init + "`M`10`bv"
    assert len(row0) == 27, len(row0)
    row1 = "v  <" + " " * 19 + "<  <"
    assert len(row1) == 27
    row2 = "   s" + " " * 23
    # row3 (carry, westbound): cells left-to-right store reversed exec order
    # exec order westbound from col 25: `CORR` N + M `10` b
    # cols: 26 '<', 25 '`', 24..13 CORR digits reversed, 12 '`', 11 'N',
    #       10 '+', 9 'M', 8 '`', 7 '1', 6 '0', 5 '`', 4 'b', 3 'N'(passthru), 0 'v'
    row3 = list(" " * 27)
    row3[26] = "<"
    row3[25] = "`"
    for i, ch in enumerate(d_corr):
        row3[24 - i] = ch            # walk west reads d_corr in order
    row3[12] = "`"
    row3[11] = "N"
    row3[10] = "+"
    row3[9] = "M"
    row3[8] = "`"
    row3[7] = "1"
    row3[6] = "0"
    row3[5] = "`"
    row3[4] = "b"
    row3[3] = "N"
    row3[0] = "v"
    row4 = ">rNXWsM`" + d_step + "`+Mma  ^"
    assert len(row4) == 27, len(row4)
    return [row0, "".join(row1), row2, "".join(row3), row4]


def test_year():
    rows = year_rows()
    for r in rows:
        assert len(r) == 27
    # stream: mix of positive values and 27 zero markers
    stream, want = [], []
    year = 2000
    code = INIT
    bp = 10
    vals = [45, 100, 3000, 77]
    import random
    random.seed(3)
    nzero = 0
    while nzero < 27:
        if random.random() < 0.3:
            stream.append(0)
            want.append(code)
            code += STEP
            bp -= 1
            if bp == 0:
                code += CORR
                bp = 10
            nzero += 1
        else:
            v = random.choice(vals)
            stream.append(v)
            want.append(v)
    queues = {"in": list(stream), "out": []}
    res = run(rows, (0, 0), "E", queues,
              lambda x, y, k: "in" if k == "in" else "out", max_steps=500000)
    assert res["reason"] == "starved", (res["reason"], res["pos"], res["A"])
    assert queues["out"] == want, (queues["out"][:8], want[:8])
    # verify generated codes decode to the right strings
    outs = [v for v in want if v > 200]
    def unpack(v):
        bs = []
        while v:
            v, r = divmod(v, B2)
            bs.append(r)
        return bytes(bs)
    texts = [unpack(v).decode() for v in outs if v >= 128]
    exp = [f"; {2000 + i}: " for i in range(27)]
    gen = [t for t in texts if t.startswith("; ")]
    assert gen == exp, (gen[:5], exp[:5])
    print("YEAR OK:", len(want), "outputs, 27 boundaries verified")


if __name__ == "__main__":
    test_year()
