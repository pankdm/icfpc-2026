// Extended differential fixtures: pipes, IO rooms, numeric literals, rounds, load errors,
// plus the real seeded triangle solutions run end-to-end.
const fs = require('fs');
const path = require('path');

function rows(str) { return str.replace(/^\n/, '').replace(/\n$/, '').split('\n'); }
function manRows(file) { return fs.readFileSync(file, 'utf8').replace(/\r/g, '').split('\n'); }

const cases = [];

// ---- numeric literals ----
cases.push({ name: 'lit-east-123', rows: rows(`
+-------+
|@\`123\`H|
+-------+`), steps: 10 });

cases.push({ name: 'lit-empty', rows: rows(`
+------+
|@\`\`3M+|
+------+`), steps: 10 });

cases.push({ name: 'lit-west-321', rows: rows(`
+-------+
|H<\`123\`|
|......@|
+-------+`), steps: 3 });

// vertical literal read downward (south) then upward (north) — route man around
cases.push({ name: 'lit-vert-south', rows: rows(`
+---+
|@v.|
|.\`.|
|.1.|
|.2.|
|.3.|
|.\`.|
|..H|
+---+`), steps: 14 });

cases.push({ name: 'lit-neg-via-N', rows: rows(`
+---------+
|@\`42\`NMH.|
+---------+`), steps: 10 });

// overflow -> load error (both should reject)
cases.push({ name: 'lit-overflow', rows: rows(`
+---------------------------+
|@\`99999999999999999999999\`H|
+---------------------------+`), steps: 4 });

// bad char in literal -> load error
cases.push({ name: 'lit-badchar', rows: rows(`
+------+
|@\`1x2\`|
|.....H|
+------+`), steps: 4 });

// west-reading: man loops up and comes back west through `123` -> expect 321
cases.push({ name: 'lit-west-read', rows: rows(`
+--------+
|H.\`123\`<|
|@......^|
+--------+`), steps: 20 });

// north-reading vertical literal -> reversed
cases.push({ name: 'lit-north-read', rows: rows(`
+----+
|H..<|
|.\`..|
|.1..|
|.2..|
|.3..|
|.\`..|
|.^.@|
+----+`), steps: 20 });

// corner backtick shared by horizontal + vertical literal
cases.push({ name: 'lit-corner', rows: rows(`
+------+
|@\`12\`.|
|.3....|
|.4....|
|.\`...H|
+------+`), steps: 20 });

// Literal content is a nop only ALONG the literal's own axis. A man crossing a horizontal
// literal from above executes the digit he lands on (A = digit); only the closing backtick
// loads the whole literal. Symmetrically for a vertical literal crossed horizontally.
cases.push({ name: 'lit-cross-h-digit', rows: rows(`
+-----+
|@.v..|
|\`12\`.|
|..M.H|
|..>^.|
+-----+`), steps: 12 });

cases.push({ name: 'lit-cross-v-digit', rows: rows(`
+------+
|..\`...|
|@.5..H|
|..\`...|
+------+`), steps: 10 });

// Literals are scoped to one ROOM: two literals on the same row in different rooms must not
// pair across the wall between them (a global row scan rejects real programs the oracle loads).
cases.push({ name: 'lit-two-rooms-same-row', rows: rows(`
+----+ +----+
|@\`  | |\`  H|
|.1  | |2..<|
|.\`  | |\`...|
+----+ +----+`), steps: 12 });

// ...but WITHIN one room a non-digit between two backticks is a load error on BOTH axes.
cases.push({ name: 'lit-junk-in-row', rows: rows(`
+--------+
|@\` M \`2\`|
+--------+`), steps: 4 });

cases.push({ name: 'lit-junk-in-col', rows: rows(`
+-----+
|@\`1\`.|
|.M...|
|.\`2\`.|
+-----+`), steps: 4 });

// A backtick with no partner on either axis is a load error.
cases.push({ name: 'lit-unmatched', rows: rows(`
+-----+
|@7\`.H|
+-----+`), steps: 4 });

// Three backticks in a column: (0,1) pair, the third is left unmatched -> load error.
cases.push({ name: 'lit-odd-tick-col', rows: rows(`
+---+
|@\`.|
|.1.|
|.\`.|
|.2.|
|.\`.|
+---+`), steps: 4 });

// ---- basic pipe + IO (hand-built echo) ----
cases.push({ name: 'echo-simple', rows: rows(`
+-+ +-+
|I| |O|
+-+ +-+
 v   ^
 v   ^
+-----+
|@rsv.|
|..<H.|
+-----+`), steps: 30, input: '7', expected: '7' });

