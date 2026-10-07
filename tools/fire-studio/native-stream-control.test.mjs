// CPU-only subprocess protocol tests. These workers never create an adapter,
// shader, GPU resource, or simulation/rendering acceptance report.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {NativeVolumeStream} from './native-volume-stream.mjs';

const root=fileURLToPath(new URL('../../',import.meta.url));
const folder=fs.mkdtempSync(path.join(root,'work/adaptive-volume-qa/control-cpu-'));
function fixture(name,code){const file=path.join(folder,name+'.mjs');fs.writeFileSync(file,code);return file;}
test('numerical-rejection exit retains the final host-success acknowledgement',async()=>{
  const script=fixture('numerical-rejection',`
process.stdout.write(JSON.stringify({kind:'ready',protocolOnly:true})+'\\n');
let text='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>{
 text+=chunk;let end;while((end=text.indexOf('\\n'))>=0){
  const message=JSON.parse(text.slice(0,end));text=text.slice(end+1);
  if(message.kind==='finish'){
   process.stdout.write(JSON.stringify({kind:'finished',pass:false,productionHostPass:true,numericalPass:false})+'\\n');
   process.exitCode=1;
  }
 }
});`);
  const stream=new NativeVolumeStream({python:process.execPath,script,recording:folder,output:'cpu-protocol-only'});
  await stream.start();const result=await stream.finish();
  assert.equal(result.pass,false);assert.equal(result.productionHostPass,true);assert.equal(result.numericalPass,false);
  assert.equal((await stream.exit).code,1);
});
test('clean worker EOF without an acknowledgement rejects immediately',async()=>{
  const script=fixture('missing-ack','process.exitCode=0;');
  const stream=new NativeVolumeStream({python:process.execPath,script,recording:folder,output:'cpu-protocol-only'});
  await assert.rejects(stream.start(),/closed before its acknowledgement/);
  assert.equal((await stream.exit).code,0);
});
