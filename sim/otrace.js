const { boot } = require('./harness.js');
const { room } = require('./grid.js');
const cases = {
  'wall-walk': room(3,1,[[1,1,'@']]),
  'baseline-fork': room(5,5,[[1,3,'@'],[3,3,'Y']]),
  'fork-into-wall': room(4,3,[[1,1,'@'],[3,1,'Y']]),
};
(async()=>{const w=await boot();
 for(const [nm,rows] of Object.entries(cases)){
  console.log('\n### '+nm); const s=w.newSession(); let j=JSON.parse(w.load(s,rows,'','',''));
  const line=j=>`  end=${j.halted?(j.fatal?('FATAL:'+j.fatal.reason+'@'+j.fatal.pos):j.reason):'run'} | `+
    j.entities.runners.map(r=>`#${r.id}[${r.pos}]${r.halted?'H':''}`).join(' ');
  console.log('load'+line(j));
  for(let i=0;i<10;i++){j=JSON.parse(w.step(s)); console.log('t'+(i+1)+line(j)); if(j.halted)break;}
  w.closeSession(s);
 } process.exit(0);})();
