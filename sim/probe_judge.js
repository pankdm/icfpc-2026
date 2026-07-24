const { boot } = require('./harness.js');
const P2 = ["+-+ +-+","|I| |O|","+-+ +-+"," v   ^"," v   ^","+-------+","|@rM*+Wv|","|H.s/W2<|","+-------+"];
(async()=>{const w=await boot();
 for(const [exp,label] of [['10','correct'],['11','wrong']]){
   const s=w.newSession(); let j=JSON.parse(w.load(s,P2,'4',exp,''));
   for(let i=0;i<50 && !j.halted && !j.outputSettled;i++){j=JSON.parse(w.stepN(s,5000,false));}
   console.log(`\n[expected ${exp} / ${label}] keys:`, Object.keys(j).join(','));
   console.log('  halted=%s outputSettled=%s reason=%s output=%j frameJudge=%j step=%s',
     j.halted, j.outputSettled, j.reason, j.output, j.frameJudge, j.step);
   w.closeSession(s);
 }
 process.exit(0);})();
