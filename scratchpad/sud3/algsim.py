"""Faithful register+FIFO simulator for developing the sudoku algorithm.
Program = list of (op, *args). Labels are ('L','name'). Branches jump by label.
Registers A,B,BP (python ints). FIFOs: MR (main ring), SR (scratch ring),
IN (input queue), OUT (output list). r/s block model: since a relay always
forwards, MR/SR behave as plain queues for value/order purposes.
Ops:
  ('c',n)  A=n (constant; represents digit or literal load)
  ('M')    B=A
  ('W')    swap A,B
  ('b')    BP=A
  ('m')    BP-=1
  ('+')('-')('*')('N')('&')('|')('{')('}')
  ('/')    A=A//B (floored), B=A%B ; if B==0: A=0,B=dividend
  ('%')    A = A mod B (sign of B); B==0 -> A=0
  ('sMR')('rMR')('sSR')('rSR')('rIN')('sOUT')
  ('jmp',lbl)
  ('brA',neg,zero,pos)   # like X
  ('brBP',pos,nonpos)    # like d
  ('halt')
"""
import collections

def run(prog, inputs, mr_init, maxsteps=200000, trace=False):
    A=B=BP=0
    MR=collections.deque(mr_init)
    SR=collections.deque()
    SR2=collections.deque()
    IN=collections.deque(inputs)
    OUT=[]
    labels={}
    for i,ins in enumerate(prog):
        if ins[0]=='L': labels[ins[1]]=i
    pc=0
    steps=0
    def mask64(x):
        x&=(1<<64)-1
        if x>=(1<<63): x-=(1<<64)
        return x
    while pc<len(prog):
        steps+=1
        if steps>maxsteps: raise RuntimeError("maxsteps")
        op=prog[pc]; k=op[0]
        if trace and k not in('L',):
            print(f"pc{pc} {op} | A={A} B={B} BP={BP} MR={list(MR)} SR={list(SR)} SR2={list(SR2)} OUT={OUT}")
        if k=='L': pc+=1; continue
        elif k=='c': A=op[1]
        elif k=='M': B=A
        elif k=='W': A,B=B,A
        elif k=='b': BP=A
        elif k=='m': BP-=1
        elif k=='+': A=mask64(A+B)
        elif k=='-': A=mask64(A-B)
        elif k=='*': A=mask64(A*B)
        elif k=='N': A=mask64(-A)
        elif k=='&': A=mask64(A&B)
        elif k=='|': A=mask64(A|B)
        elif k=='{': A=(A<<B) if 0<=B<=63 else 0; A=mask64(A)
        elif k=='}': A=(A>>B) if B>=0 else 0; A=mask64(A)
        elif k=='/':
            if B==0: dividend=A; A=0; B=dividend
            else:
                q=A//B; r=A-q*B; A=mask64(q); B=mask64(r)
        elif k=='%':
            if B==0: A=0
            else: A=mask64(A%B if B>0 else -((-A)%(-B)) if False else A - (A//B)*B)
        elif k=='sMR': MR.append(A)
        elif k=='rMR':
            if not MR: raise RuntimeError("rMR empty (block)")
            A=MR.popleft()
        elif k=='sSR': SR.append(A)
        elif k=='sSR2': SR2.append(A)
        elif k=='rSR2':
            if not SR2: raise RuntimeError('rSR2 empty')
            A=SR2.popleft()
        elif k=='rSR':
            if not SR: raise RuntimeError("rSR empty (block)")
            A=SR.popleft()
        elif k=='rIN':
            if not IN: return OUT,'input_exhausted',(A,B,BP),MR,SR,SR2
            A=IN.popleft()
        elif k=='sOUT': OUT.append(A)
        elif k=='jmp': pc=labels[op[1]]; continue
        elif k=='brA':
            pc=labels[op[1] if A<0 else op[2] if A==0 else op[3]]; continue
        elif k=='brBP':
            pc=labels[op[1] if BP>0 else op[2]]; continue
        elif k=='halt': return OUT,'halt',(A,B,BP),MR,SR,SR2
        else: raise RuntimeError("badop "+k)
        pc+=1
    return OUT,'end',(A,B,BP),MR,SR,SR2

if __name__=='__main__':
    print("sim module ok")
