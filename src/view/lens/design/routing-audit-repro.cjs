// Read-only probes of current source. Run: node lens/design/routing-audit-repro.cjs
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');
const factories = new Map(), cache = new Map();
const shared = { trace: {} };
const ctx = vm.createContext({ window: { __ModuleLoader__: { load: x => factories.set(x.id, x.factory) } } });
for (const file of JSON.parse(fs.readFileSync(path.join(root, 'src/client/parts.json'))).order)
  vm.runInContext(fs.readFileSync(path.join(root, 'src/client', file), 'utf8'), ctx, { filename: file });
function get(name) {
  if (name === 'dsh-cdd-lens/view/record') return { stateOf: () => null };
  if (name === 'dsh-cdd-lens/state/store') return { shared };
  if (!cache.has(name)) cache.set(name, factories.get(name)(get));
  return cache.get(name);
}
const mod = name => get('dsh-cdd-lens/' + name);
const avoid = mod('routing/avoid');
const emit = mod('routing/emit').emitWires;
const hops = mod('routing/hops').markHops;
const metrics = { PORT_STUB: 9, LANE_STEP: 12, WIRE_HOP: 4.5, ARROW_EVERY: 84,
  CORRIDOR_MIN: 8, LAYER_GAP_X: 96, SUBLANE_STEP: 4, INNER_GAP_Y: 20,
  BOX_GAP_X: 80, BOX_GAP_Y: 80 };
const box = (id, x, y, w = 40, h = 40) => ({ id, x, y, w, h, file: id, flowLayer: 0 });
const orient = boxes => ({ byId: Object.fromEntries(boxes.map(b => [b.id, b])) });
const pts = pairs => pairs.map(([x,y]) => ({x,y}));
const line = (id, pairs, from = 'a', to = 'b') => ({ id, pts: pts(pairs), from, to, type: 'call' });
const route = polylines => ({ polylines, HOP: 4.5, ARROW_EVERY: 84, LANE_STEP: 12 });
const len = ps => ps.slice(1).reduce((n,p,i) => n + Math.abs(p.x-ps[i].x) + Math.abs(p.y-ps[i].y),0);
const results = [];
function probe(name, fn) { const result = fn(); results.push({ name, ...result }); console.log(name + ': ' + JSON.stringify(result)); }

probe('A 圆弧后的真实穿节点被漏检', () => {
  const r = route([line('a-b', [[100,100],[300,100]]), line('c-d', [[150,50],[150,150]],'c','d')]);
  const drawn = emit(r, hops(r));
  const boxes = [box('a',60,80),box('b',300,80),box('obstacle',220,85,30,30)];
  assert.equal(avoid.blockedBy(r.polylines[0].pts,boxes,'a','b'), true);
  const d = drawn.wires[0].d;
  const fixed = avoid.repairCrossings(drawn,orient(boxes),metrics);
  assert.equal(fixed,0);
  assert.equal(drawn.wires[0].d,d);
  return { d, actualCollision:true, repairs:fixed };
});

probe('B 圆弧把画布原点拉向伪造的零坐标', () => {
  const r = route([line('a-b',[[100,100],[300,100]]),line('c-d',[[150,50],[150,150]],'c','d')]);
  const drawn = emit(r,hops(r));
  const fit = mod('layout/space').fitExtent({placed:[],fileBoxes:[]},drawn,{PAD:20});
  assert.equal(fit.minX,0); assert.equal(fit.minY,0);
  return { realMinimum:{x:100,y:50}, computed:fit };
});

probe('C 优先绕整个图，放弃近处空隙', () => {
  const a=box('a',0,100), b=box('b',300,100);
  const boxes=[a,b,box('obstacle',140,90,40,60),box('unrelated',600,1000)];
  const found=avoid.clearPath(a,b,boxes,9,'a','b');
  const local=pts([[40,120],[49,120],[49,80],[291,80],[291,120],[300,120]]);
  assert.equal(avoid.blockedBy(local,boxes,'a','b'),false);
  assert.ok(len(found)>len(local)*5);
  return { chosenLength:len(found), validLocalLength:len(local), chosenPoints:found };
});

