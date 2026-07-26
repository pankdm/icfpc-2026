import os as _os; _REPO = _os.path.abspath(__file__).split('/scratchpad/')[0]
import sys
sys.path.insert(0, _REPO + '/tools')
import littleman as lm

# STACK-MAN (decstack coprocessor), isolated & input-fed.
# cmd: 0/1 = PUSH bit ; <0 = POP (emit top bit). stack in A (init 0).
#   push: newstack = bit + 2*stack   ([A=bit,B=stack] '+' '+')
#   pop:  bit=stack%2, stack=stack/2 (A=2,B=stack -> W -> A=stack,B=2 -> '/' -> A=q,B=rem)
# "1 0 1 -1 -1 -1" -> push1(1) push0(2) push1(5) pop(1) pop(0) pop(1) -> [1,0,1].

def build():
    p=lm.Program(); placed={}
    def C(x,y,ch):
        if (x,y) in placed and placed[(x,y)]!=ch: raise SystemExit(f"COL {(x,y)} {placed[(x,y)]!r} vs {ch!r}")
        placed[(x,y)]=ch; p.put(x,y,ch)
    def room(x,y,w,h,g="+-|"):
        p.room(x,y,w,h,g)
        for i in range(w):
            placed[(x+i,y)]=p.get(x+i,y); placed[(x+i,y+h-1)]=p.get(x+i,y+h-1)
        for j in range(h):
            placed[(x,y+j)]=p.get(x,y+j); placed[(x+w-1,y+j)]=p.get(x+w-1,y+j)

    room(0,0,16,16)
    p.man(1,1)
    C(2,1,'v')                 # merge -> down
    C(2,2,'M')                 # B:=stack
    C(2,3,'r')                 # A=cmd
    C(2,4,'X')                 # S: >0 push(W) ; ==0 push(S) ; <0 pop(E)
    # push
    C(1,4,'v'); C(1,5,'>')     # >0 -> (2,5)
    C(2,5,'v')                 # push merge ; A=bit,B=stack
    C(2,6,'+'); C(2,7,'+')     # A=bit+2*stack=newstack
    C(2,8,'v')                 # down to bottom merge row
    C(2,9,'v'); C(2,10,'v'); C(2,11,'v'); C(2,12,'v'); C(2,13,'>')
    # pop (X CCW leaves man heading E at (3,4); turn S first)
    C(3,4,'v')                 # turn S
    C(3,5,'2')                 # A=2, B=stack
    C(3,6,'W')                 # A=stack, B=2
    C(3,7,'/')                 # A=stack/2, B=bit
    C(3,8,'W')                 # A=bit, B=stack/2
    C(3,9,'s')                 # emit bit
    C(3,10,'W')                # A=stack/2=newstack
    C(3,11,'v'); C(3,12,'v'); C(3,13,'>')
    # loopback: row13 east -> up col7 -> row1 -> west to (2,1)
    C(7,13,'^'); C(7,1,'<')
    # I -> stack ; stack -> O
    p.input_room(-5,0); p.pipe([(-2,1),(-1,1)])
    p.output_room(-5,7); p.pipe([(-1,8),(-2,8)])
    return p

if __name__=='__main__':
    p=build(); p.save(_REPO + '/scratchpad/ss_stack.man'); print(p.render())
