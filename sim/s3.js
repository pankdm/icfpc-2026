const {boot}=require('./lab.js');
const {grid,rect,put,toRows}=require('./build.js');
// Follow/train rig: B parks on r facing N; A follows from directly south, also facing N.
// On unblock tick B moves N (vacates C); A tries to move N into C. Same direction => different targets.
function buildS3(L){
  const iW=5,iH=5; const mainLeft=3+L;
  const g=grid(mainLeft+iW+2,iH+2);
  rect(g,mainLeft,0,mainLeft+iW+1,iH+1);
  rect(g,0,1,2,3); put(g,1,2,'I');
  for(let c=3;c<mainLeft;c++) put(g,c,2,'>');
  const X=ix=>mainLeft+ix;
  put(g,X(5),1,'r');                 // B parks (facing N)
  put(g,X(1),3,'>'); put(g,X(5),3,'^');
  put(g,X(1),4,'@'); put(g,X(5),4,'Y');
  put(g,X(1),5,'^'); put(g,X(5),5,'<');
  return toRows(g);
}
function dir(d){const m={'1,0':'E','-1,0':'W','0,1':'S','0,-1':'N'};return d?m[d+'']:'-';}
(async()=>{const w=await boot();
  for(let L=6;L<=20;L++){
    const s=w.newSession(); JSON.parse(w.load(s,buildS3(L),'7','',''));
    let prev=null, verdict='';
    for(let t=1;t<=30;t++){
      const j=JSON.parse(w.step(s));
      const rs=j.entities.runners;
      const cur=rs.map(r=>({id:r.id,p:r.pos.join(','),d:dir(r.dir),h:r.halted,a:r.a}));
      if(j.halted){verdict=`HALT@t${t} ${j.reason}${j.fatal?':'+j.fatal.reason:''} `+cur.map(c=>`#${c.id}@${c.p}${c.d}${c.h?'!':''}(a${c.a})`).join(' ');break;}
      // detect both moving N in column together (train) at consecutive cells
      prev=cur;
    }
    if(!verdict)verdict='no-halt/last='+(prev?prev.map(c=>`#${c.id}@${c.p}${c.d}(a${c.a})`).join(' '):'');
    w.closeSession(s);
    console.log('L='+L+': '+verdict);
  }
  process.exit(0);
})();
