import {mkdirSync,readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root=fileURLToPath(new URL('../',import.meta.url));
// The retained subprocess protocol fixture writes only tiny fake-worker files.
// A fresh checkout has no generated QA directory yet.
mkdirSync(path.join(root,'work/adaptive-volume-qa'),{recursive:true});
const suites=readdirSync(path.join(root,'tools/fire-studio'))
  .filter(name=>name.endsWith('.test.mjs')).sort()
  .map(name=>path.join(root,'tools/fire-studio',name));
suites.push(path.join(root,'tools/fire-browser/test.mjs'));
let failed=0;
for(const suite of suites){
  const result=spawnSync(process.execPath,[suite],{cwd:root,encoding:'utf8'});
  const lines=(result.stdout||'').split('\n').filter(line=>/^# (tests|pass|fail) /.test(line));
  console.log(path.relative(root,suite),...lines);
  if(result.status!==0){failed++;console.error(result.stdout||'',result.stderr||'');}
}
console.log(JSON.stringify({suites:suites.length,failed,scope:'Node CPU fixtures; no real GPU adapter or browser launched'}));
process.exitCode=failed?1:0;
