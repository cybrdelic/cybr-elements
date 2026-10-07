"""Replay actual Original host GL commands into a hidden native GLES context.

The recorder executes production host code with a deterministic clock and
records every resource upload, shader, uniform, solver pass and presentation.
This runner executes that trace without substituting synthetic fluid fields.
Native synchronous replay timings are comparative evidence, not browser FPS.
"""
import argparse,ctypes,json,os,re,statistics,subprocess,time,traceback
from pathlib import Path
import glfw
import numpy as np
from OpenGL import GL
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(os.environ.get('FIRE_STUDIO_ROOT',ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live')).resolve()
DTYPES={'Uint8Array':np.uint8,'Uint16Array':np.uint16,'Uint32Array':np.uint32,'Int32Array':np.int32,'Float32Array':np.float32,'Float64Array':np.float64}
DEPTH_RECONSTRUCTION_GLSL='''
float depthSlope(float left,float right){
  if(left*right<=0.)return 0.;
  return 2.*left*right/(left+right);
}
float depthCubic(float a,float b,float c,float d,float f){
  float m0=depthSlope(b-a,c-b),m1=depthSlope(c-b,d-c);
  float f2=f*f,f3=f2*f;
  float value=(2.*f3-3.*f2+1.)*b+(f3-2.*f2+f)*m0
             +(-2.*f3+3.*f2)*c+(f3-f2)*m1;
  return clamp(value,min(b,c),max(b,c));
}
vec4 cubicField(sampler2D tex,vec3 p){
  p=clamp(p,vec3(0.),vec3(1.));
  float z=p.z*(DEPTHf-1.),lo=floor(z),f=fract(z);
  vec4 a=texture(tex,atlasUV(p.xy,max(lo-1.,0.)));
  vec4 b=texture(tex,atlasUV(p.xy,lo));
  vec4 c=texture(tex,atlasUV(p.xy,min(lo+1.,DEPTHf-1.)));
  vec4 d=texture(tex,atlasUV(p.xy,min(lo+2.,DEPTHf-1.)));
  return vec4(depthCubic(a.x,b.x,c.x,d.x,f),depthCubic(a.y,b.y,c.y,d.y,f),
              depthCubic(a.z,b.z,c.z,d.z,f),depthCubic(a.w,b.w,c.w,d.w,f));
}
'''
RATE_RECONSTRUCTION_GLSL='''
float gasReactionRate(float fuel,float oxygen,float heat){
  return max(min(fuel,.7*oxygen),0.)*8.*clamp((heat-.15)/.22,0.,1.);
}
float reactionResidual(float stored,float localRate,float donorRate){
  return max(0.,stored+(localRate-donorRate));
}
float depthGasReaction(sampler2D tex,vec3 p,float stored){
  p=clamp(p,vec3(0.),vec3(1.));
  float z=p.z*(DEPTHf-1.),lo=floor(z),hi=min(lo+1.,DEPTHf-1.),f=fract(z);
  vec4 a=texture(tex,atlasUV(p.xy,lo)),b=texture(tex,atlasUV(p.xy,hi));
  vec4 c=mix(a,b,f);
  float donor=mix(gasReactionRate(a.r,a.g,a.b),gasReactionRate(b.r,b.g,b.b),f);
  return reactionResidual(stored,gasReactionRate(c.r,c.g,c.b),donor);
}
float cellGasReaction(sampler2D tex,vec3 p,float stored){
  vec3 grid=clamp(vec3(p.xy*vec2(NXf,NZf)-.5,p.z*(DEPTHf-1.)),
                  vec3(0.),vec3(NXf-1.,NZf-1.,DEPTHf-1.));
  ivec3 lo=ivec3(floor(grid)),hi=min(lo+ivec3(1),ivec3(int(NXf)-1,int(NZf)-1,int(DEPTHf)-1));
  vec3 f=fract(grid);vec4 chem=vec4(0);float donor=0.;
  for(int z=0;z<2;z++)for(int y=0;y<2;y++)for(int x=0;x<2;x++){
    ivec3 cell=ivec3(x==0?lo.x:hi.x,y==0?lo.y:hi.y,z==0?lo.z:hi.z);
    float weight=(x==0?1.-f.x:f.x)*(y==0?1.-f.y:f.y)*(z==0?1.-f.z:f.z);
    int tiles=int(atlasSize.x/NXf);
    ivec2 pixel=ivec2((cell.z%tiles)*int(NXf)+cell.x,(cell.z/tiles)*int(NZf)+cell.y);
    vec4 value=texelFetch(tex,pixel,0);
    chem+=weight*value;donor+=weight*gasReactionRate(value.r,value.g,value.b);
  }
  return reactionResidual(stored,gasReactionRate(chem.r,chem.g,chem.b),donor);
}
'''
CELL_AVERAGE_RECONSTRUCTION_GLSL='''
float cellAverageWeight(float distance){
  float r=abs(distance);
  if(r<1.)return (4.-6.*r*r+3.*r*r*r)/6.;
  if(r<2.)return pow(2.-r,3.)/6.;
  return 0.;
}
vec4 cellAverageField(sampler2D tex,vec3 p){
  p=clamp(p,vec3(0.),vec3(1.));
  float z=p.z*(DEPTHf-1.),lo=floor(z),f=fract(z);
  vec4 a=texture(tex,atlasUV(p.xy,max(lo-1.,0.)));
  vec4 b=texture(tex,atlasUV(p.xy,lo));
  vec4 c=texture(tex,atlasUV(p.xy,min(lo+1.,DEPTHf-1.)));
  vec4 d=texture(tex,atlasUV(p.xy,min(lo+2.,DEPTHf-1.)));
  return a*cellAverageWeight(f+1.)+b*cellAverageWeight(f)
        +c*cellAverageWeight(f-1.)+d*cellAverageWeight(f-2.);
}
'''
parser=argparse.ArgumentParser(description=__doc__,epilog='--record-only writes commands using Node and OpenGL enum constants without creating a GPU context. Native execution requires the exclusive GPU lease. All images and logs stay on disk.')
parser.add_argument('output',type=Path)
parser.add_argument('--record-only',action='store_true')
parser.add_argument('--replay-only',action='store_true')
parser.add_argument('--replay-cases',default='',help='Replay a comma-separated subset of cases already present in the recorded manifest. Does not change or regenerate the trace.')
parser.add_argument('--powers',default='radial-blast,fireball,fire-rain,fire-tornado,floor-trail,combustion-bomb',help='Comma-separated ability IDs, or all for every current registered power. The default remains the six initial powers for bounded replay.')
parser.add_argument('--times',default='.10,.30,.60,1.0,1.3,1.6,2.2,3.0')
parser.add_argument('--room',choices=['0','1'],default='1')
parser.add_argument('--angle',type=float,default=16,help='Use the existing production camera orbit control, in degrees.')
parser.add_argument('--zoom',type=float,default=1.4,help='Use the existing production camera zoom control; this never changes the simulation or raymarch quality.')
parser.add_argument('--heading',type=float,default=None,help='Use the shared production power aim heading, in degrees. Omit to use the authored ability direction.')
parser.add_argument('--diagnose-contours',action='store_true',help='At diagnostic-time, save actual chemistry/reaction cuts and re-integrate the same untouched field with512depthsamples. Diagnostic only; no runtime quality setting is changed.')
parser.add_argument('--diagnostic-time',type=float,default=2.5)
parser.add_argument('--diagnostic-step-hz',choices=['30','60'],default='30',help='Explicit diagnosis only: compare full production1/30s steps against1/60s steps without changing any live source file or grid.')
parser.add_argument('--diagnostic-source-samples',choices=['1','2','3'],default='1',help='Explicit diagnosis only: integrate two/three source-age samples at the unchanged30Hz physics step. Fuel rate and momentum use the same quadrature weights.')
parser.add_argument('--diagnostic-spatial-air',choices=['0','1'],default='0',help='Explicit diagnosis only: powers use the existing spatial gas mixing instead of oxygen restoration throughout hot fuel. No normal source or live file is changed.')
parser.add_argument('--diagnostic-reconstruction',action='store_true',help='Also compare monotone cubic depth reconstruction and isolated reaction/soot emission in the same untouched fields. Diagnostic only.')
parser.add_argument('--diagnostic-gas-rate',action='store_true',help='Compare stored-reaction interpolation to gas-based nonlinear residual reconstruction, preserving voxel-center reaction values. Diagnostic only.')
parser.add_argument('--diagnostic-cell-average',action='store_true',help='Compare conservative nonnegative cubic B-spline depth reconstruction of the actual gas cell averages. Four adjacent slices; no field modification or new extrema. Diagnostic only.')
parser.add_argument('--scenario',choices=['single','overlap','charge'],default='single',help='Record an automatic sequence, four overlapping finite casts, or actual pointer hold/aim/release controls.')
parser.add_argument('--fuel',choices=['preset','wood','gas','oil'],default='preset',help='Use the authored fuel for each power, or override it for a controlled comparison.')
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
if not args.replay_only:
 names=set('FRAMEBUFFER_COMPLETE MAX_TEXTURE_SIZE'.split())
 for file in SOURCE.rglob('*.js'):
  names.update(re.findall(r'\bgl\.([A-Z][A-Z0-9_]+)\b',file.read_text(encoding='utf-8')))
 enums={name:int(getattr(GL,'GL_'+name)) for name in names if hasattr(GL,'GL_'+name)}
 enum_file=out/'gl-enums.json';enum_file.write_text(json.dumps(enums))
 command=['node',str(ROOT/'tools/fire-studio/original-powers-capture.mjs'),'--out',str(out),'--enums',str(enum_file),'--powers',args.powers,'--times',args.times,'--room',args.room,'--fuel',args.fuel,'--scenario',args.scenario,'--angle',str(args.angle),'--zoom',str(args.zoom),'--diagnostic-step-hz',args.diagnostic_step_hz,'--diagnostic-source-samples',args.diagnostic_source_samples,'--diagnostic-spatial-air',args.diagnostic_spatial_air]
 if args.heading is not None:command.extend(['--heading',str(args.heading)])
 result=subprocess.run(command,capture_output=True,text=True)
 (out/'record.log').write_text(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError('Production command recording failed; see '+str(out/'record.log'))
 if args.record_only:print(result.stdout.strip());raise SystemExit(0)

manifest=json.loads((out/'capture-manifest.json').read_text())
if args.replay_cases:
 requested=set(args.replay_cases.split(','));available={case['id'] for case in manifest['cases']}
 assert requested<=available,'Requested replay case missing from recorded manifest'
 manifest['cases']=[case for case in manifest['cases'] if case['id'] in requested]
report={'runtimeRoot':manifest['runtimeRoot'],'sourceHashes':manifest.get('sourceHashes',{}),'diagnosticHostHash':manifest.get('diagnosticHostHash'),'diagnosticSpatialAir':manifest.get('diagnosticSpatialAir',False),'simulationHz':manifest.get('simulationHz',30),'diagnosticSourceSamples':manifest.get('diagnosticSourceSamples',1),'scenario':manifest.get('scenario','single'),'scope':__doc__,'pass':False,'cases':[]};window=None;cmd={};commands=0
try:
 if not glfw.init():raise RuntimeError('GLFW initialization failed')
 glfw.window_hint(glfw.VISIBLE,glfw.FALSE);glfw.window_hint(glfw.CLIENT_API,glfw.OPENGL_ES_API)
 glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3);glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,0)
 window=glfw.create_window(1280,720,'Original powers production replay',None,None)
 if not window:raise RuntimeError('Hidden GLES context unavailable')
 glfw.make_context_current(window)
 report['renderer']=GL.glGetString(GL.GL_RENDERER).decode();report['version']=GL.glGetString(GL.GL_VERSION).decode()
 extensions={GL.glGetStringi(GL.GL_EXTENSIONS,i).decode() for i in range(int(GL.glGetIntegerv(GL.GL_NUM_EXTENSIONS)))}
 timer_available='GL_EXT_disjoint_timer_query' in extensions
 report['gpuTimerAvailable']=timer_available
 binary={};contacts=[]
 for case in manifest['cases']:
  objects={};locations={};bound_fbo=0;frame_times=[];gpu_times=[];captures=[];last=time.perf_counter();draws=0;commands=0;query=None;pending_gpu_ms=None
  shader_sources={};shader_types={};program_shaders={};program_uniforms={};textures={};active_unit=0;current_program=0;current_vao=0;current_viewport=[0,0,1280,720];render_state=None;diagnostic_programs={}
  def diagnose(meta,normal_image):
   state=render_state;assert state is not None,'No production volume rendering state captured'
   chem_unit=int(state['uniforms']['chemTex'][1][0]);vf_unit=int(state['uniforms']['vfTex'][1][0])
   chem=state['textures'][(chem_unit,GL.GL_TEXTURE_2D)];vf=state['textures'][(vf_unit,GL.GL_TEXTURE_2D)]
   saved_binding=int(GL.glGetIntegerv(GL.GL_TEXTURE_BINDING_2D));actual_filters={}
   for name,texture in [('chem',chem),('vf',vf)]:
    GL.glBindTexture(GL.GL_TEXTURE_2D,texture)
    actual_filters[name]={'min':int(GL.glGetTexParameteriv(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_MIN_FILTER)),'mag':int(GL.glGetTexParameteriv(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_MAG_FILTER))}
   GL.glBindTexture(GL.GL_TEXTURE_2D,saved_binding)
   nx,ny,nz=case['domain']['nx'],case['domain']['ny'],case['domain']['depth']
   production_fragments=[shader_sources[s] for s in program_shaders[state['program']]]
   atlas_fragment=next(s for s in production_fragments if 'bool fineDepth=' in s)
   # Derive atlas packing from the actual recorded shader, rather than inventing
   # metadata absent from older manifests.
   tiles=int(float(re.search(r'float tx=mod\(layer,([0-9.]+)\)',atlas_fragment).group(1)))
   slices=[nz//4,nz//2,3*nz//4];cut_arrays={};fbo=int(GL.glGenFramebuffers(1));saved_read=int(GL.glGetIntegerv(GL.GL_READ_FRAMEBUFFER_BINDING))
   try:
    GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER,fbo)
    for name,texture in [('chem',chem),('vf',vf)]:
     GL.glFramebufferTexture2D(GL.GL_READ_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_TEXTURE_2D,texture,0)
     assert GL.glCheckFramebufferStatus(GL.GL_READ_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
     GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0)
     values=[]
     for layer in slices:
      data=np.frombuffer(GL.glReadPixels(layer%tiles*nx,layer//tiles*ny,nx,ny,GL.GL_RGBA,GL.GL_FLOAT),np.float32).reshape(ny,nx,4).copy()
      assert np.isfinite(data).all(),'Non-finite actual gas cut';values.append(data)
     cut_arrays[name]=np.stack(values)
     yz=[]
     for layer in range(nz):
      data=np.frombuffer(GL.glReadPixels(layer%tiles*nx+nx//2,layer//tiles*ny,1,ny,GL.GL_RGBA,GL.GL_FLOAT),np.float32).reshape(ny,4).copy()
      assert np.isfinite(data).all(),'Non-finite actual depth cut';yz.append(data)
     cut_arrays[name+'YZ']=np.stack(yz,axis=1)
   finally:GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER,saved_read);GL.glDeleteFramebuffers(1,[fbo])
   stem=Path(meta['file']).stem;np.savez_compressed(out/(stem+'-field-cuts.npz'),slices=np.asarray(slices),**cut_arrays)
   sheet=Image.new('RGB',(1536,1200),(8,9,12));label=ImageDraw.Draw(sheet)
   channels=[('temperature','chem',2),('soot','chem',3),('fuel','chem',0),('reaction','vf',3)];statistics_fields={}
   for col,(name,key,channel) in enumerate(channels):
    data=cut_arrays[key][...,channel];peak=float(np.max(data));statistics_fields[name]={'min':float(np.min(data)),'max':peak}
    for row,layer in enumerate(slices):
     value=np.flipud(data[row]);pixels=np.uint8(np.clip(value/max(peak,1e-8),0,1)*255)
     tile=Image.fromarray(pixels).convert('RGB').resize((384,384));sheet.paste(tile,(col*384,row*400));label.text((col*384+6,row*400+386),f'{name} z{layer} max{peak:.4g}',fill=(230,230,230))
   sheet.save(out/(stem+'-field-cuts.png'))
   yzsheet=Image.new('RGB',(1536,400),(8,9,12));yzlabel=ImageDraw.Draw(yzsheet)
   for col,(name,key,channel) in enumerate(channels):
    value=np.flipud(cut_arrays[key+'YZ'][...,channel]);peak=max(float(np.max(value)),1e-8)
    tile=Image.fromarray(np.uint8(np.clip(value/peak,0,1)*255)).convert('RGB').resize((384,384),Image.Resampling.NEAREST)
    yzsheet.paste(tile,(col*384,0));yzlabel.text((col*384+6,386),f'{name} center YZ max{peak:.4g}',fill=(230,230,230))
   yzsheet.save(out/(stem+'-field-YZ.png'))
   sources=[shader_sources[s] for s in program_shaders[state['program']]]
   vertex=next(s for s in sources if 'gl_Position' in s);production=next(s for s in sources if 'bool fineDepth=' in s)
   assert 'int sampleCount=fineDepth?128:64;' in production and 'for(int i=0;i<128;i++)' in production,'Unexpected production depth integration schema'
   variants={'depth512':production.replace('int sampleCount=fineDepth?128:64;','int sampleCount=fineDepth?512:64;').replace('for(int i=0;i<128;i++)','for(int i=0;i<512;i++)')}
   if args.diagnostic_reconstruction:
    variants['depth128-cubic']=production.replace('  void main(){',DEPTH_RECONSTRUCTION_GLSL+'\n  void main(){',1).replace('fineDepth?field(chemTex','fineDepth?cubicField(chemTex').replace('fineDepth?field(vfTex','fineDepth?cubicField(vfTex')
    variants['reaction-only']=production.replace('fireEmission(reaction,temp)+sootEmission(soot,temp)','fireEmission(reaction,temp)').replace('emission+scattering*scatter','emission')
    variants['soot-only']=production.replace('fireEmission(reaction,temp)+sootEmission(soot,temp)','sootEmission(soot,temp)').replace('emission+scattering*scatter','emission')
   if args.diagnostic_gas_rate:
    variants['depth128-linear']=production
    needle='float reaction=fineDepth?field(vfTex,vec3(p,z/float('+str(nz-1)+'))).a:layer(vfTex,p,z).a;'
    assert needle in production,'Unexpected reaction interpolation schema'
    for method in ['depthGasReaction','cellGasReaction']:
     variants[method]=production.replace('  void main(){',RATE_RECONSTRUCTION_GLSL+'\n  void main(){',1).replace(needle,needle+'\n      if(powerFlame>.5)reaction='+method+'(chemTex,vec3(p,z/float('+str(nz-1)+')),reaction);')
   if args.diagnostic_cell_average:
    variants['depth128-linear']=production
    variants['depthCellAverage']=production.replace('  void main(){',CELL_AVERAGE_RECONSTRUCTION_GLSL+'\n  void main(){',1).replace('fineDepth?field(chemTex','fineDepth?cellAverageField(chemTex').replace('fineDepth?field(vfTex','fineDepth?cellAverageField(vfTex')
   saved_textures=dict(textures);saved_active=active_unit
   comparisons=[]
   for variant,fragment in variants.items():
    if variant not in diagnostic_programs:
     program=GL.glCreateProgram()
     for kind,source in [(GL.GL_VERTEX_SHADER,vertex),(GL.GL_FRAGMENT_SHADER,fragment)]:
      shader=GL.glCreateShader(kind);GL.glShaderSource(shader,source);GL.glCompileShader(shader)
      assert GL.glGetShaderiv(shader,GL.GL_COMPILE_STATUS),GL.glGetShaderInfoLog(shader).decode(errors='replace')
      GL.glAttachShader(program,shader);GL.glDeleteShader(shader)
     GL.glLinkProgram(program);assert GL.glGetProgramiv(program,GL.GL_LINK_STATUS),GL.glGetProgramInfoLog(program).decode(errors='replace');diagnostic_programs[variant]=program
    program=diagnostic_programs[variant];GL.glUseProgram(program)
    for name,(method,values) in state['uniforms'].items():
     location=int(GL.glGetUniformLocation(program,name))
     if location<0:continue
     if method in ['uniform2fv','uniform3fv','uniform4fv']:getattr(GL,'gl'+method[0].upper()+method[1:])(location,len(values[0])//int(method[7]),values[0])
     else:getattr(GL,'gl'+method[0].upper()+method[1:])(location,*values)
    for (unit,target),texture in state['textures'].items():GL.glActiveTexture(GL.GL_TEXTURE0+unit);GL.glBindTexture(target,texture)
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,state['fbo']);GL.glViewport(*state['viewport']);GL.glBindVertexArray(state['vao'])
    projection_times=[]
    for warm in range(6 if (args.diagnostic_gas_rate or args.diagnostic_cell_average) and timer_available else 1):
     local_query=None
     if timer_available:
      local_query=int(np.asarray(GL.glGenQueries(1)).reshape(-1)[0]);GL.glBeginQuery(GL.GL_TIME_ELAPSED,local_query)
     GL.glDrawArrays(GL.GL_TRIANGLES,0,3)
     if local_query is not None:
      GL.glEndQuery(GL.GL_TIME_ELAPSED);ns=int(GL.glGetQueryObjectuiv(local_query,GL.GL_QUERY_RESULT));GL.glDeleteQueries(1,[local_query])
      if warm>=2 and not int(GL.glGetIntegerv(0x8FBB)):projection_times.append(ns/1e6)
    for (unit,target),texture in saved_textures.items():GL.glActiveTexture(GL.GL_TEXTURE0+unit);GL.glBindTexture(target,texture)
    GL.glActiveTexture(GL.GL_TEXTURE0+saved_active);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,bound_fbo);GL.glViewport(*current_viewport);GL.glBindVertexArray(current_vao);GL.glUseProgram(current_program);GL.glDrawArrays(GL.GL_TRIANGLES,0,3);GL.glFinish()
    im=Image.frombytes('RGBA',(1280,720),GL.glReadPixels(0,0,1280,720,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert('RGB');filename=stem+'-'+variant+'.png';im.save(out/filename)
    assert GL.glGetError()==GL.GL_NO_ERROR,'Diagnostic GL error'
    comparisons.append({'variant':variant,'image':filename,'meanAbsolutePixelDifference':float(np.abs(np.asarray(im).astype(np.float32)-np.asarray(normal_image).astype(np.float32)).mean()),'projectionGpuMsMedian':statistics.median(projection_times) if projection_times else None,'projectionGpuSamples':len(projection_times),'timingScope':'One warmed production projection draw only; excludes solver, room gather, presentation and browser scheduling.'})
   report.setdefault('diagnostics',[]).append({'id':case['id'],'time':meta['time'],'baselineSamples':128,'actualFields':statistics_fields,'actualFilters':actual_filters,'fieldSlices':slices,'fields':stem+'-field-cuts.npz','fieldImage':stem+'-field-cuts.png','depthImage':stem+'-field-YZ.png','comparisons':comparisons})
  def end_timer():
   global query,pending_gpu_ms,timer_available
   if query is not None:
    GL.glEndQuery(GL.GL_TIME_ELAPSED);ns=int(GL.glGetQueryObjectuiv(query,GL.GL_QUERY_RESULT));GL.glDeleteQueries(1,[query]);query=None
    if not int(GL.glGetIntegerv(0x8FBB)):pending_gpu_ms=ns/1e6
  def decode(value):
   if isinstance(value,list):return [decode(v) for v in value]
   if not isinstance(value,dict):return value
   if '$ref' in value:return objects[value['$ref']]
   if '$uniform' in value:
    key=(value['$uniform'],value['name'])
    if key not in locations:locations[key]=int(GL.glGetUniformLocation(objects[value['$uniform']],value['name']))
    return locations[key]
   if '$typed' in value:return np.asarray(value['data'],DTYPES[value['$typed']])
   if '$binary' in value:
    key=value['$binary']
    if key not in binary:binary[key]=np.fromfile(out/key,DTYPES[value['type']])
    return binary[key]
   return value
  for line in (out/case['trace']).open(encoding='utf-8'):
   cmd=json.loads(line);name=cmd['name'];values=[decode(v) for v in cmd['args']];commands+=1
   if name=='$capture':
    end_timer()
    GL.glFinish();data=GL.glReadPixels(0,0,1280,720,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
    im=Image.frombytes('RGBA',(1280,720),data).transpose(Image.Transpose.FLIP_TOP_BOTTOM).convert('RGB');im.save(out/values[0]['file'])
    arr=np.asarray(im);luma=arr.astype(np.float32).mean(axis=2)/255;lit=luma>.03
    captures.append({**values[0],'brightPixels':int((luma>.75).sum()),'litPixels':int(lit.sum()),'meanLuma':float(luma.mean()),'sha256':__import__('hashlib').sha256(im.tobytes()).hexdigest()})
    if args.diagnose_contours and abs(values[0]['time']-args.diagnostic_time)<.02:diagnose(values[0],im)
    contacts.append((values[0],im));continue
   if name=='$frame':
    end_timer();GL.glFinish();now=time.perf_counter();frame_times.append((now-last)*1000);last=now
    if pending_gpu_ms is not None:gpu_times.append(pending_gpu_ms);pending_gpu_ms=None
    continue
   if name=='$end':break
   if name=='viewport' and bound_fbo==0:values=[0,0,1280,720]
   if name=='bindFramebuffer':bound_fbo=values[1] or 0
   if name.startswith('bind') or name=='useProgram':values=[0 if v is None else v for v in values]
   if name=='activeTexture':active_unit=int(values[0])-GL.GL_TEXTURE0
   if name=='bindTexture':textures[(active_unit,int(values[0]))]=int(values[1])
   if name=='useProgram':current_program=int(values[0])
   if name=='bindVertexArray':current_vao=int(values[0])
   if name=='viewport':current_viewport=list(values)
   if name.startswith('uniform') and '$uniform' in cmd['args'][0]:
    location=cmd['args'][0];program_uniforms.setdefault(objects[location['$uniform']],{})[location['name']]=(name,values[1:])
   if name=='attachShader':program_shaders.setdefault(values[0],[]).append(values[1])
   if name=='shaderSource':shader_sources[values[0]]=values[1];GL.glShaderSource(*values);continue
   if name=='compileShader':
    GL.glCompileShader(*values)
    if not GL.glGetShaderiv(values[0],GL.GL_COMPILE_STATUS):raise RuntimeError(GL.glGetShaderInfoLog(values[0]).decode(errors='replace'))
    continue
   if name=='linkProgram':
    GL.glLinkProgram(*values)
    if not GL.glGetProgramiv(values[0],GL.GL_LINK_STATUS):raise RuntimeError(GL.glGetProgramInfoLog(values[0]).decode(errors='replace'))
    continue
   if name=='drawBuffers':GL.glDrawBuffers(len(values[0]),values[0]);continue
   if name in ['uniform2fv','uniform3fv','uniform4fv']:
    count=int(name[7]);getattr(GL,'gl'+name[0].upper()+name[1:])(values[0],len(values[1])//count,values[1]);continue
   if name=='bufferData':
    target,data,usage=values;GL.glBufferData(target,data if isinstance(data,(int,float)) else data.nbytes,None if isinstance(data,(int,float)) else data,usage);continue
   if name in ['vertexAttribPointer','vertexAttribIPointer','drawElements']:values[-1]=ctypes.c_void_p(values[-1])
   if name in ['drawArrays','drawElements'] and timer_available and query is None:
    query=int(np.asarray(GL.glGenQueries(1)).reshape(-1)[0]);GL.glBeginQuery(GL.GL_TIME_ELAPSED,query)
   if args.diagnose_contours and name=='drawArrays' and any('bool fineDepth=' in shader_sources.get(s,'') for s in program_shaders.get(current_program,[])):
    render_state={'program':current_program,'fbo':bound_fbo,'viewport':list(current_viewport),'vao':current_vao,'textures':dict(textures),'uniforms':dict(program_uniforms[current_program])}
   generators={'createTexture':'glGenTextures','createFramebuffer':'glGenFramebuffers','createVertexArray':'glGenVertexArrays','createBuffer':'glGenBuffers','createRenderbuffer':'glGenRenderbuffers'}
   if name in generators:result=getattr(GL,generators[name])(1)
   else:
    fn=getattr(GL,'gl'+name[0].upper()+name[1:]);result=fn(*values)
   if 'result' in cmd:objects[cmd['result']]=int(result)
   if name in ['drawArrays','drawElements']:draws+=1
  error=int(GL.glGetError());assert error==0,'Native GL error '+str(error)
  # Production trace ends with live resources; delete by retained type only
  # through context teardown after all cases. Allocation counts stay fixed.
  record={'id':case['id'],'domain':case['domain'],'captures':captures,'commands':commands,'draws':draws,
   'frameMsMedian':statistics.median(frame_times[2:]),'frameMsP95':sorted(frame_times)[max(0,int(len(frame_times)*.95)-1)],
   'gpuMsMedian':statistics.median(gpu_times[2:]) if len(gpu_times)>2 else None,'gpuMsP95':sorted(gpu_times)[max(0,int(len(gpu_times)*.95)-1)] if gpu_times else None,'gpuSamples':len(gpu_times),
   'timingScope':'Synchronous native replay including production light/render passes and occasional readback; browser scheduling not measured.'}
  report['cases'].append(record)
  (out/'render-progress.json').write_text(json.dumps({'completedCases':len(report['cases']),'totalCases':len(manifest['cases']),'lastCase':case['id'],'captures':sum(len(c['captures']) for c in report['cases'])}))
  # Destroy this context and open a fresh one to bound peak resources per case.
  glfw.destroy_window(window);window=glfw.create_window(1280,720,'Original powers production replay',None,None)
  if not window:raise RuntimeError('Hidden GLES context recreation failed')
  glfw.make_context_current(window)
 for case in manifest['cases']:
  selected=[(meta,im) for meta,im in contacts if meta['preset']==case['id']];cols=4;w,h=400,250;sheet=Image.new('RGB',(1600,h*((len(selected)+cols-1)//cols)),(7,9,12));text=ImageDraw.Draw(sheet)
  for i,(meta,im) in enumerate(selected):
   x=i%cols*w;y=i//cols*h;sheet.paste(im.resize((400,225)),(x,y));text.text((x+8,y+230),case['id']+f" {meta['time']:.2f} s",fill=(230,230,230))
  sheet.save(out/(case['id']+'-contact.png'))
 report['pass']=True
except Exception as error:
 report['error']=str(error)[:10000];report['lastCommand']={k:v for k,v in cmd.items() if k!='args'};report['commandIndex']=commands;(out/'native-error.log').write_text(traceback.format_exc())
finally:
 (out/'render-report.json').write_text(json.dumps(report,indent=2))
 if window:glfw.destroy_window(window)
 glfw.terminate()
print(json.dumps({'report':str(out/'render-report.json'),'pass':report['pass'],'cases':len(report['cases']),'captures':sum(len(c['captures']) for c in report['cases']),'error':report.get('error')}))
if not report['pass']:raise SystemExit(1)
