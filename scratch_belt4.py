import sys, os
sys.path.insert(0,'tools')
import littleman as lm

# Compact belt v4: belt pipes are the RIGHTMOST bottom-wall attaches so the belt
# escapes cleanly to a serpentine placed BESIDE the controller (shares its rows).
# Attach (bottom wall): input=2, output=5, beltret=10, beltfwd=14.
# Bands: input-read col<=5 ; belt-read col>=7 ; output-send col<=9 ; belt-send col>=10.
# RAW values + negative sentinel S=-2000000 ; LIMIT=1000001 ; drain test A=cell+LIMIT.

def build(N=100, cap=112, foldw=5):
    p=lm.Program(); put=p.put; text=p.text
    # ================= SEED =================  send 0 x100 then sentinel S
    put(1,1,'@'); text(2,1,'`100`'); put(7,1,'b'); put(8,1,'0'); put(13,1,'v')
    # seed loop rows2-3 (cols10-13): send0(col12>=10), dec, a-test ; exit WEST to col1
    put(13,2,'<'); put(12,2,'s'); put(11,2,'m'); put(10,2,'a')
    put(10,3,'>'); put(13,3,'^')          # loop-return (E then up), right of exit
    put(1,2,'v')                           # a BP==0 -> straight W -> col1 -> down
    put(1,3,'v')
    put(1,4,'>'); text(3,4,'`2000000`'); put(12,4,'N'); put(13,4,'s'); put(14,4,'v')
    # row5 = merge-into-MAIN + return bus (west into (2,5))
    put(2,5,'v'); put(14,5,'<'); put(16,5,'<')
    # ================= MAIN =================
    put(2,6,'r'); put(2,7,'M'); put(2,8,'r'); put(2,9,'b')
    put(2,10,'>'); put(11,10,'v')
    # ================= SEEK =================  belt read col11 ; resend col10
    put(11,11,'r'); put(11,12,'d')
    put(10,12,'s'); put(9,12,'m'); put(8,12,'^'); put(8,10,'>')
    # d BP==0 -> straight S -> (11,13) TGT
    # ================= TGT =================
    put(11,13,'W'); put(11,14,'X')
    # ---- READ path (X straight S): resend cell(>=10) then output cell(<=9) ----
    put(11,15,'W'); put(11,16,'s'); put(11,17,'<'); put(5,17,'s')
    put(4,17,'v'); put(4,19,'<')             # down, then west to collector row19
    # ---- WRITE path (X CW=west): down col3, read value(<=5), store(>=10) on row18 ----
    put(3,14,'v'); put(3,15,'r'); put(3,16,'v'); put(3,18,'>'); put(13,18,'s'); put(14,18,'v')
    put(14,19,'<')                            # down col14 then west on collector row19
    # ---- collector row19 -> col1 -> LIMIT load (B=LIMIT) ----
    put(1,19,'v'); put(1,20,'>'); text(4,20,'`1000001`'); put(13,20,'M'); put(14,20,'v')
    put(14,21,'<'); put(11,21,'v')            # feeder into drain loop col11
    # ---- DRAIN loop col11 rows22-25 : r; s; +(cell+LIMIT); X ----
    put(11,22,'r'); put(11,23,'s'); put(11,24,'+'); put(11,25,'X')
    put(10,25,'^'); put(10,21,'>')            # real(>0)->W-> loop-return up col10
    put(16,25,'^')                            # sentinel(<0)->E-> glide to bus col16 up
    # ================= ROOM + IO + BELT =================
    p.room(0,0,18,27); SR=26
    p.input_room(1, SR+5);  p.pipe([(2, SR+4), (2, SR+1)])
    p.output_room(4, SR+5); p.pipe([(5, SR+1), (5, SR+4)])
    # belt: forward col14 (rightmost) -> down -> right -> up right side -> serpentine
    _belt(p, put, SR, cap, foldw)
    return p

def _belt(p, put, SR, cap, foldw):
    fwd=SR+2                       # forward connector row (below controller)
    sx=20; w=foldw; bx1=sx+w-1
    nr=(cap+w-1)//w
    if nr%2==0: nr+=1              # odd -> serpentine ends on the RIGHT (next to relay)
    # forward: (14,SR+1) down -> right along fwd -> up col18 -> serpentine top-left
    wp=[(14,SR+1),(14,fwd),(18,fwd),(18,1),(sx,1)]
    y=1; gr=True
    for r in range(nr):
        wp.append((bx1 if gr else sx, y))
        if r<nr-1: wp.append((bx1 if gr else sx, y+1))
        y+=1; gr=not gr
    ey=wp[-1][1]                   # last serpentine row (on the right)
    wp.append((bx1+1, ey))         # step right into relay wall
    p.pipe(wp)
    rx=bx1+2
    p.room(rx, ey-2, 6, 6)         # proven 6x6 relay
    put(rx+1,ey,'>'); put(rx+2,ey,'@'); put(rx+3,ey,'r'); put(rx+4,ey,'v')
    put(rx+4,ey+1,'<'); put(rx+3,ey+1,'s'); put(rx+2,ey+1,'.'); put(rx+1,ey+1,'^')
    # return: exit relay WEST (backward nb = relay wall), down col19 (gap), west
    # below controller to col10, up to beltret attach (10,SR+1)
    ret=SR+3
    p.pipe([(rx-1,ey+1),(19,ey+1),(19,ret),(10,ret),(10,SR+1)])

if __name__=="__main__":
    p=build()
    print(p.render()); print("fp",p.footprint())
