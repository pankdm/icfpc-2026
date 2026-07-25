"""Two-man lanes-as-pipes model for TCP.
READER: r seq; forward seq to collector; r val; slot=seq&15; drop val into lane[slot].
COLLECTOR: owns waiting locally. recv seq; off=seq-waiting; if off>=16 -> emit -1 (final).
  else sweep: while lane[waiting&15] occupied: r val -> output; clear; waiting++.
Lanes modeled as 16 one-slot cells (a live packet at slot). Cross-man = seq pipe + 16 lanes.
This validates the ALGORITHM + q-gate + off-check split (timing is oracle-checked later).
"""
import json

def run_rounds(rounds):
    lanes=[None]*16       # reader writes, collector reads (one live value per slot)
    seqpipe=[]            # reader -> collector
    waiting=0
    out=[]
    halted=False
    per=[]
    for j,r in enumerate(rounds):
        if halted: per.append([]); continue
        vals=[int(x) for x in r['in']]
        seq,val=(vals[1],vals[2]) if j==0 else (vals[0],vals[1])
        base=len(out)
        # READER: forward seq, drop val into lane[slot]
        seqpipe.append(seq)
        slot=seq&15
        lanes[slot]=val      # (if already occupied it'd be the -1 case; collector catches via off)
        # COLLECTOR:
        s=seqpipe.pop(0)
        off=s-waiting
        if off>=16:
            out.append(-1); per.append(out[base:]); halted=True; continue
        while lanes[waiting&15] is not None:
            out.append(lanes[waiting&15])
            lanes[waiting&15]=None
            waiting+=1
        per.append(out[base:])
    return per

if __name__=='__main__':
    d=json.load(open('scratchpad/tcp_problem.json'))
    allok=True
    for i,c in enumerate(d['publicTestData']):
        got=run_rounds(c['rounds'])
        exp=[[int(x) for x in r['out']] for r in c['rounds']]
        ok=got==exp; allok&=ok
        print(f'case {i} {c["name"]:28s} {"OK" if ok else "FAIL"}')
        if not ok:
            for j in range(len(c['rounds'])):
                if got[j]!=exp[j]: print('  r',j,'in',c['rounds'][j]['in'],'exp',exp[j],'got',got[j])
    print('ALL OK' if allok else 'FAIL')
