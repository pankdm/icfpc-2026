const { boot } = require('./harness.js');
const { room } = require('./grid.js');

const mk = (odrop, cdrop) => room(9, 5, [
  [1,4,'@'], [5,4,'^'], [5,2,'Y'],
  [odrop,2,'v'], [odrop,3,'<'],
  [cdrop,2,'v'], [cdrop,3,'>'],
]);

function classify(w, rows) {
  const s = w.newSession();
  const j0 = JSON.parse(w.load(s, rows, '', '', ''));
  if (j0.type === 'error') { w.closeSession(s); return 'LOAD_ERR'; }
  let prev = j0.entities.runners.map(r => ({ id: r.id, pos: r.pos.join(','), dir: r.dir.join(',') }));
  for (let i = 0; i < 20; i++) {
    const jj = JSON.parse(w.step(s));
    if (jj.type === 'error') { w.closeSession(s); return 'STEP_ERR'; }
    const cur = jj.entities.runners.map(r => ({ id: r.id, pos: r.pos.join(','), dir: r.dir.join(',') }));
    // swap detection: two runners exchanged positions between prev and cur
    if (cur.length === 2 && prev.length === 2) {
      const [a, b] = prev, [c, d] = cur;
      const byId = id => cur.find(x => x.id === id);
      const pa = byId(a.id), pb = byId(b.id);
      if (pa && pb && pa.pos === b.pos && pb.pos === a.pos && a.pos !== b.pos) {
        w.closeSession(s); return `SWAP@t${i + 1} (${a.id}:${a.pos}<->${b.id}:${b.pos})`;
      }
      // adjacency-facing snapshot just before halt
    }
    if (jj.halted) {
      const at = cur.map(r => `#${r.id}@${r.pos}`).join(' ');
      w.closeSession(s);
      return `HALT@t${i + 1} reason=${jj.reason} [${at}]${jj.fatal ? ' FATAL:' + jj.fatal.reason : ''}`;
    }
    prev = cur;
  }
  w.closeSession(s); return 'no-halt';
}

(async () => {
  const w = await boot();
  for (let odrop = 6; odrop <= 9; odrop++)
    for (let cdrop = 2; cdrop <= 5; cdrop++)
      console.log(`odrop=${odrop} cdrop=${cdrop}: ${classify(w, mk(odrop, cdrop))}`);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
