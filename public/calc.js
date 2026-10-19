(function(g){const r=x=>Math.round((x+Number.EPSILON)*100)/100,n=x=>+x||0;
function item(i){const net=Math.max(0,n(i.gross)-n(i.stone))*n(i.qty||1),metal=r(net*n(i.rate));
let mk=i.mkType==='percent'?metal*n(i.mk)/100:i.mkType==='item'?n(i.mk)*n(i.qty||1):n(i.mk)*net;mk=r(mk);
const w=r(metal*n(i.wp)/100),b1=metal+w,b2=mk+Math.max(0,n(i.extra)),base=b1+b2,f=base>0?Math.max(0,base-Math.max(0,n(i.disc)))/base:0,t1=r(b1*f),t2=r(b2*f);
let g1,g2;if(i.gstMode==='split'){g1=r(t1*n(i.tax)/100);g2=r(t2*n(i.mtax)/100)}else{g1=r((t1+t2)*n(i.tax)/100);g2=0}
const tx=r(t1+t2),gst=r(g1+g2);return{net:r(net),metal,mk,w,taxable:tx,gst,gstm:g1,gstk:g2,total:r(tx+gst)}}
function bill(b){const L=(b.items||[]).map(item),t=r(L.reduce((s,x)=>s+x.total,0)),g=r(L.reduce((s,x)=>s+x.gst,0)),gm=r(L.reduce((s,x)=>s+x.gstm,0)),gk=r(L.reduce((s,x)=>s+x.gstk,0));
return{lines:L,gst:g,gstm:gm,gstk:gk,total:t,balance:r(t-n(b.paid))}}
g.calc={item,bill};if(typeof module!=='undefined')module.exports=g.calc})(typeof window!=='undefined'?window:globalThis);
