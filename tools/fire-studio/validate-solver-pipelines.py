"""Compile fallback families; Chrome validates standard subgroup variants."""
import json,sys,hashlib
from pathlib import Path
repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'work/smoke-shapes-qa/vendor'))
import wgpu
adapter=wgpu.gpu.request_adapter_sync(power_preference='high-performance');device=adapter.request_device_sync()
rows=json.loads((repo/'output/fire-principal-pass/solver-validation-fixture.json').read_text(encoding='utf-8'));errors=[]
skipped=[];compiled=0;validated=set();unique=0
for row in rows:
 if 'enable subgroups;' in row['code']:
  skipped.append(row['name']);continue
 key=(row.get('stage','compute'),row.get('entry','main'),hashlib.sha256(row['code'].encode()).hexdigest())
 if key in validated:
  compiled+=1;continue
 try:
  module=device.create_shader_module(code=row['code'])
  if row.get('stage')=='render':device.create_render_pipeline(layout='auto',vertex={'module':module,'entry_point':'vertex'},fragment={'module':module,'entry_point':'fragment','targets':[{'format':'rgba8unorm'}]})
  else:device.create_compute_pipeline(layout='auto',compute={'module':module,'entry_point':row.get('entry','main')})
  compiled+=1;unique+=1;validated.add(key)
 except Exception as error:errors.append({'name':row['name'],'message':str(error)[:3000]})
 if len(errors)>=20:break
report={'pass':not errors,'requested':len(rows),'compiled':compiled,'uniqueCompiled':unique,'browserOnly':skipped,'errors':errors,'adapter':dict(adapter.info),'nativeOnly':True}
out=repo/'output/fire-principal-pass/solver-pipelines.json';out.write_text(json.dumps(report,indent=2))
print(json.dumps({'out':str(out),'pass':report['pass'],'pipelines':compiled,'browserOnly':len(skipped),'errors':len(errors)}))
if errors:sys.exit(1)
