// CPU-only Float32 oracle. Every arithmetic operator rounds separately.
const f=Math.fround,add=(a,b)=>f(a+b),sub=(a,b)=>f(a-b),mul=(a,b)=>f(a*b),div=(a,b)=>f(a/b);
export function hancockReference(left,center,right,uLeft,uRight,sigma,side){
 const a=mul(2,sub(center,left)),b=mul(.5,sub(right,left)),d=mul(2,sub(right,center));
 const slope=mul(mul(mul(.25,add(Math.sign(a),Math.sign(b))),Math.abs(add(Math.sign(a),Math.sign(d)))),Math.min(Math.abs(a),Math.min(Math.abs(b),Math.abs(d))));
 const base=mul(center,sub(1,mul(mul(.5,sigma),sub(uRight,uLeft)))),drift=mul(mul(.25,sigma),add(uRight,uLeft));
 const leftValue=add(base,mul(sub(-.5,drift),slope)),rightValue=add(base,mul(sub(.5,drift),slope)),lower=Math.min(leftValue,rightValue);
 const theta=lower<0?mul(Math.min(1,div(base,sub(base,lower))),sub(1,mul(8,2**-23))):1;
 return add(base,mul(theta,mul(sub(mul(side,.5),drift),slope)));
}
// Interpret the actual production scalar GLSL's expressions as Float32. This
// verifies operation order on CPU; native compiler contraction still needs GPU.
export function interpretHancockGLSL(source){
 const statements=source.slice(source.indexOf('{')+1,source.lastIndexOf('}')).split(';').map(s=>s.trim()).filter(Boolean);
 function expression(text){
  const tokens=text.match(/(?:\d*\.\d+|\d+\.?)(?:e[-+]?\d+)?|[A-Za-z_]\w*|[()+*/?,:<-]/g);let pos=0;
  const precedence={'<':0,'+':1,'-':1,'*':2,'/':2};
  const atom=()=>{const token=tokens[pos++];if(token==='-')return {op:'neg',a:atom()};if(token==='('){const node=parse();if(tokens[pos++]!==')')throw Error('GLSL closing parenthesis');return node;}if(/^\d|^\./.test(token))return {value:f(Number(token))};if(tokens[pos]==='('){pos++;const args=[parse()];while(tokens[pos]===','){pos++;args.push(parse());}if(tokens[pos++]!==')')throw Error('GLSL call parenthesis');return {call:token,args};}return {name:token};};
  const binary=(level=0)=>{let left=atom();while(Object.hasOwn(precedence,tokens[pos])&&precedence[tokens[pos]]>=level){const op=tokens[pos++],right=binary(precedence[op]+1);left={op,a:left,b:right};}return left;};
  const parse=()=>{let node=binary();if(tokens[pos]==='?'){pos++;const yes=parse();if(tokens[pos++]!==':')throw Error('GLSL conditional');node={op:'conditional',a:node,b:yes,c:parse()};}return node;};
  const node=parse();if(pos!==tokens.length)throw Error('Unsupported GLSL expression: '+text);return node;
 }
 const compiled=statements.map(s=>s.startsWith('return ')?{result:expression(s.slice(7))}:(()=>{const m=s.match(/^float (\w+)=(.*)$/s);if(!m)throw Error('Unsupported GLSL statement: '+s);return {name:m[1],expression:expression(m[2])};})());
 const evaluate=(node,scope)=>{if(Object.hasOwn(node,'value'))return node.value;if(node.name)return scope[node.name];if(node.call){const values=node.args.map(a=>evaluate(a,scope)),fn={sign:Math.sign,abs:Math.abs,min:Math.min,max:Math.max}[node.call];if(!fn)throw Error('Unsupported GLSL function');return f(fn(...values));}const a=evaluate(node.a,scope);if(node.op==='neg')return f(-a);if(node.op==='conditional')return evaluate(a?node.b:node.c,scope);const b=evaluate(node.b,scope);return node.op==='<'?a<b:({'+' :add,'-':sub,'*':mul,'/':div}[node.op])(a,b);};
 return (...args)=>{const scope=Object.fromEntries(['left','center','right','uLeft','uRight','sigma','side'].map((name,i)=>[name,f(args[i])]));for(const row of compiled){if(row.result)return evaluate(row.result,scope);scope[row.name]=evaluate(row.expression,scope);}throw Error('GLSL return missing');};
}
export function transportReference(input,velocity,n,delta,schedule,{periodic=false,floor=0,kernel=hancockReference,onSweep}={}){
 const size=n.reduce((a,b)=>a*b),h=n.map((x,a)=>f(1/(a===2?x-1:x))),idx=c=>(c[2]*n[1]+c[1])*n[0]+c[0],cells=[];
 for(let z=0;z<n[2];z++)for(let y=0;y<n[1];y++)for(let x=0;x<n[0];x++)cells.push([x,y,z]);
 const offset=(c,a,d)=>c.map((x,i)=>x+(a===i?d:0)),valid=c=>c.every((x,i)=>x>=0&&x<n[i]),wrap=c=>c.map((x,i)=>(x+n[i])%n[i]);
 const cell=c=>periodic?wrap(c):c,width=(c,a)=>mul(h[a],!periodic&&a===2&&(c[2]===0||c[2]===n[2]-1)?.5:1);
 const v=(c,a)=>{c=periodic?wrap(c):c.map((x,i)=>Math.max(0,Math.min(n[i]-1,x)));return !periodic&&(c[1]<floor||a===1&&c[1]===floor)?0:f(velocity[a][idx(c)]);};
 const rates=[0,0,0];for(const c of cells)for(let a=0;a<3;a++){const l=v(c,a),r=v(offset(c,a,1),a);rates[a]=Math.max(rates[a],div(Math.max(Math.abs(l),Math.abs(r),add(Math.max(r,0),Math.max(-l,0))),width(c,a)));}
 const sweeps=schedule(delta,rates);let state=Float32Array.from(input),boundaryLoss=0,minFace=Infinity,minCell=Infinity;
 for(const sweep of sweeps){const a=sweep.axis,step=sweep.delta;for(let k=0;k<sweep.steps;k++){
  const at=c=>{c=cell(c);return valid(c)?state[idx(c)]:0;};
  const flux=c=>{const u=v(c,a),donor=cell(u>=0?offset(c,a,-1):c);if(!valid(donor))return 0;const q=kernel(at(offset(donor,a,-1)),at(donor),at(offset(donor,a,1)),v(donor,a),v(offset(donor,a,1),a),div(step,width(donor,a)),u>=0?1:-1);minFace=Math.min(minFace,q);return mul(u,q);};
  onSweep?.({state,axis:a,delta:step,flux});
  const next=new Float32Array(size);for(const c of cells){const left=flux(c),right=flux(offset(c,a,1)),i=idx(c);next[i]=sub(state[i],mul(div(step,width(c,a)),sub(right,left)));minCell=Math.min(minCell,next[i]);if(!periodic){const area=h.reduce((s,x,b)=>s*(b===a?1:x),1)*(!periodic&&a!==2&&(c[2]===0||c[2]===n[2]-1)?.5:1);if(c[a]===0)boundaryLoss-=step*left*area;if(c[a]===n[a]-1)boundaryLoss+=step*right*area;}}state=next;
 }}return {q:state,rates,sweeps,boundaryLoss,minFace,minCell};
}
export function inventory(q,n,{periodic=false}={}){let sum=0;const volume=1/n[0]/n[1]/(n[2]-1);for(let i=0;i<q.length;i++){const z=Math.floor(i/n[0]/n[1]);sum+=q[i]*volume*(!periodic&&(z===0||z===n[2]-1)?.5:1);}return sum;}
