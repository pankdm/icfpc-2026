#!/usr/bin/env python3
"""Iterative DFS (the exact state machine to compile to littleman) + cost measurement
for candidate value-storage schemes."""
import json, os

def load_cases(path):
    d = json.load(open(path)); ptd = d["publicTestData"]; cases = []
    for c in ptd:
        r = c["rounds"][0]; ints=[int(x) for x in r["in"]]; n=ints[0]
        cases.append((c["name"], ints[1:1+n], ints[1+n], [int(x) for x in r["out"]]))
    return cases

def solve_iter(values, target):
    n = len(values)
    INCLUDED, EXCLUDED = 1, 0
    decision = [0]*n
    d = 0; S = 0
    # todoTotal maintained incrementally = suf[d]
    suf = [0]*(n+1)
    for i in range(n-1,-1,-1): suf[i]=suf[i+1]+values[i]
    todoTotal = suf[0]
    steps=0; descends=0; backtracks=0
    # ring model: front=v_d. count forward-rotations.
    ring_rot=0
    mode="DESCEND"
    chosen=None
    while True:
        steps+=1
        if mode=="DESCEND":
            descends+=1
            if S==target:
                chosen=[i for i in range(d) if decision[i]==INCLUDED]
                break
            if d==n or S+todoTotal<target:
                mode="BACKTRACK"; continue
            v=values[d]           # from ring front (rotate fwd 1 to consume)
            ring_rot+=1
            todoTotal-=v          # move v_d todo->done
            if S+v<=target:
                decision[d]=INCLUDED; S+=v
            else:
                decision[d]=EXCLUDED
            d+=1
            mode="DESCEND"
        else: # BACKTRACK
            backtracks+=1
            if d==0:
                chosen=None; break
            d-=1
            v=values[d]           # need v_d: ring backward 1 = forward (n-1)
            ring_rot+=(n-1)
            if decision[d]==INCLUDED:
                S-=v
                decision[d]=EXCLUDED
                d+=1
                mode="DESCEND"
            else:
                todoTotal+=v       # move back to todo
                mode="BACKTRACK"
    return chosen, dict(steps=steps,descends=descends,backtracks=backtracks,ring_rot=ring_rot)

def main():
    here=os.path.dirname(os.path.abspath(__file__))
    cases=load_cases(os.path.join(here,"..","..","scratchpad","ss_problem.json"))
    allok=True
    for name,vals,tgt,exp in cases:
        chosen,st=solve_iter(vals,tgt)
        if chosen is None: got=[0]
        else: got=[len(chosen)]+[vals[i] for i in chosen]
        ok=got==exp; allok&=ok
        print(f"[{'OK' if ok else 'FAIL'}] {name:30s} n={len(vals):2d} steps={st['steps']:7d} "
              f"desc={st['descends']:7d} back={st['backtracks']:7d} ring_rot={st['ring_rot']:8d}")
        if not ok: print("     exp",exp,"got",got)
    print("ALLOK" if allok else "FAIL")

if __name__=="__main__": main()
