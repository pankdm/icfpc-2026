import sys; sys.path.insert(0,'tools'); import littleman as lm

def build_echo(pump_w=10, right_col=18):
    p=lm.Program(); P=p.put
    x,y,w=10,10,pump_w
    p.room(x,y,w,4)                      # forwarder, interior rows y+1,y+2
    r1,r2=y+1,y+2
    P(x+1,r1,'>');P(x+2,r1,'@');P(x+3,r1,'R');P(x+4,r1,'s')
    P(right_col,r1,'v');P(right_col,r2,'<');P(x+1,r2,'^')
    p.input_room(x+1,y-4)               # I room rows y-4..y-2, I at (x+2,y-3)
    p.pipe([(x+2,y-2+1),(x+2,y-1)])     # gap cells into forwarder top border row y
    p.output_room(x+w+1,y)              # O room cols x+w+1.. , O at (x+w+2,y+1)=r1
    p.pipe([(x+w,r1),(x+w,r1)] ) if False else p.pipe([(x+w,r1)])  # placeholder
    return p

# simpler: just render and inspect
try:
    p=build_echo(); print(p.render()); print("FP",p.footprint())
except Exception as e:
    print("ERR",e)
