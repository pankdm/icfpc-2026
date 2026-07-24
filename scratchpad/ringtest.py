import sys, os, json, subprocess, tempfile
sys.path.insert(0,'tools')
import littleman as lm

# Minimal recirculating ring: CTRL man loads N values from input, then both CTRL and
# RELAY men just r;s forever, circulating the ring. Measure throughput.
def build():
    p=lm.Program()
    # CTRL room outer (0,0) 6x6 interior cols1-4 rows1-4
    p.room(0,0,6,6)
    # RELAY room outer (10,0) 6x6 interior cols 11-14 rows1-4
    p.room(10,0,6,6)
    # I room feeding CTRL (top)
    p.input_room(1,-4)  # I at (2,-3); 3x3 rows -4..-2
    p.pipe([(2,-2),(2,-1)])  # I down into CTRL top wall (col2 row0 border)
    # pipeA: CTRL right (col5) -> RELAY left (col10). row2
    p.pipe([(6,2),(9,2)])
    # pipeB: RELAY bottom (row5) -> CTRL bottom. route under.
    p.pipe([(12,6),(12,8),(3,8),(3,6)])
    # ---- CTRL man ----
    # start @ (1,1). Read N (count) then load N vals into ring, then loop r;s.
    # Simplify: just read a fixed number via backpack countdown then infinite r;s.
    # program: read count -> b ; loop: r (from input) s (to ring pipeA) until BP done...
    # But we want to measure recirculation, so: load phase reads from I, circulate phase r from pipeB s to pipeA.
    # Hard to switch nearest pipe. Instead: measure pure relay throughput with preloaded seed.
    return p

# Too fiddly; instead directly measure a SINGLE tight relay loop throughput:
# One room, man does r;s in a tight cycle, with an input pipe and output pipe.
def build2():
    p=lm.Program()
    # room 6x6 interior cols1-4 rows1-4
    p.room(0,0,7,6)
    p.input_room(1,-4); p.pipe([(2,-2),(2,-1)])   # I -> top wall col2
    p.output_room(-4,1); p.pipe([(-1,2),(0,2)])    # left... O room left; pipe into CTRL left wall? O is incoming to O.
    # man: @ at (1,1) reads from input, sends to output, tight loop
    p.text(1,1,"@r",'E')   # (1,1)=@ (2,1)=r
    p.put(3,1,'s')
    p.put(4,1,'v')
    p.put(4,2,'<')
    p.put(1,2,'^')
    return p

p=build2()
print(p.render())
print("FP",p.footprint())
src=p.render()
open('scratchpad/rt.man','w').write(src)
