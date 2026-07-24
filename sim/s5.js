const {boot,trace}=require('./lab.js');
const {grid,rect,put,toRows}=require('./build.js');

// (a) two blocked men adjacent: both park on their own r (shared empty input queue).
function buildTwoBlocked(){
  const L=3, iW=6, iH=4, mainLeft=3+L;
  const g=grid(mainLeft+iW+2,iH+2);
  rect(g,mainLeft,0,mainLeft+iW+1,iH+1);
  rect(g,0,1,2,3); put(g,1,2,'I');
  for(let c=3;c<mainLeft;c++) put(g,c,2,'>');
  const X=ix=>mainLeft+ix;
  put(g,X(4),1,'r'); put(g,X(5),1,'r');   // r2 (west), r1 (east) adjacent
  put(g,X(4),4,'^');                       // original: W->N up col4
  put(g,X(1),3,'@'); put(g,X(5),3,'Y');
  put(g,X(5),4,'<');                       // original turns W after fork(S)
  return toRows(g);
}
(async()=>{const w=await boot();
  await trace(w,'S5a two blocked men adjacent (empty input)',buildTwoBlocked(),{input:'',steps:14});
  // (b) can a man traverse a pipe? man walks toward the pipe-entry border cell.
  await trace(w,'S5b man walks into pipe-border (should fatal wall, cannot enter pipe)',[
    '+----+  +-+',
    '|@  H|>>|O|',
    '+----+  +-+'],{input:'',steps:8});
  // O-room = output room; the pipe flows OUT of the left room. Man walking east hits H first.
  process.exit(0);
})();
