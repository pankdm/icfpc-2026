const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const L = require('/Users/visenbaev/icfpc26/tools/lib.js');
(async()=>{
  const w=await boot();
  const rows=L.manRows(L.readMan('solutions/sort-numbers/select-v3.man'));
  // single round: count=3 vals 3 1 2 -> expect 1 2 3
  const s=w.newSession();
  let j=JSON.parse(w.load(s, rows, "3 3 1 2", "1 2 3", ""));
  console.log('load type', j.type, j.message||'');
  let last=j;
  while(!j.halted && !j.outputSettled && j.step<20000){
    const nj=JSON.parse(w.stepN(s,2000,false));
    if(nj.type==='error'){console.log('ERR',nj.message);break;}
    if(nj.step===j.step){j=nj;break;}
    j=nj;
  }
  console.log('step',j.step,'halted',j.halted,'output',JSON.stringify(j.output),'reason',j.reason,'fatal',JSON.stringify(j.fatal||null));
  w.closeSession(s);
})();
