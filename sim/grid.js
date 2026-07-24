// Build a rectangular room grid with precise cell placements (no hand-alignment).
function room(w, h, cells) { // w,h = interior size; cells = [[c,r,ch],...] in interior coords (1..w, 1..h)
  const W = w + 2, H = h + 2;
  const g = Array.from({ length: H }, () => Array(W).fill(' '));
  for (let x = 0; x < W; x++) { g[0][x] = '-'; g[H - 1][x] = '-'; }
  for (let y = 0; y < H; y++) { g[y][0] = '|'; g[y][W - 1] = '|'; }
  g[0][0] = g[0][W - 1] = g[H - 1][0] = g[H - 1][W - 1] = '+';
  for (const [c, r, ch] of cells) g[r][c] = ch;
  return g.map(row => row.join(''));
}
module.exports = { room };
