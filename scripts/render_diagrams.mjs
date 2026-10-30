import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url), sharp=require('sharp');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const folder=path.join(root,'diagrams');
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const colors={person:['#EDF0F4','#334155'],external:['#F2F3F5','#526276'],container:['#E9F1FA','#194A7B'],store:['#E8F3EF','#22624B']};
for(const d of JSON.parse(fs.readFileSync(path.join(folder,'diagrams.json'),'utf8'))){
 const height=d.height||Math.max(...d.nodes.map(n=>n.y+n.h),...d.edges.flatMap(e=>e.points.map(p=>p[1])),...d.edges.map(e=>e.ly+12))+35, width=1200;
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="${width}" height="${height}" fill="white"/><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#526276"/></marker></defs>`;
 let cells='<mxCell id="0"/><mxCell id="1" parent="0"/>';
 for(const e of d.edges){
  svg+=`<path d="${e.points.map(([x,y],i)=>(i?'L':'M')+x+','+y).join(' ')}" fill="none" stroke="#526276" stroke-width="2" ${e.dashed?'stroke-dasharray="7 5"':''} marker-end="url(#arrow)"/>`;
  const w=Math.max(100,e.label.length*8.1);
  svg+=`<rect x="${e.lx-w/2}" y="${e.ly-18}" width="${w}" height="25" fill="white"/><text x="${e.lx}" y="${e.ly}" text-anchor="middle" font-family="Arial" font-size="16" fill="#334155">${escape(e.label)}</text>`;
  const pts=e.points.slice(1,-1).map(([x,y])=>`<mxPoint x="${x}" y="${y}"/>`).join('');
  cells+=`<mxCell id="edge-${cells.length}" value="${escape(e.label)}" edge="1" parent="1" source="${e.a}" target="${e.b}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;fontSize=16;strokeColor=#526276;${e.dashed?'dashed=1;':''}"><mxGeometry relative="1" as="geometry"><Array as="points">${pts}</Array></mxGeometry></mxCell>`;
 }
 for(const n of d.nodes){
  const [fill,stroke]=colors[n.kind]||colors.container;
  svg+=`<rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="6" fill="${fill}" stroke="${stroke}" stroke-width="2"/><text x="${n.x+n.w/2}" y="${n.y+34}" text-anchor="middle" font-family="Arial" font-weight="bold" font-size="20" fill="${stroke}">${escape(n.title)}</text><text x="${n.x+n.w/2}" y="${n.y+67}" text-anchor="middle" font-family="Arial" font-size="15" fill="${stroke}">${escape(n.detail)}</text>`;
  cells+=`<mxCell id="${n.id}" value="${escape(n.title+'<br>'+n.detail)}" vertex="1" parent="1" style="rounded=1;whiteSpace=wrap;html=1;fontSize=20;fillColor=${fill};strokeColor=${stroke};"><mxGeometry x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" as="geometry"/></mxCell>`;
 }
 svg+='</svg>';
 fs.writeFileSync(path.join(folder,d.slug+'.svg'),svg);
 await sharp(Buffer.from(svg),{density:180}).png().toFile(path.join(folder,d.slug+'.png'));
 fs.writeFileSync(path.join(folder,d.slug+'.drawio'),`<mxfile host="app.diagrams.net"><diagram name="${escape(d.title)}"><mxGraphModel page="1" pageWidth="1200" pageHeight="${height}"><root>${cells}</root></mxGraphModel></diagram></mxfile>`);
 console.log(d.slug);
}
