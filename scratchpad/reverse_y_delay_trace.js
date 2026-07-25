#!/usr/bin/env node
// Oracle runner for reverse_y_delay_poc.man.

const fs = require('fs');
const path = require('path');
const { boot } = require('../sim/harness.js');
const L = require('../tools/lib.js');

async function main() {
  const man = path.join(__dirname, 'reverse_y_delay_poc.man');
  const rows = L.manRows(fs.readFileSync(man, 'utf8'));
  const wasm = await boot();
  const session = wasm.newSession();

  let snap = JSON.parse(wasm.load(session, rows, '3 10 20 30', '30 20 10', ''));
  if (snap.type === 'error') {
    throw new Error(`load failed: ${snap.message}`);
  }

  const events = [];
  let previousOutputLength = 0;
  for (let i = 0; i < 500 && !snap.outputSettled && !snap.halted; i++) {
    snap = JSON.parse(wasm.stepN(session, 1, false));
    const output = snap.output || [];
    if (output.length !== previousOutputLength) {
      events.push({
        tick: snap.step,
        output: [...output],
        runners: (snap.entities?.runners || []).map(r => ({
          id: r.id,
          pos: r.pos,
          a: r.a,
          bp: r.backpack,
          halted: r.halted,
        })),
      });
      previousOutputLength = output.length;
    }
  }

  console.log(JSON.stringify({
    settled: !!snap.outputSettled,
    halted: !!snap.halted,
    reason: snap.reason || snap.fatal || null,
    tick: snap.step,
    output: snap.output || [],
    events,
  }, null, 2));

  wasm.closeSession(session);
  process.exit(snap.outputSettled ? 0 : 1);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