probe('D 存在可走路径，模板搜索却失败；非 call 分层线抛错', () => {
  const a=box('a',0,100),b=box('b',300,100);
  const boxes=[a,b,box('right',41,80,50,100),box('top',-5,50,50,40),box('bottom',-5,150,50,40)];
  const local=pts([[0,120],[-20,120],[-20,30],[320,30],[320,100]]);
  assert.equal(avoid.blockedBy(local,boxes,'a','b'),false);
  assert.equal(avoid.clearPath(a,b,boxes,9,'a','b'),null);
  let error;
  try { mod('skins/tiers/route').routeTiers({chosen:[{from:'a',to:'b',types:['dataflow']}]},orient(boxes),undefined,metrics); }
  catch(e) { error=e.message; }
  assert.ok(error && /undefined/.test(error));
  return { validRoute:local, clearPath:null, tiersError:error };
});

probe('E 避障后原始折线和标签留在旧位置', () => {
  const a=box('a',0,100),b=box('b',300,100),boxes=[a,b,box('obstacle',140,90,40,60)];
  const r=route([line('a-b',[[40,120],[100,120],[100,120],[300,120]])]);
  const drawn=emit(r,hops(r));
  const original=JSON.stringify(r),labels=JSON.stringify(drawn.labels),d=drawn.wires[0].d;
  const fixed=avoid.repairCrossings(drawn,orient(boxes),metrics);
  assert.equal(fixed,1); assert.notEqual(d,drawn.wires[0].d);
  assert.equal(JSON.stringify(r),original); assert.equal(JSON.stringify(drawn.labels),labels);
  return { repairs:fixed, oldPath:d, newPath:drawn.wires[0].d, labelsUnchanged:true, routeUnchanged:true };
});

probe('F 同源左右出口被合并成穿过源节点的总线', () => {
  const r=route([
    line('left',[[0,120],[-10,120],[-10,220],[-100,220],[-100,300],[-90,300]],'a','left'),
    line('right',[[40,120],[50,120],[50,220],[200,220],[200,300],[210,300]],'a','right')
  ]);
  mod('routing/bus').mergeBuses(r);
  const ps=r.polylines[1].pts;
  assert.equal(ps[0].x,40); assert.equal(ps[1].x,-10);
  assert.equal(avoid.blockedBy(ps,[box('a',0,100)],'a','right'),false);
  return { source:{x:0,y:100,w:40,h:40}, newFirstSegment:ps.slice(0,2), sourceCollisionIgnored:true };
});

probe('G 流向同列入线落在右侧，节点入端口固定在左侧', () => {
  const a=box('a',0,100),b=box('b',0,220);
  const out=mod('skins/flow/route').routeFlow({chosen:[{from:'a',to:'b',types:['call']}]},orient([a,b]),undefined,metrics);
  const ps=out.route.polylines[0].pts, endpoint=ps[ps.length-1];
  assert.equal(endpoint.x,b.x+b.w);
  return { targetEntryX:b.x, wireTargetX:endpoint.x, wire:out.drawn.wires[0].d };
});

probe('H 相邻跳线没有合并，圆弧间出现反向回折', () => {
  const r=route([line('a-b',[[100,100],[300,100]]),line('c-d',[[150,50],[150,150]],'c','d'),line('e-f',[[154,50],[154,150]],'e','f')]);
  const drawn=emit(r,hops(r)),d=drawn.wires[0].d;
  assert.ok(d.includes('154.5,100 L149.5,100'));
  return { d, backwardRun:5 };
});
console.log('Confirmed ' + results.length + ' independent defects against current source.');
if (process.argv.includes('--json')) fs.writeFileSync(path.join(__dirname,'routing-audit-evidence.json'),JSON.stringify(results,null,2)+'\n');
