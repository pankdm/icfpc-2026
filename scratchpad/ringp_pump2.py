import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'solutions/reverse-a-list')
import littleman as lm, dsl

def build(pump_rc):
    RB=5; EO=RB+1
    p=lm.Program(); BOTROW=EO+6; HT=BOTROW+1
    p.room(10,0,15,HT+1)
    Orow=EO+2; P=p.put
    P(12,1,'@');P(14,1,'>');P(17,1,'r');P(18,1,'M');P(19,1,'b');P(20,1,'v');P(20,3,'<');P(15,3,'^')
    P(15,2,'>');P(17,2,'r');P(19,2,'v');P(19,RB,'<');P(17,RB,'s');P(16,RB,'m');P(15,RB,'d')
    P(11,RB,'v');P(11,EO,'>');P(12,EO,'W');P(13,EO,'X');P(14,EO,'^')
    dr=EO+5
    P(13,dr,'>');P(14,dr,'b');P(15,dr,'M');P(16,dr,'1');P(17,dr,'W');P(18,dr,'-');P(19,dr,'M')
    P(20,dr,'^');P(20,EO+1,'<')
    P(11,EO+1,'v');P(11,EO+2,'r');P(11,EO+3,'m');P(11,EO+4,'a')
    P(12,EO+4,'>');P(17,EO+4,'s');P(19,EO+4,'^');P(19,EO+1,'<')
    P(11,EO+6,'>');P(23,EO+6,'^');P(23,Orow,'s');P(23,RB-1,'<');P(11,RB-1,'v')
    p.input_room(25,4); p.pipe([(26,3),(26,1),(25,1)])
    p.output_room(25,Orow+3); p.pipe([(25,Orow),(26,Orow),(26,Orow+2)])
    py=HT+3
    p.room(10,py,10,4)                       # pump room UNCHANGED w=10
    p.pipe([(17,y) for y in range(HT+1,py)]) # FEED
    # tiny pump: only change right_col
    r1,r2=py+1,py+2
    P(11,r1,'>');P(12,r1,'@');P(13,r1,'R');P(14,r1,'s')
    P(pump_rc,r1,'v');P(pump_rc,r2,'<');P(11,r2,'^')
    # RETURN folded for capacity (>=16): route left margin
    retcol=6
    ret=[(9,py+2),(retcol,py+2),(retcol,Orow),(9,Orow)]
    p.pipe(ret)
    return p

for rc in [18,16,15]:
    try:
        p=build(rc); g=p.grade('reverse-a-list')
        loop=2*(rc-11)+2
        print(f"rc={rc} pumploop~{loop}: FP={p.footprint()} pass={g.get('passed')}/{g.get('total')} avgT={g.get('avgTicks')} score={g.get('score')}")
    except Exception as e:
        print("rc",rc,"ERR",e)
