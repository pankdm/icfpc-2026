const {boot}=require('./lab.js');
const {grid,rect,put,toRows}=require('./build.js');
// Follow/train, clean exit: B parks on r(5,2) facing N; on unblock B goes N to (5,1)='>' then E.
// A follows up column 5 from the south. Watch whether A enters B's vacated cell same tick.
function buildS3(L){
  const iW=7,iH=6; const mainLeft=3+L;
  const g=grid(mainLeft+iW+2,iH+2);
  rect(g,mainLeft,0,mainLeft+iW+1,iH+1);
  rect(g,0,1,2,3); put(g,1,2,'I');
  for(let c=3;c<mainLeft;c++) put(g,c,2,'>');
  const X=ix=>mainLeft+ix;
  put(g,X(5),1,'>');                 // B turns E after unblocking
  put(g,X(5),2,'r');                 // B parks facing N
  put(g,X(1),4,'>'); put(g,X(5),4,'^');
  put(g,X(1),5,'@'); put(g,X(5),5,'Y');
  put(g,X(1),6,'^'); put(g,X(5),6,'<');
  return toRows(g);
}
function dir(d){const m={'1,0':'E','-1,0':'W','0,1':'S','0,-1':'N'};return d?m[d+'']:'-';}
(async()=>{const w=await boot();
  const L=Number(process.argv[2]||14);
  const s=w.newSession(); JSON.parse(w.load(s,buildS3(L),'7','',''));
  console.log('=== S3 follow L='+L+' ===');
  buildS3(L).forEach(r=>console.log('   |'+r));
  for(let t=1;t<=30;t++){
    const j=JSON.parse(w.step(s));
    const rs=j.entities.runners.map(r=>`#${r.id}@[${r.pos}]${dir(r.dir)}${r.halted?'!H':''}(a${r.a})`).join('  ');
    console.log('t'+t+'  '+rs+(j.halted?` <<${j.reason}${j.fatal?':'+j.fatal.reason:''}>>`:''));
    if(j.halted)break;
  }
  w.closeSession(s);
  process.exit(0);
})();
