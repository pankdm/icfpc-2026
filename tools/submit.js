#!/usr/bin/env node
// Submit a solution to the grader and poll the result.
//   node tools/submit.js <slug> <file.man>
const L = require('./lib.js');

(async () => {
  const [slug, file] = process.argv.slice(2);
  if (!slug || !file) { console.error('usage: node tools/submit.js <slug> <file.man>'); process.exit(2); }
  const key = L.apiKey();
  if (!key) { console.error('no API_KEY found (.env)'); process.exit(1); }
  const probs = await L.listProblems();
  const p = probs.find(x => x.slug === slug);
  if (!p) { console.error(`unknown slug ${slug}`); process.exit(1); }
  if (p.status === 'practice') { console.error('practice problem — the grader rejects submissions'); process.exit(1); }

  const program = L.readMan(file);
  const r = await fetch(`${L.BASE}/submissions`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ problemId: p.id, program }),
  });
  const j = await r.json();
  if (!r.ok) { console.error('submit failed:', r.status, JSON.stringify(j)); process.exit(1); }
  console.log(`submitted ${file} → ${slug}: id=${j.id} status=${j.status}`);

  for (let i = 0; i < 45; i++) {
    await new Promise(res => setTimeout(res, 2000));
    const pr = await fetch(`${L.BASE}/submissions/${j.id}`, { headers: { Authorization: `Bearer ${key}` } });
    const pj = await pr.json();
    if (pj.status === 'done' || pj.status === 'failed') {
      console.log(`\nresult: ${pj.status}   cases ${pj.casesPassed}/${pj.casesTotal}   score ${pj.score ?? 'n/a'}`);
      if (pj.loadError) console.log('loadError:', pj.loadError);
      if (pj.error) console.log('error:', pj.error);
      process.exit(pj.status === 'done' && pj.casesPassed === pj.casesTotal ? 0 : 1);
    }
    process.stdout.write(`\r  ${pj.status}... (${(i + 1) * 2}s)   `);
  }
  console.log('\nstill pending — re-check with tools/status.js or poll the submission id.');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
