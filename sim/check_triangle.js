const { boot } = require('./harness.js');
const progs = {
  P1: ["+-+ +-+","|I| |O|","+-+ +-+"," v   ^"," v   ^","+-----+","|@rM*v|","|v2W+<|","|>W/sv|","|   H<|","+-----+"],
  P2: ["+-+ +-+","|I| |O|","+-+ +-+"," v   ^"," v   ^","+-------+","|@rM*+Wv|","|H.s/W2<|","+-------+"],
  P3: ["+-+  +--------+","|I|>>|@rsM1+sH|","+-+  +--------+","      v","      v","     +-------+","     |@rMr*sH|","     +-------+","      v","      v","+-+  +-------+","|O|<<|@2Mr/sH|","+-+  +-------+"],
};
const T = n => n*(n+1)/2;
const inputs = [0,1,2,3,4,5,10,100,1000];
(async()=>{const w=await boot();
 for(const [nm,rows] of Object.entries(progs)){
   console.log(`\n### ${nm}`);
   // load-only check with first input
   const s0=w.newSession(); const ld=JSON.parse(w.load(s0,rows,'0','',''));
   if(ld.type==='error'){console.log('  LOAD ERROR:',ld.message); w.closeSession(s0); continue;}
   console.log('  loads OK. rooms='+(ld.entities.rooms||[]).length+' men='+(ld.entities.runners||[]).length);
   w.closeSession(s0);
   for(const n of inputs){
     const s=w.newSession(); const j0=JSON.parse(w.load(s,rows,String(n),'',''));
     if(j0.type==='error'){console.log(`  n=${n}: LOAD ERROR ${j0.message}`); w.closeSession(s); continue;}
     let out=[], end=null, steps=0; const cap=2_000_000;
     for(;steps<cap;steps++){const j=JSON.parse(w.step(s)); if(j.type==='error'){end='err:'+j.message;break;} if(j.output&&j.output.length)out=j.output; if(j.halted){end=j.fatal?('fatal:'+j.fatal.reason):j.reason;break;}}
     w.closeSession(s);
     const got=out.join(' '), exp=String(T(n));
     const ok = got===exp;
     console.log(`  n=${n}: out=[${got}] exp=${exp} ${ok?'PASS':'FAIL'} (end=${end||'cap'}, steps=${steps})`);
   }
 }
 process.exit(0);})();
