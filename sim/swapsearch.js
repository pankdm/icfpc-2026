const { boot } = require('./harness.js');
const { room } = require('./grid.js');
function rnd(n){ return Math.floor(Math.random()*n); }
const ARROWS=['<','>','^','v'];
function randProg(W,H){
  const cells=[]; const used=new Set();
  const put=(ch)=>{let x,y,k;do{x=1+rnd(W);y=1+rnd(H);k=x+','+y;}while(used.has(k));used.add(k);cells.push([x,y,ch]);};
  put('@'); put('Y'); put('Y');
  const na=6+rnd(8); for(let i=0;i<na;i++) put(ARROWS[rnd(4)]);
  return room(W,H,cells);
}
function detectSwap(snaps){
  for(let i=1;i<snaps.length;i++){
    const p=snaps[i-1].entities?.runners, c=snaps[i].entities?.runners; if(!p||!c) continue;
    for(let a=0;a<c.length;a++)for(let b2=0;b2<c.length;b2++){ if(a===b2)continue;
      const ca=c[a], cb=c[b2]; if(ca.halted||cb.halted) continue;
      const pa=p.find(r=>r.id===ca.id), pb=p.find(r=>r.id===cb.id); if(!pa||!pb)continue;
      if(pa.pos[0]===cb.pos[0]&&pa.pos[1]===cb.pos[1]&&pb.pos[0]===ca.pos[0]&&pb.pos[1]===ca.pos[1]
         && !(pa.pos[0]===pb.pos[0]&&pa.pos[1]===pb.pos[1]))
        return {i, a:ca.id, b:cb.id, pos:[pa.pos,pb.pos]};
    }
  }
  return null;
}
(async()=>{const w=await boot(); let tries=0, swaps=0, adjHeadons=0;
 for(let t=0;t<4000;t++){ const rows=randProg(9,9); const s=w.newSession();
   const j0=JSON.parse(w.load(s,rows,'','','')); if(j0.type==='error'){w.closeSession(s);continue;}
   const snaps=[j0]; for(let k=0;k<24;k++){const jj=JSON.parse(w.step(s)); snaps.push(jj); if(jj.type==='error'||jj.halted)break;}
   w.closeSession(s); tries++;
   const sw=detectSwap(snaps);
   if(sw){ swaps++; if(swaps<=3){ console.log('SWAP FOUND @tries',t,'step',sw.i,'ids',sw.a,sw.b,'pos',JSON.stringify(sw.pos)); rows.forEach(r=>console.log('   '+r)); } }
 }
 console.log(`\n${tries} valid runs, ${swaps} swaps detected`);
 process.exit(0);})();
