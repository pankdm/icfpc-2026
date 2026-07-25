const { boot } = require('/Users/visenbaev/icfpc26/sim/harness.js');
const fs=require('fs');
(async()=>{
  const w=await boot(); const s=w.newSession();
  const rows=fs.readFileSync('scratchpad/belt_floor/rigs/ring_both_wide.man','utf8').replace(/\n$/,'').split('\n');
  const W=Math.max(...rows.map(r=>r.length)); const g=(x,y)=>(rows[y]&&rows[y][x])||' ';
  const input=[11,22,33,44,55,66].join(' ');
  let j=JSON.parse(w.load(s,rows,input,"",""));
  const seq=[]; let prev=new Map();
  for(let i=0;i<1200 && seq.length<20;i++){
    const cur=JSON.parse(w.stepN(s,1,false));
    for(const r of (j.entities?.runners||[])){
      if(r.id!==0) continue;
      const [x,y]=r.pos; const cr=(cur.entities?.runners||[]).find(u=>u.id===0);
      if(g(x,y)==='s' && cr && (cr.pos[0]!==x||cr.pos[1]!==y)) seq.push(r.a);
    }
    j=cur;
  }
  console.log('main A at each send (first 20):',seq.join(' '));
  w.closeSession(s);
})().catch(e=>{console.error(String(e).slice(0,300));process.exit(1)});
