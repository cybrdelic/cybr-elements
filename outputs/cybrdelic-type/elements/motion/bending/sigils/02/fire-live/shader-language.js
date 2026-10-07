// Translate the deliberately small, typed WGSL helper subset shared with WebGL.
export function shaderFunctionsToGLSL(source){return source
 .replace(/fn (\w+)\(([^)]*)\)->(vec[234]f|f32|bool)\{/g,(_,name,args,type)=>
  (type==='f32'?'float':type.replace('f',''))+' '+name+'('+args.split(',').map(a=>a.trim().replace(/(\w+):(vec[234]f|f32)/,(_,n,t)=>(t==='f32'?'float':t.replace('f',''))+' '+n)).join(',')+'){')
 .replace(/\b(?:let|var) (\w+):(vec[234]f|f32)=/g,(_,name,type)=>(type==='f32'?'float':type.replace('f',''))+' '+name+'=')
 .replace(/\bvec([234])f\b/g,'vec$1')
 .replace(/all\(abs\(q\)<vec3\(([^)]+)\)\)/g,'all(lessThan(abs(q),vec3($1)))')
 .replace(/atan2\(/g,'atan(');}
