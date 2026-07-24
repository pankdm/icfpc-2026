// Programmatic grid builder. Produces array-of-row-strings.
// Coordinates are grid indices [col,row] = [x,y], matching oracle pos.
function grid(W, H) {
  const g = Array.from({length:H}, ()=>Array(W).fill(' '));
  return g;
}
function rect(g, x0, y0, x1, y1) { // draw a room border rectangle inclusive corners
  for (let x=x0;x<=x1;x++){ g[y0][x]='-'; g[y1][x]='-'; }
  for (let y=y0;y<=y1;y++){ g[y][x0]='|'; g[y][x1]='|'; }
  g[y0][x0]=g[y0][x1]=g[y1][x0]=g[y1][x1]='+';
}
function put(g, x, y, ch){ g[y][x]=ch; }
function toRows(g){ return g.map(r=>r.join('')); }
module.exports={grid,rect,put,toRows};
