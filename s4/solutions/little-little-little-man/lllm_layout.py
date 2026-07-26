"""Op-stream -> .man placer for the LLLM interpreter (two regions)."""
import sys
import os
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'..','..','tools'))
sys.path.insert(0,HERE)
import littleman as lm
import driver16

INP=22; OUTC=25
STATE_BAND=(40,70); SOUT_C=53; SIN_C=55
CELLS_BAND=(82,102); COUT_C=90; CIN_C=92
CMD_C=118
TOP=3; GATE_W=CMD_C+10

DESP={}
def despine(k):
    if 0<=k<=9: return [str(k)]
    if k in DESP: return DESP[k]
    for a in range(2,10):
        if k%a==0 and 2<=k//a<=9: DESP[k]=[str(k//a),'M',str(a),'*']; return DESP[k]
    raise ValueError(f"despine {k} not a*b")

def has_state(body):   # direct-level state r/s ?
    for op in body:
        if op in ('r','s'): return True
    return False
def has_cells(body):
    for op in body:
        if op in ('rc','sc'): return True
    return False

class Lay:
    def __init__(self):
        self.p=lm.Program(); self.region='state'
        L,_=STATE_BAND; self.x=L; self.y=TOP; self.dir=1; self.maxy=TOP
        self.sdepth=0; self.cdepth=0; self.use_display=False
    def band(self): return STATE_BAND if self.region=='state' else CELLS_BAND
    def railcol(self):
        if self.region=='state': return 8+2*self.sdepth
        else: return 72+2*self.cdepth      # gap between bands, west of cells band
    def put(self,x,y,ch):
        assert self.p.get(x,y)==' ', f"overlap {(x,y)} {self.p.get(x,y)!r} vs {ch!r}"
        self.p.put(x,y,ch)
        if y>self.maxy: self.maxy=y
    def start_row(self,y):
        BL,_=self.band(); self.y=y; self.x=BL; self.dir=1
        if self.p.get(BL-1,y)==' ': self.put(BL-1,y,'>')
    def wrap(self):
        BL,BR=self.band()
        if self.dir==1:
            self.put(self.x,self.y,'v'); self.put(self.x,self.y+1,'<'); self.y+=1; self.x-=1; self.dir=-1
        else:
            self.put(BL-1,self.y,'v'); self.put(BL-1,self.y+1,'>'); self.y+=1; self.x=BL; self.dir=1
    def place(self,ch):
        BL,BR=self.band()
        if self.dir==1 and self.x>BR: self.wrap()
        elif self.dir==-1 and self.x<BL: self.wrap()
        self.put(self.x,self.y,ch); self.x+=self.dir
    def K(self,k):
        for ch in despine(k): self.place(ch)
    def newline(self):
        BL,_=self.band(); self.put(self.x,self.y,'v'); r1=self.y+1
        if self.x>BL-1:
            self.put(self.x,r1,'<'); self.put(BL-1,r1,'v'); self.put(BL-1,r1+1,'>'); self.y=r1+1
        elif self.x<BL-1:
            self.put(self.x,r1,'>'); self.put(BL-1,r1,'v'); self.put(BL-1,r1+1,'>'); self.y=r1+1
        else:
            self.put(BL-1,r1,'>'); self.y=r1
        self.x=BL; self.dir=1
    def excursion(self,col,opch):
        BL,_=self.band(); x0=self.x; y0=self.y; self.put(x0,y0,'v'); y1=y0+1
        if col<x0:   # WEST
            self.put(x0,y1,'<'); self.put(col,y1,opch); self.put(col-1,y1,'v'); self.put(col-1,y1+1,'>')
            self.put(BL-1,y1+1,'>'); self.start_row(y1+1)
        else:        # EAST
            self.put(x0,y1,'>'); self.put(col,y1,opch); self.put(col+1,y1,'v'); self.put(col+1,y1+1,'<')
            self.put(BL-1,y1+1,'v'); self.put(BL-1,y1+2,'>'); self.start_row(y1+2)
    def switch_to(self,region):
        if self.region==region: return
        newBL=(STATE_BAND if region=='state' else CELLS_BAND)[0]
        self.put(self.x,self.y,'v'); r1=self.y+1
        if self.x>newBL-1: self.put(self.x,r1,'<')
        elif self.x<newBL-1: self.put(self.x,r1,'>')
        self.put(newBL-1,r1,'v'); self.put(newBL-1,r1+1,'>')
        self.region=region; self.x=newBL; self.y=r1+1; self.dir=1
    # --- ops ---
    def belt_read(self,belt):   # belt: 'state'/'cells'
        if self.region==belt: self.place('r')
        else: self.excursion(SIN_C if belt=='state' else CIN_C,'r')
    def belt_write(self,belt):
        if self.region==belt: self.place('s')
        else: self.excursion(SOUT_C if belt=='state' else COUT_C,'s')
    def _rail_ft(self,dcol,dy,head_y,RAIL):
        BL,_=self.band()
        self.put(RAIL,dy,'^'); self.put(RAIL,head_y,'>')
        self.put(dcol,dy+1,'<'); self.put(BL-1,dy+1,'v'); self.put(BL-1,dy+2,'>')
        self.x=BL; self.y=dy+2; self.dir=1
    def _depth_inc(self):
        if self.region=='state': self.sdepth+=1
        else: self.cdepth+=1
    def _depth_dec(self):
        if self.region=='state': self.sdepth-=1
        else: self.cdepth-=1
    def loop_bp(self,body):
        self.place('b'); RAIL=self.railcol(); self._depth_inc()
        self.newline(); head_y=self.y; self.emit(body)
        self.newline(); self.place('m')
        dcol=self.x; self.put(dcol,self.y,'v'); dy=self.y+1; self.put(dcol,dy,'d')
        self._rail_ft(dcol,dy,head_y,RAIL); self._depth_dec()
    def loop_x(self,body):
        RAIL=self.railcol(); self._depth_inc()
        self.newline(); head_y=self.y; self.emit(body)
        self.newline()
        dcol=self.x; self.put(dcol,self.y,'v'); dy=self.y+1; self.put(dcol,dy,'X')
        self._rail_ft(dcol,dy,head_y,RAIL); self._depth_dec()
    def forever(self,body):
        RAIL=self.railcol(); self._depth_inc()
        self.newline(); head_y=self.y; self.emit(body)
        self.newline()
        dcol=self.x; self.put(dcol,self.y,'v'); dy=self.y+1
        self.put(dcol,dy,'<'); self.put(RAIL,dy,'^'); self.put(RAIL,head_y,'>')
        self._depth_dec()
    def emit_loop(self,tag,body):
        want='cells' if (has_cells(body) and not has_state(body)) else 'state'
        prev=self.region
        if want!=self.region: self.switch_to(want)
        if tag=='BPLOOP': self.loop_bp(body)
        elif tag=='LOOPX': self.loop_x(body)
        elif tag=='FOREVER': self.forever(body)
        if prev!=self.region: self.switch_to(prev)
    def emit(self,ops):
        for op in ops:
            if isinstance(op,tuple):
                if op[0]=='#': self.K(op[1])
                elif op[0] in ('BPLOOP','LOOPX','FOREVER'): self.emit_loop(op[0],op[1])
                else: raise ValueError(op[0])
            elif op=='r': self.belt_read('state')
            elif op=='s': self.belt_write('state')
            elif op=='rc': self.belt_read('cells')
            elif op=='sc': self.belt_write('cells')
            elif op=='ri': self.excursion(INP,'r')
            elif op=='out': self.excursion(OUTC,'s')
            elif op=='cmd': self.excursion(CMD_C,'s')
            elif op in ('M','W','b','m','+','-','*','/','{','}','&','|','~','N') or (isinstance(op,str) and op.isdigit()):
                self.place(op)
            else: raise ValueError(repr(op))
    def finish_H(self): self.put(self.x,self.y,'H')
    def build_belt(self, out_col, in_col, L, rw=50):
        # straight vertical belt (cap ~2L). belt-out down out_col, belt-in up in_col.
        # rw>0: BATCHED relay (r s r s ..., ~1val/2t, high throughput, wide=more latency).
        # rw==0: TIGHT single relay (low latency, ~1val/7t) — best for latency-bound state belt.
        p=self.p; SOUTH=self.SOUTH; ybot=SOUTH+L
        p.pipe([(out_col,SOUTH),(out_col,ybot-1)])          # belt-out -> relay top col out_col
        p.pipe([(in_col,ybot-1),(in_col,SOUTH)])            # belt-in up -> gate col in_col
        if rw==0:
            j0=out_col-2; endc=in_col+2; p.room(j0-1,ybot,endc-j0+3,4); ry=ybot+1
            for c,g in [(j0,'@'),(j0+1,'>'),(out_col,'r'),(in_col,'s'),(endc,'v')]: p.put(c,ry,g)
            p.put(endc,ry+1,'<'); p.put(j0+1,ry+1,'^'); return
        rr=out_col-3; rl=max(2,rr-rw)                       # rsrs batch WEST of belt cols
        p.room(rl-1,ybot,(in_col+2)-(rl-1)+1,4)             # relay room spans rl-1..in_col+2
        r0=ybot+1; r1=ybot+2
        p.put(rl,r0,'@'); p.put(rl+1,r0,'>')                # spawn -> junction '>'
        c=rl+2
        while c+1<=rr: p.put(c,r0,'r'); p.put(c+1,r0,'s'); c+=2
        p.put(rr+1,r0,'v'); p.put(rr+1,r1,'<')
        c=rr
        while c-1>=rl+2: p.put(c,r1,'r'); p.put(c-1,r1,'s'); c-=2
        p.put(rl+1,r1,'^')                                  # up into '>' junction -> loops
    def build_rooms(self):
        SOUTH=self.maxy+3; self.SOUTH=SOUTH
        self.p.room(0,0,GATE_W,SOUTH)
        self.build_belt(SOUT_C, SIN_C, 18, rw=8)     # state
        self.build_belt(COUT_C, CIN_C, 400, rw=120)   # cells
        self.p.input_room(INP-1,SOUTH+3); self.p.pipe([(INP,SOUTH+2),(INP,SOUTH)])
        if self.use_display:
            dvx=CMD_C+4; dvy=SOUTH+5
            info=driver16.build_driver(self.p, dvx, dvy, None, 16, 16)
            rENTRY=info['rENTRY']; DR=info['DR']
            self.p.pipe([(CMD_C,SOUTH),(CMD_C,rENTRY),(DR.x0-1,rENTRY)])  # gate CMD -> driver entry
        else:
            self.p.output_room(OUTC-1,SOUTH+15); self.p.pipe([(OUTC,SOUTH),(OUTC,SOUTH+14)])
    def save(self,path): self.build_rooms(); self.p.save(path); return path
    def spawn(self):
        L,_=STATE_BAND; self.put(L-1,TOP,'@'); self.x=L; self.y=TOP; self.dir=1