// ---- q (count nearest incoming) never blocks ----
cases.push({ name: 'q-count', rows: rows(`
+-+
|I|
+-+
 v
 v
+---+
|@qH|
+---+`), steps: 12, input: '5' });

// ---- send blocking: pipe capacity ----
cases.push({ name: 'send-block-cap', rows: rows(`
+-----+
|@2sM.|
|H.s<.|
+-----+
 v
 v
+-+
|O|
+-+`), steps: 40, input: '', expected: '' });

// ---- looping echo (exercises round gating: input withheld until prior round output) ----
const echoLoop = rows(`
+-+   +-+
|I|   |O|
+-+   +-+
 v     ^
 v     ^
+-------+
|>@r.s.v|
|^.....<|
+-------+`);
cases.push({ name: 'echo-loop-1round', rows: echoLoop, steps: 200, input: '7', expected: '7' });
cases.push({ name: 'echo-loop-2round', rows: echoLoop, steps: 400, input: '7 / 8', expected: '7 / 8' });
cases.push({ name: 'echo-loop-3round', rows: echoLoop, steps: 600, input: '3 / 4 / 5', expected: '3 / 4 / 5' });
cases.push({ name: 'echo-loop-zero-round', rows: echoLoop, steps: 400, input: '/ 9', expected: '/ 9' });

// ---- multi-pipe nearest: two output pipes, man sends to nearest ----
cases.push({ name: 'two-out-nearest', rows: rows(`
+-+   +-+
|O|   |O|
+-+   +-+
 ^     ^
 ^     ^
+-------+
|@1sH...|
+-------+`), steps: 30 });

// ---- shared-wall quirk & stray men ----
cases.push({ name: 'shared-wall', rows: rows(`
+--+--+
|@.|@.|
+--+--+`), steps: 10 });
cases.push({ name: 'stray-man', rows: rows(`
+--+
|@.|
+--+
@...`), steps: 10 });
cases.push({ name: 'shared-wall-3', rows: rows(`
+--+--+--+
|@1|@2|@3|
+--+--+--+`), steps: 10 });

// ---- LM-75 display ----
// DATA (left) + SWAP (bottom) into a 2x2 display; drivers send once then wall-fault.
const disp2 = rows(`
+---+   +==+
|@5s|>>>:..:
+---+   :..:
        +==+
         ^
         ^
       +---+
       |@1s|
       +---+`);
// mismatch: commits an all-0 frame, expected all-5
cases.push({ name: 'disp-mismatch', rows: disp2, steps: 8, frames: JSON.stringify([[['55', '55'], ['55', '55']]]) });
// match: expected all-0 (what it actually commits) -> frame_matched increments
cases.push({ name: 'disp-match', rows: disp2, steps: 8, frames: JSON.stringify([[['00', '00']]]) });

// DATA-only looping driver: cursor advance + back-buffer writes, no frames judged
cases.push({ name: 'disp-data-loop', rows: rows(`
+----+  +==+
|>@.v|>>:..:
|^7s<|  :..:
+----+  +==+`), steps: 60 });

// ADDR (top) + DATA (left) + SWAP (bottom), single-shot drivers
cases.push({ name: 'disp-addr-data-swap', rows: rows(`
        +--+
        |@2|
        +--+
         v
         v
+---+   +==+
|@6s|>>>:..:
+---+   :..:
        +==+
         ^
         ^
       +---+
       |@1s|
       +---+`), steps: 12, frames: JSON.stringify([[['66', '66'], ['66', '66']]]) });

// display fault reasons
cases.push({ name: 'disp-swap-bad', rows: rows(`
+==+
:..:
:..:
+==+
 ^
 ^
+----+
|@5sH|
+----+`), steps: 25 });
cases.push({ name: 'disp-addr-oob', rows: rows(`
+----+
|@9sH|
+----+
 v
 v
+==+
:..:
:..:
+==+`), steps: 25 });
cases.push({ name: 'disp-data-oob', rows: rows(`
+------+  +==+
|@9M9+s|>>:..:
+------+  :..:
          +==+`), steps: 25 });

// ---- triangle real solutions across several inputs ----
const triDir = path.join(__dirname, '..', 'solutions', 'triangle');
const triInputs = [['0', '0'], ['1', '1'], ['4', '10'], ['10', '55'], ['63', '2016'], ['987', '487578']];
for (const sol of ['p1', 'p2', 'p3']) {
  const file = path.join(triDir, `${sol}.man`);
  if (!fs.existsSync(file)) continue;
  for (const [inp, exp] of triInputs) {
    cases.push({ name: `triangle-${sol}-in${inp}`, rows: manRows(file), steps: 4000, input: inp, expected: exp });
  }
}

module.exports = { cases };
