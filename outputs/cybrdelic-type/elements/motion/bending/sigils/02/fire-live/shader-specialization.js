// Source transforms for our generated shaders, before driver compilation.
// Fail closed on changed syntax. No runtime values or shader arithmetic change.
function close(code,open,left,right){
 let depth=1,i=open+1;
 for(;i<code.length&&depth;i++){if(code[i]===left)depth++;else if(code[i]===right)depth--;}
 if(depth)throw Error('Unbalanced generated shader');return i;
}
function functions(code){
 code=code.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g,c=>c.replace(/[^\n]/g,' '));
 const result=[];const re=/\bfn\s+(\w+)\s*\(/g;let match;
 while((match=re.exec(code))){
  const argsEnd=close(code,code.indexOf('(',match.index),'(',')');
  const open=code.indexOf('{',argsEnd);const end=close(code,open,'{','}');
  result.push({name:match[1],start:match.index,end,open,args:code.slice(match.index,argsEnd),body:code.slice(open+1,end-1)});
  re.lastIndex=end;
 }return result;
}
export function pruneShaderFunctions(code,roots=['main']){
 const list=functions(code),byName=new Map(list.map(f=>[f.name,f]));
 const live=new Set(),queue=[...roots];
 while(queue.length){const name=queue.pop();if(live.has(name))continue;
  const f=byName.get(name);if(!f)throw Error('Shader entry missing: '+name);live.add(name);
  for(const call of f.body.matchAll(/\b(\w+)\s*\(/g)){if(byName.has(call[1])&&!live.has(call[1]))queue.push(call[1]);}
 }
 for(const f of list.reverse()){if(!live.has(f.name))code=code.slice(0,f.start)+code.slice(f.end);}
 return code;
}
function constantCondition(condition,kind){
 if(!/^[\s\d.kind<>=!&|().+\-]+$/.test(condition)||/\b(?!kind\b)[a-z]+\b/.test(condition))return null;
 const numeric=condition.replace(/\bkind\b/g,String(kind));
 // The whitelist accepts numeric expressions only, from authored source.
 return Boolean(Function('return ('+numeric+');')());
}
function returnsAtTopLevel(body){
 let depth=0;
 for(let i=0;i<body.length;i++){
  if(body[i]==='{')depth++;else if(body[i]==='}')depth--;
  if(depth===0&&/^return\b/.test(body.slice(i)))return true;
 }return false;
}
function specializeBody(body,kind){
 let cursor=0;
 while(cursor<body.length){
  const match=/\bif\s*\(/g;match.lastIndex=cursor;const found=match.exec(body);if(!found)break;
  const start=found.index,open=body.indexOf('(',start),conditionEnd=close(body,open,'(',')');
  const condition=body.slice(open+1,conditionEnd-1),known=constantCondition(condition,kind);
  let block=conditionEnd;while(/\s/.test(body[block]))block++;
  if(known===null||body[block]!=='{'){cursor=conditionEnd;continue;}
  const end=close(body,block,'{','}');let after=end;while(/\s/.test(body[after]))after++;
  if(body.slice(after,after+4)==='else')throw Error('Static power branch now has else; update specialization');
  const contents=body.slice(block+1,end-1);
  let depth=0;for(const c of body.slice(0,start)){if(c==='{')depth++;else if(c==='}')depth--;}
  if(known&&depth===0&&returnsAtTopLevel(contents)){body=body.slice(0,start)+contents;break;}
  body=body.slice(0,start)+(known?contents:'')+body.slice(end);cursor=start;
 }
 return body.replace(/\bkind\b/g,Number(kind).toFixed(1));
}
export function specializePowerSource(source,kind,additionalRoots=[]){
 source=source.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g,'');
 if(!Number.isInteger(kind)||kind<1||kind>24)throw Error('Unknown power specialization');
 for(const f of functions(source).reverse()){
  if(!/\bkind\s*:\s*f32\b/.test(f.args))continue;
  source=source.slice(0,f.open+1)+specializeBody(f.body,kind)+source.slice(f.end-1);
 }
 return pruneShaderFunctions(source,['powerCastSource','powerCastSupport','powerCastAcceleration','powerCastExpansion',...additionalRoots]);
}
