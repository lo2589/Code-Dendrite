"""
anchor_browser.py - CD Anchor Browser (compound force graph)
=============================================================
  Left   : file tree
  Center : compound graph — class = large rect containing method circles;
           standalone functions = circles; external callers/callees = dashed circles
  Right  : detail panel for selected node

Usage:
  python anchor_browser.py <project_root_with_.codedendrite> [--output browser.html]
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict

_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CD Anchor Browser — __PROJECT__</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{display:flex;height:100vh;overflow:hidden;font-family:'Consolas','Menlo',monospace;font-size:13px;background:#1e1e1e;color:#d4d4d4}

/* sidebar */
#sidebar{width:210px;min-width:120px;display:flex;flex-direction:column;border-right:1px solid #3e3e42;background:#252526;overflow:hidden;flex-shrink:0}
#sb-hdr{padding:7px 10px;font-size:11px;font-weight:bold;color:#bbb;letter-spacing:.05em;text-transform:uppercase;border-bottom:1px solid #3e3e42;flex-shrink:0}
#tf-wrap{padding:5px 7px;flex-shrink:0;border-bottom:1px solid #3e3e42}
#tf-wrap input{width:100%;padding:3px 6px;background:#3c3c3c;border:1px solid #555;color:#d4d4d4;font-size:12px;border-radius:2px;outline:none}
#tf-wrap input:focus{border-color:#007acc}
#file-tree{flex:1;overflow-y:auto;padding:3px 0}
.dl{display:flex;align-items:center;padding:2px 7px;color:#e2c08d;cursor:pointer;user-select:none;white-space:nowrap}
.dl:hover{background:#2a2d2e}
.ca{width:13px;display:inline-block;font-size:10px;color:#858585}
.dc{padding-left:12px;display:none}
.dc.open{display:block}
.fi{padding:2px 7px 2px 19px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#c8c8c8;font-size:12px}
.fi:hover{background:#2a2d2e}
.fi.sel{background:#094771;color:#fff}
.fc{float:right;color:#555;font-size:10px;margin-left:4px}

/* graph */
#graph-area{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}
#gh{padding:5px 10px;border-bottom:1px solid #3e3e42;display:flex;align-items:center;gap:6px;background:#2d2d30;flex-shrink:0}
#gtit{flex:1;color:#9cdcfe;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.leg{display:inline-block;padding:1px 7px;border-radius:2px;font-size:10px}
.tog{padding:2px 8px;border:1px solid #555;background:#3c3c3c;color:#aaa;font-size:11px;border-radius:2px;cursor:pointer;flex-shrink:0}
.tog.on{background:#264f78;border-color:#007acc;color:#9cdcfe}
#gw{flex:1;overflow:hidden;position:relative}
#gsvg{width:100%;height:100%;background:#16161c;display:block;cursor:grab}
#gsvg:active{cursor:grabbing}
#gemp{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#3a3a3a;font-size:14px;text-align:center;pointer-events:none;line-height:2.2}

/* detail */
#detail{width:420px;min-width:200px;display:flex;flex-direction:column;border-left:1px solid #3e3e42;background:#1c1c1c;overflow:hidden;flex-shrink:0}
#dh{padding:7px 10px;font-size:11px;font-weight:bold;color:#bbb;letter-spacing:.05em;text-transform:uppercase;border-bottom:1px solid #3e3e42;flex-shrink:0;display:flex;align-items:center;gap:6px}
#dh span{flex:1}
#db{flex:1;overflow-y:auto;display:flex;flex-direction:column}
#d-meta{flex-shrink:0}
#d-src{flex:1;display:flex;flex-direction:column;border-top:1px solid #2a2a2a;min-height:0}
#d-src-hdr{padding:4px 10px;font-size:10px;font-weight:bold;color:#666;letter-spacing:.05em;text-transform:uppercase;flex-shrink:0;background:#161616}
#d-src-pre{flex:1;overflow:auto;margin:0;background:#0d1117;color:#c9d1d9;font-size:11px;font-family:'Consolas','Menlo',monospace;padding:6px 0;white-space:pre;tab-size:4;line-height:1.55}
.src-ln{display:block;padding:0 8px;min-width:100%}
.src-hl{background:#1c3553;display:block;padding:0 8px;min-width:100%}
.src-lnum{color:#3a3a4a;user-select:none;display:inline-block;min-width:3.2em;text-align:right;padding-right:10px;font-size:10px}
.ph{padding:28px 14px;color:#3a3a3a;text-align:center;font-size:12px;line-height:1.8}
.dn{padding:10px 12px 3px;color:#dcdcaa;font-size:13px;word-break:break-all}
.dm{padding:0 12px 8px;color:#858585;font-size:11px}
.ds{padding:6px 12px;border-bottom:1px solid #222}
.ds h4{color:#858585;font-size:10px;letter-spacing:.05em;text-transform:uppercase;margin-bottom:4px}
.ds p{color:#c8c8c8;font-size:12px;line-height:1.5}
.chip{display:inline-block;padding:1px 6px;margin:2px 2px 2px 0;border-radius:2px;cursor:pointer;font-size:11px;white-space:nowrap}
.ci{background:#264f78;color:#9cdcfe}.ci:hover{background:#094771}
.ce{background:#222230;color:#556}.ce:hover{background:#2a2a42;color:#9cdcfe}
</style>
</head>
<body>

<div id="sidebar">
  <div id="sb-hdr">Files</div>
  <div id="tf-wrap"><input id="tree-filter" type="text" placeholder="Filter files…" oninput="filterTree(this.value)"></div>
  <div id="file-tree"></div>
</div>

<div id="graph-area">
  <div id="gh">
    <div id="gtit">Select a file</div>
    <button class="tog on" id="ext-btn" onclick="toggleExt()">external</button>
    <span class="leg" style="background:#1e1535;color:#c586c0;border:1px solid #5a3a9a">class</span>
    <span class="leg" style="background:#1a4a2a;color:#4ec9b0">method</span>
    <span class="leg" style="background:#1a3060;color:#9cdcfe">function</span>
    <span class="leg" style="background:#1a2030;color:#3a5a7a;border:1px dashed #3a5a7a">ext</span>
  </div>
  <div id="gw">
    <svg id="gsvg"></svg>
    <div id="gemp">← select a file<br><span style="font-size:11px">click a node to see details</span></div>
  </div>
</div>

<div id="detail">
  <div id="dh"><span>Detail</span></div>
  <div id="db">
    <div id="d-meta"><div class="ph">Click a node<br>in the graph</div></div>
    <div id="d-src">
      <div id="d-src-hdr">Source</div>
      <pre id="d-src-pre"><span class="src-ln"><span class="src-lnum"></span>Select a file to view source</span></pre>
    </div>
  </div>
</div>

<script>
__DATA_JS__
__FILE_CODE_JS__

/* ──────── state ──────── */
let curFile = null, showExt = true, CG = null;

/* ──────── source view ──────── */
/* 源码不装在页里，用到才从磁盘取。内联过的那一版，四分之三的体积是源码快照，
   而快照一旦生成就开始过时；而且只装了本页那一个文件，点到邻居的 anchor 就是
   一句「取不到」。现在它来自磁盘，所以既不占页面体积，也永远是当前的。 */
const CODE = {};
function sourceUrl(fp){
  const q = new URLSearchParams(location.search);
  q.delete('page'); q.set('file', fp);
  return 'draw-source?' + q.toString();
}
function paintSource(fp, src, ls, le){
  const lines = src.split('\\n');
  let h = '';
  lines.forEach((line,i)=>{
    const ln=i+1;
    const hl=(ls&&le&&ln>=ls&&ln<=le);
    const cls=hl?'src-hl':'src-ln';
    h+=`<span class="${cls}"><span class="src-lnum">${ln}</span>${escX(line)}</span>\n`;
  });
  const pre=document.getElementById('d-src-pre');
  pre.innerHTML=h;
  if(ls){
    const spans=pre.querySelectorAll('.src-hl');
    if(spans.length) spans[0].scrollIntoView({block:'center'});
  }
}
function renderSource(fp, ls, le){
  const pre=document.getElementById('d-src-pre');
  if(CODE[fp]!==undefined){paintSource(fp,CODE[fp],ls,le);return;}
  if(FILE_CODE[fp]!==undefined){CODE[fp]=FILE_CODE[fp];paintSource(fp,FILE_CODE[fp],ls,le);return;}
  pre.textContent='读取中… '+fp;
  fetch(sourceUrl(fp),{cache:'no-store'})
    .then(r=>r.ok?r.text():Promise.reject(new Error('HTTP '+r.status)))
    .then(t=>{CODE[fp]=t;paintSource(fp,t,ls,le);})
    /* 说清楚是哪个文件、为什么没拿到。「取不到」这三个字本身不是答案。 */
    .catch(e=>{pre.textContent='读不到 '+fp+'：'+String(e.message||e)
      +'\\n（把这一页当普通文件直接打开时会这样，源码要经 host 才能读）';});
}

/* ──────── file tree ──────── */
function renderTree(tree, el, path) {
  for (const [name, ch] of Object.entries(tree)) {
    const fp = path ? path+'/'+name : name;
    if (ch !== null) {
      const wrap = document.createElement('div');
      const lbl = document.createElement('div');
      lbl.className = 'dl';
      lbl.innerHTML = '<span class="ca">▶</span><span>📁 '+esc(name)+'</span>';
      lbl.onclick = () => toggleD(lbl);
      const kids = document.createElement('div'); kids.className='dc';
      renderTree(ch, kids, fp);
      wrap.appendChild(lbl); wrap.appendChild(kids); el.appendChild(wrap);
    } else {
      const cnt=(typeof FILE_COUNT!=='undefined'&&FILE_COUNT[fp]!==undefined)?FILE_COUNT[fp]:(FILE_ANCHORS[fp]||[]).length;
      const f=document.createElement('div');
      f.className='fi'; f.dataset.path=fp; f.title=fp;
      f.innerHTML=esc(name)+'<span class="fc">'+cnt+'</span>';
      f.onclick=()=>selectFile(fp,f);
      el.appendChild(f);
    }
  }
}
function toggleD(lbl){const c=lbl.nextElementSibling;const o=c.classList.toggle('open');lbl.querySelector('.ca').textContent=o?'▼':'▶';}
function expandUp(el){let p=el.parentElement;while(p&&p.id!=='file-tree'){if(p.classList.contains('dc')){p.classList.add('open');const l=p.previousElementSibling;if(l){const c=l.querySelector('.ca');if(c)c.textContent='▼';}}p=p.parentElement;}}
function filterTree(q){q=q.toLowerCase();document.querySelectorAll('.fi').forEach(el=>{const s=!q||el.dataset.path.toLowerCase().includes(q);el.style.display=s?'':'none';if(s&&q)expandUp(el);});}
/* 每一页只装自己这个文件和它一跳之内的邻居。点到本页没有的文件，就换页——
   一页的大小因此由文件决定，不由仓库决定。 */
function pageHref(path){
  const id = (typeof PAGE_OF!=='undefined') ? PAGE_OF[path] : undefined;
  if (id === undefined) return null;
  if (location.protocol === 'file:') {
    const base = location.pathname.replace(/[/][^/]*$/, '');
    const stem = location.pathname.split('/').pop().replace(/[.]html$/, '').replace(/_pages$/, '');
    return base.replace(/[/][^/]*_pages$/, '') + '/' + (location.pathname.includes('_pages/') ? '' : stem + '_pages/') + id + '.html';
  }
  const q = new URLSearchParams(location.search);
  q.set('page', id);
  return location.pathname + '?' + q.toString();
}
function goHome(){
  if (location.protocol === 'file:') { history.back(); return; }
  const q = new URLSearchParams(location.search);
  q.delete('page');
  location.href = location.pathname + (q.toString() ? '?' + q.toString() : '');
}
function selectFile(path,el){
  if ((FILE_ANCHORS[path]||[]).length === 0 && (typeof FILE_COUNT==='undefined' || (FILE_COUNT[path]||0) > 0)) {
    const href = pageHref(path);
    if (href) { location.href = href; return; }
  }
  document.querySelectorAll('.fi').forEach(e=>e.classList.remove('sel')); el.classList.add('sel');
  curFile=path;
  document.getElementById('gtit').textContent=path+'  ('+(FILE_ANCHORS[path]||[]).length+' anchors)';
  document.getElementById('gemp').style.display='none';
  document.getElementById('d-meta').innerHTML='<div class="ph">Click a node<br>in the graph</div>';
  renderSource(path, null, null);
  loadGraph(path);
}
function toggleExt(){showExt=!showExt;document.getElementById('ext-btn').classList.toggle('on',showExt);if(curFile)loadGraph(curFile);}

/* ──────── build compound graph data ──────── */
function buildData(filePath) {
  const nids = FILE_ANCHORS[filePath]||[];
  const nset = new Set(nids);

  // 1. class containers
  const classMap = {};          // class_nid → {id,label,methods:[]}
  const orphans  = [];          // method/fn with no class in this file
  const virtualsByOwner = {};
  const placedVirtuals = new Set();

  // Virtual blocks can be nested (condition inside loop inside method). Resolve
  // every block to its nearest real function/method so it is drawn inside that
  // function instead of as a fake top-level function.
  for (const nid of nids) {
    const a=ANCHORS[nid]; if(!a||a.t!=='virtual_block') continue;
    let owner=a.par, guard=0;
    while(owner&&ANCHORS[owner]&&ANCHORS[owner].t==='virtual_block'&&guard++<30)
      owner=ANCHORS[owner].par;
    if(owner&&nset.has(owner)){
      if(!virtualsByOwner[owner]) virtualsByOwner[owner]=[];
      virtualsByOwner[owner].push({
        id:nid, label:virtualLabel(nid,a), type:'virtual_block',
        parent:a.par||owner, depth:virtualDepth(nid)
      });
    }
  }
  for (const nid of nids) {
    const a=ANCHORS[nid]; if(!a) continue;
    if (a.t==='class') classMap[nid]={id:nid,label:shortN(nid),methods:[]};
  }
  // Mark attachable virtual blocks before the rendering pass so JSON key order
  // cannot make a block appear both inside its method and as an orphan node.
  for(const [owner,virtuals] of Object.entries(virtualsByOwner)){
    const a=ANCHORS[owner]; if(!a||a.t!=='method') continue;
    const ci=owner.indexOf('::');
    const sym=ci>=0?owner.slice(ci+2):'';
    const dot=sym.indexOf('.');
    const classNid=dot>=0?owner.slice(0,ci+2)+sym.slice(0,dot):'';
    if(classMap[classNid]) virtuals.forEach(v=>placedVirtuals.add(v.id));
  }
  for (const nid of nids) {
    const a=ANCHORS[nid]; if(!a||a.t==='class') continue;
    let placed=false;
    if(a.t==='method'){
      // nid format: "path/file.py::ClassName.method_name"
      const ci=nid.indexOf('::');
      if(ci>=0){
        const sym=nid.slice(ci+2);
        const dot=sym.indexOf('.');
        if(dot>=0){
          const parentNid=nid.slice(0,ci+2)+sym.slice(0,dot);
          if(classMap[parentNid]){
            const virtuals=(virtualsByOwner[nid]||[]).sort((a,b)=>a.depth-b.depth||a.id.localeCompare(b.id));
            virtuals.forEach(v=>placedVirtuals.add(v.id));
            classMap[parentNid].methods.push({
              id:nid, label:sym.slice(dot+1), type:'method', virtuals
            });
            placed=true;
          }
        }
      }
    }
    if(a.t==='virtual_block'&&placedVirtuals.has(nid)) placed=true;
    if(!placed) orphans.push({id:nid, label:shortN(nid), type:a.t||''});
  }

  // 2. calculate class rect size + method offsets (relative to class center)
  const MR=18, MS=52, VGAP=38, PAD_H=20, PAD_TOP=34;
  const simNodes=[]; // simulation particles
  const simByNid={}; // nid → simNode  (methods map to parent class simNode)

  for (const [cnid,cls] of Object.entries(classMap)) {
    const n=cls.methods.length;
    const cols=Math.max(1,Math.ceil(Math.sqrt(Math.max(n,1))));
    const rows=Math.ceil(Math.max(n,1)/cols);
    let cellW=MS,cellH=MS;
    cls.methods.forEach(m=>{
      const vc=Math.min(3,Math.max(1,m.virtuals.length));
      const vr=Math.ceil(m.virtuals.length/vc);
      m.gw=m.virtuals.length?Math.max(92,vc*VGAP+16):MS;
      m.gh=m.virtuals.length?54+vr*VGAP:MS;
      cellW=Math.max(cellW,m.gw);
      cellH=Math.max(cellH,m.gh);
    });
    const CELL_GAP=14;
    const w=Math.max(130,cols*cellW+Math.max(0,cols-1)*CELL_GAP+PAD_H*2);
    const h=PAD_TOP+rows*cellH+Math.max(0,rows-1)*CELL_GAP+PAD_H;
    cls.methods.forEach((m,i)=>{
      const c=i%cols, r=Math.floor(i/cols);
      const gx=-w/2+PAD_H+c*(cellW+CELL_GAP)+(cellW-m.gw)/2;
      const gy=-h/2+PAD_TOP+r*(cellH+CELL_GAP)+(cellH-m.gh)/2;
      m.gx=gx; m.gy=gy;
      m.ox=gx+m.gw/2;
      m.oy=gy+(m.virtuals.length?24:m.gh/2);
      const vc=Math.min(3,Math.max(1,m.virtuals.length));
      m.virtuals.forEach((v,vi)=>{
        const vr=Math.floor(vi/vc), vv=vi%vc;
        v.ox=m.ox+(vv-(Math.min(vc,m.virtuals.length-vr*vc)-1)/2)*VGAP;
        v.oy=gy+58+vr*VGAP;
      });
    });
    const sn={id:cnid,label:cls.label,type:'class',methods:cls.methods,w,h,x:0,y:0,vx:0,vy:0,ext:false};
    simNodes.push(sn);
    simByNid[cnid]=sn;
    for (const m of cls.methods) {
      simByNid[m.id]=sn; // method → parent simNode
      for(const v of m.virtuals) simByNid[v.id]=sn; // virtual block → owning class
    }
  }

  // orphan functions / methods
  for (const o of orphans) {
    const sn={id:o.id,label:o.label,type:o.type||'function',w:44,h:44,x:0,y:0,vx:0,vy:0,ext:false};
    simNodes.push(sn); simByNid[o.id]=sn;
  }

  // 3. external nodes
  if (showExt) {
    const extRoles=new Map();
    for (const nid of nids) {
      const a=ANCHORS[nid]; if(!a) continue;
      for (const c of (a.callers||[])) {
        if (!nset.has(c) && ANCHORS[c] && extRoles.size<25)
          extRoles.set(c, extRoles.get(c)==='right'?'both':'left');
      }
      for (const c of (a.callees||[])) {
        if (!nset.has(c) && ANCHORS[c] && extRoles.size<25)
          extRoles.set(c, extRoles.get(c)==='left'?'both':'right');
      }
    }
    for (const [eid,side] of extRoles) {
      const a=ANCHORS[eid];
      const sn={id:eid,label:shortN(eid),type:a.t||'',w:26,h:26,x:0,y:0,vx:0,vy:0,ext:true,side};
      simNodes.push(sn); simByNid[eid]=sn;
    }
  }

  // 4. edges  (caller → callee)
  const eSet=new Set(); const edges=[];
  const addE=(s,t)=>{
    if(!simByNid[s]||!simByNid[t]||s===t) return;
    const k=s+'→'+t; if(eSet.has(k)) return; eSet.add(k);
    edges.push({s,t,ext:!nset.has(s)||!nset.has(t)});
  };
  for (const nid of nids) {
    const a=ANCHORS[nid]; if(!a) continue;
    for (const c of (a.callees||[])) addE(nid,c);
    for (const c of (a.callers||[])) addE(c,nid);
  }

  return {simNodes,edges,simByNid};
}

/* ──────── deterministic layered compound graph ──────── */
const CFILL={class:'#1e1535',method:'#1a4a2a',function:'#1a3060',virtual_block:'#4a3218',''  :'#282838'};
const CTXT ={class:'#c586c0',method:'#4ec9b0',function:'#9cdcfe',virtual_block:'#e7b86c',''  :'#aaa'};

class CompoundGraph {
  constructor(svgEl,simNodes,edges,simByNid,onSel){
    this.svg=svgEl; this.sn=simNodes; this.edges=edges;
    this.snByNid=simByNid; this.onSel=onSel;
    this.sel=null; this.drag=null;
    this.tx=0; this.ty=0; this.sc=1; this.cx=0; this.cy=0;
    this._a=1; this._run=false;
    this._setup(); this._layout(); this._fit(); this._render();
  }

  _setup(){
    const svg=this.svg;
    const par=svg.parentElement;
    this.cx=(par?par.clientWidth:1000)/2||500;
    this.cy=(par?par.clientHeight:700)/2||350;
    svg.innerHTML=`<defs>
      <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
        <path d="M0,0 L10,5 L0,10 z" fill="#5a6a9a"/></marker>
      <marker id="are" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto">
        <path d="M0,0 L10,5 L0,10 z" fill="#3a4a6a"/></marker>
    </defs>
    <g id="zg" transform="translate(${this.cx},${this.cy})">
      <g id="bg"></g><g id="eg"></g><g id="ng"></g></g>`;
    this.zg=svg.querySelector('#zg');
    this.bg=svg.querySelector('#bg');
    this.eg=svg.querySelector('#eg');
    this.ng=svg.querySelector('#ng');

    // pan / zoom
    let pan=false,lx=0,ly=0;
    svg.addEventListener('mousedown',e=>{if(!e.target.closest('[data-nid]')){pan=true;lx=e.clientX;ly=e.clientY;}});
    document.addEventListener('mousemove',e=>{
      if(this.drag){
        const r=svg.getBoundingClientRect();
        this.drag.x=(e.clientX-r.left-this.cx-this.tx)/this.sc;
        this.drag.y=(e.clientY-r.top-this.cy-this.ty)/this.sc;
        this.drag.vx=0;this.drag.vy=0;this._render();
      }else if(pan){this.tx+=e.clientX-lx;this.ty+=e.clientY-ly;lx=e.clientX;ly=e.clientY;this._applyT();}
    });
    document.addEventListener('mouseup',()=>{pan=false;this.drag=null;});
    svg.addEventListener('wheel',e=>{
      e.preventDefault();
      this.sc=Math.max(0.05,Math.min(6,this.sc*(e.deltaY>0?0.88:1.14)));
      this._applyT();
    },{passive:false});

    // click delegation
    for(const layer of [this.bg,this.ng]){
      layer.addEventListener('click',e=>{
        const g=e.target.closest('[data-nid]'); if(!g) return; e.stopPropagation();
        this.sel=g.dataset.nid; this._render(); if(this.onSel) this.onSel(this.sel);
      });
      layer.addEventListener('mousedown',e=>{
        const g=e.target.closest('[data-nid]'); if(!g) return;
        e.preventDefault(); e.stopPropagation();
        this.drag=this.snByNid[g.dataset.nid]; // methods map to parent class simNode
      });
    }
    // 点连线 = 跳到子节点（连线的 t 端），与直接点该节点同义。
    this.eg.addEventListener('click',e=>{
      const p=e.target.closest('[data-to]'); if(!p) return; e.stopPropagation();
      const to=p.dataset.to;
      if(!to||!this.snByNid[to]) return;   // 图上没有这个节点就不动
      this.sel=to; this._render(); if(this.onSel) this.onSel(this.sel);
    });
  }

  _applyT(){this.zg.setAttribute('transform',`translate(${this.cx+this.tx},${this.cy+this.ty}) scale(${this.sc})`);}

  _layout(){
    const core=this.sn.filter(n=>!n.ext).sort((a,b)=>a.label.localeCompare(b.label));
    const left=this.sn.filter(n=>n.ext&&(n.side==='left'||n.side==='both')).sort((a,b)=>a.label.localeCompare(b.label));
    const right=this.sn.filter(n=>n.ext&&n.side==='right').sort((a,b)=>a.label.localeCompare(b.label));

    // Collapse method endpoints to their class simulation node, then compute a
    // deterministic caller -> callee rank. This is a graph layout rather than
    // a file-list layout: entry points stay left and dependencies flow right.
    const coreIds=new Set(core.map(n=>n.id));
    const adj=new Map(core.map(n=>[n.id,new Set()]));
    const indeg=new Map(core.map(n=>[n.id,0]));
    for(const e of this.edges){
      const s=this.snByNid[e.s],t=this.snByNid[e.t];
      if(!s||!t||s===t||!coreIds.has(s.id)||!coreIds.has(t.id)) continue;
      if(!adj.get(s.id).has(t.id)){adj.get(s.id).add(t.id);indeg.set(t.id,indeg.get(t.id)+1);}
    }
    const rank=new Map(core.map(n=>[n.id,0]));
    const queue=core.filter(n=>indeg.get(n.id)===0).map(n=>n.id).sort();
    const seen=new Set();
    while(queue.length){
      const id=queue.shift(); seen.add(id);
      for(const to of adj.get(id)){
        rank.set(to,Math.max(rank.get(to),rank.get(id)+1));
        indeg.set(to,indeg.get(to)-1);
        if(indeg.get(to)===0){queue.push(to);queue.sort();}
      }
    }
    // Cycles have no topological root. Keep their members together, but place
    // them after any already-ranked predecessor instead of dropping them.
    for(const n of core) if(!seen.has(n.id)){
      let r=0;
      for(const e of this.edges){
        const s=this.snByNid[e.s],t=this.snByNid[e.t];
        if(s&&t&&t.id===n.id&&seen.has(s.id)) r=Math.max(r,rank.get(s.id)+1);
      }
      rank.set(n.id,r);
    }

    const ranks=new Map();
    for(const n of core){const r=rank.get(n.id)||0;if(!ranks.has(r))ranks.set(r,[]);ranks.get(r).push(n);}
    const rankKeys=[...ranks.keys()].sort((a,b)=>a-b);
    const colGap=250,rowGap=48;
    for(const r of rankKeys){
      const items=ranks.get(r).sort((a,b)=>(a.type==='class'?0:1)-(b.type==='class'?0:1)||a.label.localeCompare(b.label));
      const total=items.reduce((s,n)=>s+n.h,0)+Math.max(0,items.length-1)*rowGap;
      let y=-total/2;
      for(const n of items){
        n.x=(r-(rankKeys.length-1)/2)*colGap;
        n.y=y+n.h/2; y+=n.h+rowGap;
      }
    }

    const coreHalf=Math.max(150,(rankKeys.length-1)*colGap/2+120);
    const placeSide=(items,x)=>{
      const gap=52,total=Math.max(0,(items.length-1)*gap);
      items.forEach((n,i)=>{n.x=x;n.y=i*gap-total/2;});
    };
    placeSide(left,-coreHalf-190);
    placeSide(right,coreHalf+190);
    for(const n of this.sn){n.vx=0;n.vy=0;}
  }

  _fit(){
    if(!this.sn.length){this.sc=1;this.tx=0;this.ty=0;this._applyT();return;}
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    for(const n of this.sn){
      minX=Math.min(minX,n.x-n.w/2); maxX=Math.max(maxX,n.x+n.w/2);
      minY=Math.min(minY,n.y-n.h/2); maxY=Math.max(maxY,n.y+n.h/2);
    }
    const par=this.svg.parentElement;
    const vw=(par?par.clientWidth:1000)||1000, vh=(par?par.clientHeight:700)||700;
    const bw=Math.max(1,maxX-minX), bh=Math.max(1,maxY-minY);
    this.sc=Math.max(.12,Math.min(1.35,(vw-90)/bw,(vh-90)/bh));
    this.tx=-((minX+maxX)/2)*this.sc;
    this.ty=-((minY+maxY)/2)*this.sc;
    this._applyT();
  }

  _snR(n){return Math.sqrt(n.w*n.w+n.h*n.h)/2;}

  // world position of a nid (for edge drawing)
  _pos(nid){
    const sn=this.snByNid[nid]; if(!sn) return null;
    // Only an in-file class is a compound container. External class anchors
    // are intentionally rendered as ordinary external circles and therefore
    // have no `methods` collection.
    if(sn.type==='class'&&!sn.ext){
      const methods=sn.methods||[];
      const m=methods.find(m=>m.id===nid);
      if(m) return {x:sn.x+m.ox, y:sn.y+m.oy, r:18};
      for(const method of methods){
        const v=method.virtuals.find(v=>v.id===nid);
        if(v) return {x:sn.x+v.ox, y:sn.y+v.oy, r:15};
      }
      return {x:sn.x, y:sn.y, r:this._snR(sn)};
    }
    return {x:sn.x, y:sn.y, r:sn.ext?12:20};
  }

  _tick(){
    if(!this._run) return;
    if(this._a<0.003){this._run=false;this._render();return;}
    this._a*=0.955;
    const a=this._a;

    // repulsion between sim nodes
    for(let i=0;i<this.sn.length;i++) for(let j=i+1;j<this.sn.length;j++){
      const u=this.sn[i],v=this.sn[j];
      const dx=v.x-u.x,dy=v.y-u.y;
      const d2=dx*dx+dy*dy+1,d=Math.sqrt(d2);
      const minD=this._snR(u)+this._snR(v)+50;
      const rep=(u.ext||v.ext)?3000:9000;
      const extra=d<minD?3:1;
      const f=rep*extra/d2*a;
      u.vx-=f*dx/d;u.vy-=f*dy/d;
      v.vx+=f*dx/d;v.vy+=f*dy/d;
    }

    // edge springs (act on sim nodes, not individual nids)
    for(const e of this.edges){
      const sp=this._pos(e.s),tp=this._pos(e.t); if(!sp||!tp) continue;
      const ssn=this.snByNid[e.s],tsn=this.snByNid[e.t];
      if(!ssn||!tsn||ssn===tsn) continue;
      const dx=tp.x-sp.x,dy=tp.y-sp.y,d=Math.sqrt(dx*dx+dy*dy)+1;
      const ideal=e.ext?260:140;
      const f=(d-ideal)*0.025*a;
      ssn.vx+=f*dx/d;ssn.vy+=f*dy/d;
      tsn.vx-=f*dx/d;tsn.vy-=f*dy/d;
    }

    for(const n of this.sn){
      if(n===this.drag){n.vx=0;n.vy=0;continue;}
      n.vx*=0.78;n.vy*=0.78;n.x+=n.vx;n.y+=n.vy;
    }
    this._render();
    requestAnimationFrame(()=>this._tick());
  }

  _go(){this._run=true;requestAnimationFrame(()=>this._tick());}
  stop(){this._run=false;}

  _render(){
    const sel=this.sel;

    /* edges */
    let eh='';
    for(const e of this.edges){
      const sp=this._pos(e.s),tp=this._pos(e.t); if(!sp||!tp) continue;
      const dx=tp.x-sp.x,dy=tp.y-sp.y,d=Math.sqrt(dx*dx+dy*dy)||1;
      const x1=sp.x+dx/d*sp.r, y1=sp.y+dy/d*sp.r;
      const x2=tp.x-dx/d*(tp.r+5), y2=tp.y-dy/d*(tp.r+5);
      const mx=(x1+x2)/2-dy/d*14, my=(y1+y2)/2+dx/d*14;
      const hl=sel&&(e.s===sel||e.t===sel);
      const col=hl?(e.ext?'#607090':'#7080c0'):(e.ext?'#2a3a50':'#384870');
      const sw=hl?2:1.2;
      const dash=e.ext?'stroke-dasharray="5 3"':'';
      const mk=e.ext?'are':'ar';
      const op=hl?1:0.55;
      // 连线可点：带着两端 id 落进 SVG，点击即跳到子节点（连线的 t 端）。
      // 细线只有 1.2px，命中区靠一条透明加粗的同路径兜住。
      const pathD=`M${x1.toFixed(1)},${y1.toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
      eh+=`<path data-from="${escA(e.s)}" data-to="${escA(e.t)}" d="${pathD}" fill="none" stroke="transparent" stroke-width="10" style="cursor:pointer"><title>${escX(shortN(e.s))} → ${escX(shortN(e.t))}</title></path>`;
      eh+=`<path d="${pathD}" fill="none" stroke="${col}" stroke-width="${sw}" ${dash} marker-end="url(#${mk})" opacity="${op}" pointer-events="none"/>`;
    }
    this.eg.innerHTML=eh;

    /* nodes */
    let bh='',nh='';
    for(const sn of this.sn){
      if(sn.type==='class'&&!sn.ext){
        const hw=sn.w/2,hh=sn.h/2;
        const isSel=sn.id===sel;
        // All large container rectangles live in the bottom layer. Edges are
        // rendered above them, so internal method/virtual-block links stay visible.
        bh+=`<g data-nid="${escA(sn.id)}" transform="translate(${sn.x.toFixed(1)},${sn.y.toFixed(1)})" style="cursor:pointer">`;
        bh+=`<rect x="${-hw}" y="${-hh}" width="${sn.w}" height="${sn.h}" rx="8" fill="${CFILL.class}" stroke="${isSel?'#fff':'#5a3a9a'}" stroke-width="${isSel?2:1}"/>`;
        bh+=`<line x1="${-hw+8}" y1="${-hh+26}" x2="${hw-8}" y2="${-hh+26}" stroke="#3a2a5a" stroke-width="1"/>`;
        for(const m of sn.methods){
          if(m.virtuals.length){
            bh+=`<rect data-nid="${escA(m.id)}" x="${m.gx.toFixed(1)}" y="${m.gy.toFixed(1)}" width="${m.gw}" height="${m.gh}" rx="8" fill="#17261e" stroke="#315944" stroke-width="1"/>`;
          }
        }
        bh+=`</g>`;
        nh+=`<g transform="translate(${sn.x.toFixed(1)},${sn.y.toFixed(1)})">`;
        // Labels and small nodes stay in the foreground layer.
        /* 名字不截断：放不下就折行。一个被切成 factory#14.tre… 的名字，
           既不能读也不能搜，省下的那点宽度不值这个。 */
        const clines=wrapLabel(sn.label, Math.max(12, Math.floor(sn.w/7.2)), 3);
        clines.forEach((ln,li)=>{
          nh+=`<text data-nid="${escA(sn.id)}" x="0" y="${-hh+16+li*13}" text-anchor="middle" fill="#c586c0" font-size="12" font-family="Consolas,monospace" font-weight="bold" style="cursor:pointer">${escX(ln)}</text>`;
        });
        // method circles inside
        for(const m of sn.methods){
          const mSel=m.id===sel;
          const mf=mSel?'#2a6a4a':(CFILL[m.type]||CFILL['']);
          const mt=CTXT[m.type]||CTXT[''];
          const mlines=wrapLabel(m.label, 11, 2);
          nh+=`<g data-nid="${escA(m.id)}" transform="translate(${m.ox.toFixed(1)},${m.oy.toFixed(1)})" style="cursor:pointer">`;
          nh+=`<circle r="18" fill="${mf}" stroke="${mSel?'#fff':'none'}" stroke-width="${mSel?2:0}"/>`;
          nh+=`<title>${escX(m.id)}</title>`;
          mlines.forEach((ln,li)=>{
            const dy = 22 + li*10 + (mlines.length===1?-1:0);
            nh+=`<text text-anchor="middle" y="${dy}" fill="${mt}" font-size="9" font-family="Consolas,monospace" pointer-events="none">${escX(ln)}</text>`;
          });
          nh+=`</g>`;
          for(const v of m.virtuals){
            const vSel=v.id===sel;
            nh+=`<g data-nid="${escA(v.id)}" transform="translate(${v.ox.toFixed(1)},${v.oy.toFixed(1)})" style="cursor:pointer">`;
            nh+=`<rect x="-16" y="-12" width="32" height="24" rx="6" fill="${vSel?'#76522b':CFILL.virtual_block}" stroke="${vSel?'#fff':'#8a6334'}" stroke-width="${vSel?2:1}"/>`;
            nh+=`<title>${escX(v.id)}</title>`;
            nh+=`<text text-anchor="middle" dominant-baseline="central" fill="${CTXT.virtual_block}" font-size="8" font-family="Consolas,monospace" pointer-events="none">${escX(v.label)}</text>`;
            nh+=`</g>`;
          }
        }
        nh+=`</g>`;
      } else if(!sn.ext){
        // standalone function
        const isSel=sn.id===sel;
        const r=20;
        nh+=`<g data-nid="${escA(sn.id)}" transform="translate(${sn.x.toFixed(1)},${sn.y.toFixed(1)})" style="cursor:pointer">`;
        nh+=`<circle r="${r}" fill="${isSel?'#2a4a90':CFILL[sn.type]||CFILL['']}" stroke="${isSel?'#fff':'none'}" stroke-width="${isSel?2:0}"/>`;
        /* 名字挪到圆下面折行。塞在 r=20 的圆里就只剩九个字符，
           generate_experiment_report 会变成 generate_… —— 读不出也搜不到。 */
        wrapLabel(sn.label, 14, 3).forEach((ln,li)=>{
          nh+=`<text text-anchor="middle" y="${r+13+li*11}" fill="${CTXT[sn.type]||CTXT['']}" font-size="10" font-family="Consolas,monospace" pointer-events="none">${escX(ln)}</text>`;
        });
        nh+=`</g>`;
      } else {
        // external node — dashed circle
        const isSel=sn.id===sel;
        const r=12;
        nh+=`<g data-nid="${escA(sn.id)}" transform="translate(${sn.x.toFixed(1)},${sn.y.toFixed(1)})" style="cursor:pointer" opacity="0.75">`;
        nh+=`<circle r="${r}" fill="#1a2030" stroke="${isSel?'#fff':'#3a5a7a'}" stroke-width="${isSel?2:1}" stroke-dasharray="3 2"/>`;
        wrapLabel(sn.label, 13, 2).forEach((ln,li)=>{
          nh+=`<text text-anchor="middle" y="${r+11+li*10}" fill="#3a6080" font-size="9" font-family="Consolas,monospace" pointer-events="none">${escX(ln)}</text>`;
        });
        nh+=`</g>`;
      }
    }
    this.bg.innerHTML=bh;
    this.ng.innerHTML=nh;
  }
}

/* ──────── load graph ──────── */
function loadGraph(path){
  if(CG){CG.stop();CG=null;}
  const {simNodes,edges,simByNid}=buildData(path);
  CG=new CompoundGraph(document.getElementById('gsvg'),simNodes,edges,simByNid,nid=>renderDetail(nid));
}

/* ──────── detail panel ──────── */
function renderDetail(nid){
  const a=ANCHORS[nid]; if(!a) return;
  const name=nid.split('::').slice(1).join('::')||nid;
  const fp=nid.split('::')[0];
  const inFile=new Set(FILE_ANCHORS[fp]||[]);
  let h=`<div class="dn">${esc(name)}</div>`;
  h+=`<div class="dm">${esc(fp)} &middot; ${esc(a.t||'?')}`;
  if(a.ls)h+=` &middot; L${a.ls}–${a.le}`;
  if(a.drift&&a.drift!=='ok')h+=` &middot; <span style="color:#f85149">drift:${esc(a.drift)}</span>`;
  h+=`</div>`;
  if(a.desc)h+=`<div class="ds"><h4>Description</h4><p>${esc(a.desc)}</p></div>`;
  /* 参数存的是 {name, type} 对象，join 只会调 toString，于是每一项都成了
     [object Object]。有类型就写「名字: 类型」，没有就只写名字。 */
  const io=xs=>xs.map(x=>{
    if(x===null||x===undefined) return '';
    if(typeof x!=='object') return String(x);
    if(x.type) return x.name+': '+x.type;
    return x.name===undefined?JSON.stringify(x):String(x.name);
  }).filter(Boolean).join(', ');
  if(a.ins&&a.ins.length)h+=`<div class="ds"><h4>Inputs</h4><p>${esc(io(a.ins))}</p></div>`;
  if(a.outs&&a.outs.length)h+=`<div class="ds"><h4>Outputs</h4><p>${esc(io(a.outs))}</p></div>`;
  if(a.callers.length){
    h+=`<div class="ds"><h4>Called by (${a.callers.length})</h4><div>`;
    for(const c of a.callers){const cls=inFile.has(c)?'ci':'ce';h+=`<span class="chip ${cls}" data-nid="${escA(c)}" title="${esc(c)}">${esc(shortN(c))}</span>`;}
    h+=`</div></div>`;
  }
  if(a.callees.length){
    h+=`<div class="ds"><h4>Calls (${a.callees.length})</h4><div>`;
    for(const c of a.callees){const cls=inFile.has(c)?'ci':'ce';h+=`<span class="chip ${cls}" data-nid="${escA(c)}" title="${esc(c)}">${esc(shortN(c))}</span>`;}
    h+=`</div></div>`;
  }
  document.getElementById('d-meta').innerHTML=h;
  renderSource(fp, a.ls, a.le);
}

document.getElementById('db').addEventListener('click',e=>{
  const chip=e.target.closest('.chip[data-nid]'); if(!chip) return;
  const nid=chip.dataset.nid;
  const fp=nid.split('::')[0];
  if(fp!==curFile){
    const el=document.querySelector('.fi[data-path="'+fp+'"]');
    if(el){expandUp(el);selectFile(fp,el);el.scrollIntoView({block:'nearest'});return;}
  }
  if(CG){const sn=CG.snByNid[nid];if(sn){CG.sel=nid;CG._render();}renderDetail(nid);}
});

/* ──────── utils ──────── */
function shortN(nid){const p=nid.split('::');return p[p.length-1]||nid;}
function virtualDepth(nid){return (nid.match(/#(?:loop|cond|try|with|match):/g)||[]).length;}
function virtualLabel(nid,a){
  const kind=a.vk==='condition'?'if':(a.vk||'block');
  return kind+'@'+(a.ls||'?');
}
/* 按可用宽度折行，不加省略号。宁可多占一行，也不给一个读不出来的名字。 */
function wrapLabel(text, per, maxLines){
  const t=String(text||'');
  if(t.length<=per) return [t];
  const out=[];
  let rest=t;
  while(rest.length>0 && out.length<maxLines){
    if(out.length===maxLines-1){ out.push(rest); break; }
    let cut=per;
    const seg=rest.slice(0, per+1);
    const brk=Math.max(seg.lastIndexOf('.'), seg.lastIndexOf('_'), seg.lastIndexOf('#'));
    if(brk>per*0.5) cut=brk+1;
    out.push(rest.slice(0,cut));
    rest=rest.slice(cut);
  }
  return out;
}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function escX(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function escA(s){return String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;');}
function expandUp(el){let p=el.parentElement;while(p&&p.id!=='file-tree'){if(p.classList.contains('dc')){p.classList.add('open');const l=p.previousElementSibling;if(l){const c=l.querySelector('.ca');if(c)c.textContent='▼';}}p=p.parentElement;}}

/* ──────── init ──────── */
renderTree(FILE_TREE,document.getElementById('file-tree'),'');
if (typeof PAGE_SELF !== 'undefined' && PAGE_SELF) {
  const back=document.createElement('div');
  back.className='dl'; back.style.color='#4ea1ff'; back.textContent='← 全部文件';
  back.onclick=goHome;
  const host=document.getElementById('file-tree');
  host.insertBefore(back, host.firstChild);
  const self=[...document.querySelectorAll('.fi')].find(e=>e.dataset.path===PAGE_SELF);
  if (self) { expandUp(self); selectFile(PAGE_SELF, self); }
}
if(Object.keys(FILE_TREE).length===1){const f=document.querySelector('.dl');if(f)toggleD(f);}
</script>
</body>
</html>
"""
