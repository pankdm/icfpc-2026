const { boot } = require((__dirname + '/../sim/harness.js'));
const fs = require('fs');
(async () => {
  const [file, input] = process.argv.slice(2);
  const rows = fs.readFileSync(file, 'utf8').replace(/\n$/, '').split('\n');
  const w = await boot();
  const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, '', ''));
  if (j.type==='error'){console.log('LOADERR',j.message);process.exit(1);}
  for (let k=0;k<3000 && !j.halted;k++){ j=JSON.parse(w.stepN(s,1,false)); if(j.type==='error')break; }
  const rs=(j.entities&&j.entities.runners)||[];
  rs.filter(r=>r.b!==0).sort((a,b)=>a.pos[1]-b.pos[1]).forEach(r=>console.log('pos',JSON.stringify(r.pos),'b',r.b,'a',r.a));
  console.log('step',j.step,'halted',j.halted);
  process.exit(0);
})();
