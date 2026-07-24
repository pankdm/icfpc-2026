const {boot,trace}=require('./lab.js');
const {grid,rect,put,toRows}=require('./build.js');

// Scenario 2: head-on swap. B parks on r facing W; A approaches from west facing E.
// pipe length L controls when B unblocks (blocks L-1 ticks after landing on r).
function buildS2(L){
  const iW=9,iH=5;
  const mainLeft=3+L;                 // main room left border col
  const W=mainLeft+iW+2, H=iH+2;
  const g=grid(W,H);
  rect(g,mainLeft,0,mainLeft+iW+1,iH+1);   // main room
  rect(g,0,1,2,3);                         // I-room
  put(g,1,2,'I');
  for(let c=3;c<mainLeft;c++) put(g,c,2,'>'); // pipe (empty) length L
  const X=(ix)=>mainLeft+ix;               // interior col from ix(1..iW)
  // row1
  put(g,X(1),1,'>'); put(g,X(5),1,'r'); put(g,X(9),1,'<');
  // row2
  put(g,X(5),2,'>'); put(g,X(9),2,'^');
  // row3
  put(g,X(1),3,'@'); put(g,X(5),3,'Y');
  // row4
  put(g,X(1),4,'^'); put(g,X(5),4,'<');
  return toRows(g);
}
(async()=>{const w=await boot();
  for(const L of [2,3,4,5,6,7]){
    await trace(w,'S2 head-on swap L='+L,buildS2(L),{input:'7',steps:22,showLoad:(L===2)});
  }
  process.exit(0);
})();
