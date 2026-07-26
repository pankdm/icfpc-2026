// trace runner path. node tr.js file.man "input" [nsteps] [fromtick]
const { boot } = require((__dirname + '/../sim/harness.js'));
const fs = require('fs');
(async () => {
  const file = process.argv[2], input = process.argv[3]||'';
  const N = parseInt(process.argv[4]||'800',10), from = parseInt(process.argv[5]||'0',10);
  const rows = fs.readFileSync(file,'utf8').replace(/\n$/,'').split('\n');
  const w = await boot(); const s = w.newSession();
  let j = JSON.parse(w.load(s, rows, input, '', ''));
  const cell=(x,y)=> (rows[y]&&rows[y][x])||' ';
  const d=v=>({'1,0':'>','−1,0':'<','-1,0':'<','0,1':'v','0,-1':'^'}[v+'']||v+'');
  for (let i=0;i<N;i++){
    j = JSON.parse(w.step(s));
    if (j.type==='error'){console.log('t'+(i+1)+' ERR',j.message);break;}
    if (i+1>=from){
      const rs=(j.entities.runners||[]).map(r=>`#${r.id}[${r.pos}]${d(r.dir)} '${cell(r.pos[0],r.pos[1])}' a=${r.a} b=${r.b} bp=${r.backpack}${r.halted?'H':''}`).join(' | ');
      console.log('t'+(i+1)+': '+rs+(j.output?' OUT='+j.output:'')+(j.halted?' <<'+j.reason+'>>':''));
    }
    if (j.halted) break;
  }
  process.exit(0);
})();
