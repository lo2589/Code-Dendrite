// Independent SVG oracle for routing tests: parse commands, not numeric pairs.
// The production renderer emits axis-aligned half-ellipse A commands and small
// quadratic Q corners.
function segments(d) {
  const out=[];let p=null;
  for (const m of String(d).matchAll(/([MLAQ])([^MLAQ]*)/g)) {
    const n=(m[2].match(/[-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?/gi)||[]).map(Number);
    if(m[1]==='M') {p={x:n[0],y:n[1]};continue;}
    if(m[1]==='L') {const q={x:n[0],y:n[1]};if(p)out.push([p,q]);p=q;continue;}
    if(m[1]==='A') {
      if(n.length!==7 || n[2]!==0 || n[3]!==0) throw Error('unexpected arc '+m[0]);
      const end={x:n[5],y:n[6]},cx=(p.x+end.x)/2,cy=p.y;
      const forward=end.x>p.x,up=forward===Boolean(n[4]);
      if(Math.abs(p.y-end.y)>1e-7)throw Error('non-horizontal hop');
      for(let k=1;k<=32;k++) {
        const theta=Math.PI*k/32;
        const q={x:cx+(forward?-1:1)*n[0]*Math.cos(theta),y:cy+(up?-1:1)*n[1]*Math.sin(theta)};
        out.push([p,q]);p=q;
      }
      p=end;
      continue;
    }
    if(m[1]==='Q') {
      if(n.length!==4) throw Error('unexpected quadratic '+m[0]);
      const c={x:n[0],y:n[1]},end={x:n[2],y:n[3]},start=p;
      for(let k=1;k<=16;k++) {
        const t=k/16,u=1-t;
        const q={x:u*u*start.x+2*u*t*c.x+t*t*end.x,y:u*u*start.y+2*u*t*c.y+t*t*end.y};
        out.push([p,q]);p=q;
      }
      p=end;
    }
  }
  return out;
}
// Slab intersection handles diagonals as well, independently of the router.
function hits(p,q,r) {
  const eps=1e-6,lo=[r.x+eps,r.y+eps],hi=[r.x+r.w-eps,r.y+r.h-eps];
  let first=0,last=1;
  for(let i=0;i<2;i++) {
    const key=i?'y':'x',delta=q[key]-p[key];
    if(Math.abs(delta)<1e-12){if(p[key]<lo[i]||p[key]>hi[i])return false;continue;}
    const a=(lo[i]-p[key])/delta,b=(hi[i]-p[key])/delta;
    first=Math.max(first,Math.min(a,b));last=Math.min(last,Math.max(a,b));
    if(first>last)return false;
  }
  return true;
}
module.exports={segments,hits};
