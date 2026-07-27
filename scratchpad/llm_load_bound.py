#!/usr/bin/env python3
"""Static bound on removable RAM traffic in the LLM controller flow.

Abstract-interprets every basic block of build_banked_dedup.build_flow()
(after the champion's alias_empty_gotos pass), tracking A, B, the sp/rp
scratch FIFO and versioned RAM slots, then classifies every scalar/cell
load as REDUNDANT / REGISTER-RESIDENT / HOISTABLE / IRREDUCIBLE.
"""
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "solutions", "little-little-man"))

import build_banked_dedup as dedup
import build_banked_boustro as bb

SEND = {"sc", "sp", "sd", "sa", "ss", "cc"}
RECV = {"rr", "rp", "cr", "ri"}
BIN = {"+", "-", "*", "%", "&", "|", "~", "{", "}"}

TOPN = [0]


def top(tag=""):
    TOPN[0] += 1
    return ("t", TOPN[0], tag)


class State:
    __slots__ = ("A", "B", "scratch", "sc_tx", "cc_tx", "ver", "cver",
                 "scalar_epoch", "cell_epoch")

    def __init__(self):
        self.A = top("A0")
        self.B = top("B0")
        self.scratch = []          # sp/rp FIFO
        self.sc_tx = []            # words pushed into the pending sc transaction
        self.cc_tx = []
        self.ver = {}              # scalar addr -> version
        self.cver = {}
        self.scalar_epoch = 0
        self.cell_epoch = 0

    def slot(self, addr):
        return ("r", addr, self.scalar_epoch, self.ver.get(addr, 0))

    def cslot(self, addr):
        return ("cell", addr, self.cell_epoch, self.cver.get(addr, 0))


def const_of(v):
    return v[1] if isinstance(v, tuple) and v[0] == "c" else None


def run_block(label, tokens, loads, stores, ram_touched):
    """Abstract-interpret one block; append load/store events."""
    st = State()
    seen_values = set()          # values materialised into a register in this block
    for i, tok in enumerate(tokens):
        if isinstance(tok, tuple):
            continue
        pre_A, pre_B = st.A, st.B
        if tok.isdigit():
            st.A = ("c", int(tok))
        elif tok == "M":
            st.B = st.A
        elif tok == "W":
            st.A, st.B = st.B, st.A
        elif tok == "N":
            a = const_of(st.A)
            st.A = ("c", -a) if a is not None else ("neg", st.A)
        elif tok in BIN:
            a, b = const_of(st.A), const_of(st.B)
            if tok == "+" and a is not None and b is not None:
                st.A = ("c", a + b)
            elif tok == "-" and a is not None and b is not None:
                st.A = ("c", a - b)
            else:
                st.A = ("op", tok, st.A, st.B)
        elif tok == "/":
            st.A, st.B = ("op", "/q", st.A, st.B), ("op", "/r", st.A, st.B)
        elif tok == "b":
            pass                                   # BP = A; A,B untouched
        elif tok in ("m", "]"):
            pass
        elif tok == "sp":
            st.scratch.append(st.A)
        elif tok == "rp":
            st.A = st.scratch.pop(0) if st.scratch else top("rp")
        elif tok == "ri":
            st.A = top("input")
        elif tok in ("sd", "sa", "ss"):
            pass                                   # display sends, no reg effect
        elif tok in ("sc", "cc"):
            tx = st.sc_tx if tok == "sc" else st.cc_tx
            tx.append((st.A, i, pre_A, pre_B))
            first = const_of(tx[0][0])
            if first == 1 and len(tx) == 3:        # write [1, addr, payload]
                addr = const_of(tx[1][0])
                payload = tx[2][0]
                stores.append(dict(block=label, idx=i, addr=addr,
                                   kind="sc" if tok == "sc" else "cc",
                                   payload=payload))
                if tok == "sc":
                    if addr is None:
                        st.scalar_epoch += 1
                        st.ver = {}
                    else:
                        st.ver[addr] = st.ver.get(addr, 0) + 1
                        ram_touched.setdefault(label, set()).add(("w", addr))
                else:
                    if addr is None:
                        st.cell_epoch += 1
                        st.cver = {}
                    else:
                        st.cver[addr] = st.cver.get(addr, 0) + 1
                tx.clear()
            elif first not in (0, 1):
                tx.clear()                          # unrecognised protocol word
        elif tok in ("rr", "cr"):
            tx = st.sc_tx if tok == "rr" else st.cc_tx
            addr = None
            start = i
            pre = (pre_A, pre_B)
            if len(tx) == 2 and const_of(tx[0][0]) == 0:
                addr = const_of(tx[1][0])
                start = tx[0][1]
                pre = (tx[0][2], tx[0][3])
            tx.clear()
            val = st.slot(addr) if tok == "rr" else st.cslot(addr)
            if addr is None:
                val = top("dynload")
            # --- classify -------------------------------------------------
            # registers as they were just before the transaction opened
            resident = val in pre
            repeat = val in seen_values
            loads.append(dict(block=label, idx=i, addr=addr, kind=tok,
                              value=val, resident=resident, repeat=repeat,
                              dynamic=addr is None))
            if addr is not None and tok == "rr":
                ram_touched.setdefault(label, set()).add(("r", addr))
            st.A = val
            seen_values.add(val)
        elif tok in (".", " ", "H", ">", "<", "^", "v", "V", "X", "d", "a", "x",
                     "Y", "q"):
            pass
        else:
            raise SystemExit("unhandled token %r in %s" % (tok, label))
        if tok not in ("rr", "cr"):
            for v in (st.A, st.B):
                if isinstance(v, tuple) and v[0] in ("r", "cell"):
                    seen_values.add(v)
    return st


