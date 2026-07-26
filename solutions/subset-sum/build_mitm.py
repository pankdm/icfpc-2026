#!/usr/bin/env python3
"""Meet-in-the-middle subset-sum controller on stateflow/flowgrid.

Semantic mirror: mitm_grid_model.py (fuzzed vs brute force; keep in sync!).
Scalar map and block structure are copied from that file's docstring.

Hardware: compact stateflow floor, no display, output room ("so" port),
scalar split RAM 128/4 (vars + NIB banks + V), cell split RAM 256/8
(hash table only).  nb=7: B half = last 7 indices (128 masks, <=50% load),
A half = remaining n-7 indices enumerated in descending rank order.

Register discipline (A=main, B=off; M: B:=A; W: swap; binop: A = A op B):
  - const_ops(n>=10) contains M -> clobbers B.  For "A op bigconst" use
    const-first (const, M, load x, op) or scratch staging (a_op below).
  - Flow.load() always preserves B; store() leaves A=value.
  - inp()/out() preserve B.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import stateflow

# Scalar addresses (see mitm_grid_model.py)
H, E, NEED, TB, M2, MHI, NEED1, M, S, T = range(10)
TAG, N, NA, I, J, K, FULL, TMP = range(10, 18)
BB, VB, WID, BANKI, BIT, SUM1, RMASK, M2S, MHIS, ADDR = range(18, 28)
BANKS = [(28, 0, 4), (44, 4, 3), (52, 7, 4), (68, 11, 4), (84, 15, 4), (100, 19, 1)]
VBASE = 102
SCALAR_SIZE = 128
TSIZE = 256


class Flow(stateflow.Flow):
    def a_op(self, op, c):
        """A := A <op> c with A already in hand (B is clobbered)."""
        if c < 10:
            if op in ("+", "&", "|"):
                return self.e("M").const(c).e(op)
            return self.e("M").const(c).e("W", op)
        return self.e("sp").const(c).e("M", "rp", op)


def build_flow(dump_after=None):
    """dump_after: None | 'dp' (scalar 28..121 after bank DP) | 'insert'
    (cell 0..255 after the insert phase) — debug builds halt after dumping."""
    f = Flow()

    # ---- round header: read n, bump tag, read values into V[n-1-i] ----
    f.at("ROUND").inp().store(N)
    f.addc(TAG, 1, TAG)
    f.load(TAG).a_op("{", 32).store(TB)
    f.subc(N, 7, NA)
    f.const(0).store(I)
    f.go("READV")
    f.at("READV").bin("-", I, N).br("READT", "READT", "RV_BODY")
    # scalar[101 + N - I] := next value  (V[j] = vals[n-1-j])
    f.at("RV_BODY").bin("-", N, I).a_op("+", 101).store(ADDR)
    f.e("M").inp().storev()
    f.addc(I, 1, I).go("READV")
    f.at("READT").inp().store(T)
    f.const(0).store(BANKI)
    f.go("DUMPS" if dump_after == "input" else "BANKSEQ")

    # ---- NIB bank DP: 6 banks, scalar[base+m] = scalar[base+m-bit] + V ----
    after_dp = "DUMPS" if dump_after in ("dp", "input") else "INSERT0"
    f.at("BANKSEQ").load(BANKI).br("BQ1", "BSET0", "BQ1")
    for k in range(1, 6):
        f.at(f"BQ{k}").subc(BANKI, k).br(
            f"BQ{k + 1}" if k < 5 else after_dp,
            f"BSET{k}",
            f"BQ{k + 1}" if k < 5 else after_dp,
        )
    if dump_after in ("dp", "input"):
        f.at("DUMPS").const(28).store(I).go("DUMPL")
        f.at("DUMPL").const(122).e("M").load(I).e("-")
        f.br("DUMPB", "DUMPH", "DUMPB")
        f.at("DUMPB").load(I).loadv().out().addc(I, 1, I).go("DUMPL")
        f.at("DUMPH").e("H")
    for k, (base, vbase, wid) in enumerate(BANKS):
        f.at(f"BSET{k}")
        f.const(base).store(BB)
        f.const(VBASE + vbase).store(VB)   # absolute V address of the bank's lowest bit
        f.const(wid).store(WID)
        f.const(0).store(base)          # zero the bank head every round
        f.addc(BANKI, 1, BANKI)
        f.const(0).store(J)
        f.go("DPJ")
    f.at("DPJ").bin("-", J, WID).br("BANKSEQ", "BANKSEQ", "DPJ_BODY")
    f.at("DPJ_BODY")
    f.load(J).e("M").const(1).e("{").store(BIT).store(M)  # BIT:=1<<J; M:=BIT
    f.go("DPM")
    f.at("DPM").load(BIT).e("M", "+", "M").load(M).e("-")  # M - 2*BIT
    f.br("DPJ_NEXT", "DPJ_NEXT", "DPM_BODY")
    f.at("DPM_BODY")
    f.bin("-", M, BIT).e("M").load(BB).e("+").loadv().store(TMP)
    f.bin("+", VB, J).loadv().e("M").load(TMP).e("+").store(TMP)
    f.bin("+", BB, M).e("M").load(TMP).storev()
    f.addc(M, 1, M).go("DPM")
    f.at("DPJ_NEXT").addc(J, 1, J).go("DPJ")

    # ---- INSERT: rmask ascending 0..127, skip s>t, open addressing ----
    after_ins = "DUMPT" if dump_after == "insert" else "ASETUP"
    f.at("INSERT0").const(0).store(M).go("INS")
    f.at("INS").const(128).e("M").load(M).e("-")  # M - 128
    f.br(after_ins, after_ins, "INS_BODY")
    if dump_after == "insert":
        f.at("DUMPT").const(0).store(I).go("DTL")
        f.at("DTL").const(256).e("M").load(I).e("-")
        f.br("DTB", "DTH", "DTB")
        f.at("DTB").load(I).cell_loadv().out().addc(I, 1, I).go("DTL")
        f.at("DTH").e("H")
    f.at("INS_BODY")
    f.const(15).e("M").load(M).e("&").a_op("+", BANKS[0][0]).loadv().store(TMP)
    f.load(M).a_op("}", 4).a_op("+", BANKS[1][0]).loadv()
    f.e("M").load(TMP).e("+").store(S)
    f.e("M").load(T).e("-")               # T - S: negative -> skip
    f.br("INS_PACK", "INS_PACK", "INS_NEXT")
    f.at("INS_PACK")
    f.load(S).a_op("{", 7).e("M").load(TB).e("+").e("M").load(M).e("+").store(TMP)
    f.const(255).e("M").load(S).e("&").store(H)
    f.go("IPROBE")
    f.at("IPROBE").load(H).cell_loadv().store(E)
    f.e("M").load(TB).e("-")              # TB - E: positive -> stale slot
    f.br("ISTORE", "IKEY", "IKEY")
    f.at("IKEY").bin("-", E, TB).a_op("}", 7)
    f.e("M").load(S).e("-")               # S - key: zero -> overwrite
    f.br("IPROBE_NEXT", "ISTORE", "IPROBE_NEXT")
    f.at("IPROBE_NEXT").load(H).e("M").const(1).e("+").a_op("&", 255).store(H)
    f.go("IPROBE")
    f.at("ISTORE").load(H).e("M").load(TMP).cell_storev().go("INS_NEXT")
    f.at("INS_NEXT").addc(M, 1, M).go("INS")

    # ---- A setup: M2S/MHIS from NA ----
    f.at("ASETUP").subc(NA, 4).br("AS_BIG", "AS_SMALL", "AS_SMALL")
    f.at("AS_SMALL")
    f.load(NA).e("M").const(1).e("{")     # 1 << NA
    f.e("M").const(1).e("W", "-").store(M2S)
    f.const(0).store(MHIS).go("AOUTER0")
    f.at("AS_BIG")
    f.const(15).store(M2S)
    f.subc(NA, 4).e("M").const(1).e("{")  # 1 << (NA-4)
    f.e("M").const(1).e("W", "-").store(MHIS)
    f.go("AOUTER0")
    f.at("AOUTER0").load(MHIS).store(MHI).go("AOUT")

    # ---- A enumeration: mhi desc / m2 desc, first hit wins ----
    f.at("AOUT")
    f.const(15).e("M").load(MHI).e("&").a_op("+", BANKS[3][0]).loadv().store(SUM1)
    f.load(MHI).a_op("}", 4).a_op("&", 15).a_op("+", BANKS[4][0]).loadv()
    f.e("M").load(SUM1).e("+").store(SUM1)
    f.load(MHI).a_op("}", 8).a_op("+", BANKS[5][0]).loadv()
    f.e("M").load(SUM1).e("+").store(SUM1)
    f.e("M").load(T).e("-").store(NEED1)  # T - SUM1
    f.br("AOUT_IN", "AOUT_IN", "AOUT_NEXT")
    f.at("AOUT_IN").load(M2S).store(M2).go("AIN")
    f.at("AIN")
    f.load(M2).a_op("+", BANKS[2][0]).loadv()
    f.e("M").load(NEED1).e("-").store(NEED)
    f.br("APROBE_PRE", "APROBE_PRE", "AIN_NEXT")
    f.at("APROBE_PRE").const(255).e("M").load(NEED).e("&").store(H).go("APROBE")
    f.at("APROBE").load(H).cell_loadv().store(E)
    f.e("M").load(TB).e("-")              # TB - E: positive -> stale -> miss
    f.br("AIN_NEXT", "AKEY", "AKEY")
    f.at("AKEY").bin("-", E, TB).a_op("}", 7)
    f.e("M").load(NEED).e("-")            # NEED - key
    f.br("APROBE_NEXT", "AHIT", "APROBE_NEXT")
    f.at("APROBE_NEXT").load(H).e("M").const(1).e("+").a_op("&", 255).store(H)
    f.go("APROBE")
    f.at("AIN_NEXT").subc(M2, 1, M2).br("AIN", "AIN", "AOUT_NEXT")
    f.at("AOUT_NEXT").subc(MHI, 1, MHI).br("AOUT", "AOUT", "NOSOL")
    f.at("NOSOL").const(0).out().go("ROUND")

    # ---- hit: FULL = MHI<<11 | M2<<7 | RMASK ----
    f.at("AHIT")
    f.load(NEED).a_op("{", 7).store(TMP)
    f.load(TMP).e("M").load(TB).e("+").e("M").load(E).e("-").store(RMASK)
    f.load(MHI).a_op("{", 11).store(TMP)
    f.load(M2).a_op("{", 7).e("M").load(TMP).e("+")
    f.e("M").load(RMASK).e("+").store(FULL)
    f.go("OUTK")

    # ---- output: k, then chosen values by ascending original index ----
    f.at("OUTK").const(0).store(K).subc(N, 1, J).go("KLOOP")
    f.at("KLOOP").load(J).e("M").load(FULL).e("}")
    f.e("M").const(1).e("&").br("KSET", "KNEXT", "KNEXT")
    f.at("KSET").addc(K, 1, K).go("KNEXT")
    f.at("KNEXT").subc(J, 1, J).br("KLOOP", "KLOOP", "KOUT")
    f.at("KOUT").load(K).out().subc(N, 1, J).go("ELOOP")
    f.at("ELOOP").load(J).e("M").load(FULL).e("}")
    f.e("M").const(1).e("&").br("EOUT", "ENEXT", "ENEXT")
    f.at("EOUT").load(J).a_op("+", VBASE).loadv().out().go("ENEXT")
    f.at("ENEXT").subc(J, 1, J).br("ELOOP", "ELOOP", "ROUND")
    return f


def build(dump_after=None, **kwargs):
    kwargs.setdefault("scalar_size", SCALAR_SIZE)
    kwargs.setdefault("scalar_belts", 4)
    kwargs.setdefault("cell_size", TSIZE)
    kwargs.setdefault("cell_belts", 8)
    kwargs.setdefault("compact", True)
    kwargs.setdefault("fast_cell_ram", True)
    kwargs.setdefault("fast_scalar_ram", True)
    kwargs.setdefault("boustrophedon", True)
    kwargs.setdefault("display", False)
    kwargs.setdefault("output_port", True)
    kwargs.setdefault("code_x", 70)
    return stateflow.build_program(build_flow(dump_after), **kwargs)


VARIANTS = {
    "mitm-b7.man": {},
}


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, kwargs in VARIANTS.items():
        if only and name != only:
            continue
        program = build(**kwargs)
        output = os.path.join(HERE, name)
        program.save(output)
        print("saved", output, "footprint", program.footprint())
