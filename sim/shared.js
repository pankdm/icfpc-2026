const { boot } = require('./harness.js');
const tests = {
  'vertical-shared-wall': ["+---+","|@  |","+---+","|@  |","+---+"],
  'horizontal-shared-wall': ["+--+--+","|@ |@ |","+--+--+"],
  'thick-gap (own walls)': ["+--+ +--+","|@ | |@ |","+--+ +--+"],
};
(async()=>{const w=await boot();
 for(const [nm,rows] of Object.entries(tests)){
   const s=w.newSession(); const j=JSON.parse(w.load(s,rows,'','',''));
   console.log(`\n### ${nm}`); rows.forEach(r=>console.log('   '+r));
   if(j.type==='error'){console.log('LOAD ERROR:',j.message);}
   else{const rooms=(j.entities.rooms||[]).map(r=>`room#${r.id} min${r.min} max${r.max}`);
        const men=(j.entities.runners||[]).map(r=>`#${r.id}@[${r.pos}]`);
        console.log('  OK -',rooms.length,'rooms:',rooms.join(' | '),'| men:',men.join(' '));}
   w.closeSession(s);
 } process.exit(0);})();