def main():
    flow = bb.alias_empty_gotos(dedup.build_flow())
    blocks = flow.blocks

    succ = {}
    for label, toks in blocks.items():
        term = toks[-1] if toks and isinstance(toks[-1], tuple) else None
        succ[label] = tuple(dict.fromkeys(term[1:])) if term else ()
    preds = defaultdict(list)
    for label, ss in succ.items():
        for s in ss:
            preds[s].append(label)

    loads, stores, ram_touched = [], [], {}
    for label, toks in blocks.items():
        run_block(label, toks, loads, stores, ram_touched)

    # ---- available-loads dataflow (which scalar slots are already
    #      materialised on EVERY path reaching a block) ---------------------
    entry = next(iter(blocks))
    ALL = frozenset(range(0, 320))
    gen, kill, dyn_kill = {}, {}, {}
    for label, toks in blocks.items():
        g, k = set(), set()
        dynamic_store = False
        for ev in [e for e in loads if e["block"] == label] + \
                  [e for e in stores if e["block"] == label]:
            pass
        seq = sorted([("l", e["idx"], e) for e in loads if e["block"] == label] +
                     [("s", e["idx"], e) for e in stores if e["block"] == label],
                     key=lambda t: t[1])
        for kind, _, ev in seq:
            if ev.get("kind") not in ("rr", "sc"):
                continue
            a = ev["addr"]
            if kind == "l":
                if a is None:
                    continue
                g.add(a)
            else:
                if a is None:
                    dynamic_store = True
                    g.clear()
                    k = set(ALL)
                else:
                    g.add(a)        # a store also leaves the value known
                    k.discard(a)
        gen[label], kill[label], dyn_kill[label] = g, k, dynamic_store

    IN = {label: (set() if label == entry else set(ALL)) for label in blocks}
    OUT = {}
    for _ in range(200):
        changed = False
        for label in blocks:
            if label == entry:
                inset = set()
            else:
                ps = preds.get(label, [])
                inset = set(ALL)
                for p in ps:
                    inset &= OUT.get(p, set(ALL))
                if not ps:
                    inset = set()
            new_out = (inset - kill[label]) | gen[label]
            if OUT.get(label) != new_out or IN[label] != inset:
                changed = True
                IN[label], OUT[label] = inset, new_out
        if not changed:
            break

    # per-load cross-block availability: replay the block's kill set
    for label in blocks:
        avail = set(IN[label])
        seq = sorted([("l", e["idx"], e) for e in loads if e["block"] == label] +
                     [("s", e["idx"], e) for e in stores if e["block"] == label],
                     key=lambda t: t[1])
        for kind, _, ev in seq:
            if ev.get("kind") not in ("rr", "sc"):
                continue
            a = ev["addr"]
            if kind == "l":
                ev["cross_avail"] = (a is not None and a in avail)
                if a is not None:
                    avail.add(a)
            else:
                if a is None:
                    avail = set()
                else:
                    avail.add(a)

    # ---- loop membership (SCCs with >1 block or self loops) --------------
    index, lowlink, onstack, stack, sccs = {}, {}, set(), [], []
    counter = [0]

    def strongconnect(v):
        work = [(v, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = lowlink[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                onstack.add(node)
            recurse = False
            for i in range(pi, len(succ[node])):
                w = succ[node][i]
                if w not in index:
                    work[-1] = (node, i + 1)
                    work.append((w, 0))
                    recurse = True
                    break
                elif w in onstack:
                    lowlink[node] = min(lowlink[node], index[w])
            if recurse:
                continue
            if lowlink[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                sccs.append(comp)
            work.pop()
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])

    for v in blocks:
        if v not in index:
            strongconnect(v)

    loop_of = {}
    for comp in sccs:
        cyclic = len(comp) > 1 or any(c in succ[comp[0]] for c in comp)
        if cyclic:
            for b in comp:
                loop_of[b] = frozenset(comp)

    # a load is loop-invariant if no block in its loop stores to that addr
    for ev in loads:
        ev["loop_inv"] = False
        comp = loop_of.get(ev["block"])
        if comp and ev["addr"] is not None and ev["kind"] == "rr":
            written = any(("w", ev["addr"]) in ram_touched.get(b, ())
                          for b in comp)
            dynamic = any(s["block"] in comp and s["addr"] is None and
                          s["kind"] == "sc" for s in stores)
            ev["loop_inv"] = not written and not dynamic

    # ---- classify --------------------------------------------------------
    cats = defaultdict(list)
    for ev in loads:
        if ev["dynamic"]:
            c = "IRREDUCIBLE(dynamic-addr)"
        elif ev["resident"]:
            c = "REGISTER_RESIDENT"
        elif ev["repeat"]:
            c = "REDUNDANT"
        elif ev.get("cross_avail"):
            c = "HOISTABLE(cross-block)"
        elif ev["loop_inv"]:
            c = "HOISTABLE(loop-invariant)"
        else:
            c = "IRREDUCIBLE"
        ev["cat"] = c
        cats[c].append(ev)

    print("=" * 72)
    print("blocks", len(blocks), " loads", len(loads), " stores", len(stores))
    for c in sorted(cats, key=lambda k: -len(cats[k])):
        print("  %-28s %4d" % (c, len(cats[c])))
    scalar = [e for e in loads if e["kind"] == "rr"]
    cell = [e for e in loads if e["kind"] == "cr"]
    print("  scalar rr", len(scalar), " cell cr", len(cell))

    irre = [e for e in loads if e["cat"].startswith("IRREDUCIBLE")]
    print("\nachievable L (irreducible only) =", len(irre))
    print("  of which scalar:", sum(1 for e in irre if e["kind"] == "rr"))

    # ---- store analysis (stores cost 2 rows each) ------------------------
    dead, redundant_st = 0, 0
    per_block_stores = defaultdict(list)
    for s in stores:
        per_block_stores[s["block"]].append(s)
    print("\nstores: total", len(stores),
          " scalar", sum(1 for s in stores if s["kind"] == "sc"),
          " cell", sum(1 for s in stores if s["kind"] == "cc"))

    # ---- blocks that exist only to serve a load --------------------------
    load_only = []
    for label, toks in blocks.items():
        ops = [t for t in toks if not isinstance(t, tuple)]
        blk_loads = [e for e in loads if e["block"] == label]
        blk_stores = [e for e in stores if e["block"] == label]
        cost = len(blk_loads) + 2 * len(blk_stores)
        if blk_loads and len(ops) <= 3 + 5 * len(blk_loads) and not blk_stores:
            load_only.append(label)
    print("\nblocks whose ops are (nearly) nothing but loads:", len(load_only))

    # rows accounting
    L = len(scalar)
    S = sum(1 for s in stores if s["kind"] == "sc")
    print("\nrow model: blocks + loads + 2*stores = %d + %d + 2*%d = %d"
          % (len(blocks), L, S, len(blocks) + L + 2 * S))

    # projected
    L2 = len(irre)
    print("projected rows with only irreducible loads (stores unchanged): %d"
          % (len(blocks) + L2 + 2 * S))

    # top addresses
    from collections import Counter
    print("\nload addresses (scalar):",
          Counter(e["addr"] for e in scalar).most_common(14))
    print("store addresses (scalar):",
          Counter(s["addr"] for s in stores if s["kind"] == "sc").most_common(14))
    print("\nper-category examples:")
    for c in cats:
        ex = cats[c][:4]
        print(" ", c, [(e["block"], e["addr"]) for e in ex])

    # loads per block histogram
    per = Counter(e["block"] for e in loads)
    print("\nblocks with loads:", len(per), "of", len(blocks))
    print("max loads in a block:", per.most_common(5))
    return loads, stores, blocks


if __name__ == "__main__":
    main()
