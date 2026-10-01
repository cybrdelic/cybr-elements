"""Native GLES gates for actual Original power sources and combustion programs.

Compile production startup exports; sample the production emitter/helper on a
64³ diagnostic grid; run each source through the full production gas shader.
This is source/field evidence, not browser FPS or a rendered-fire quality claim.
"""
import argparse,json,math,os,subprocess,traceback
from pathlib import Path
import glfw
import numpy as np
from OpenGL import GL
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(os.environ.get('FIRE_STUDIO_ROOT',ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live')).resolve()
parser=argparse.ArgumentParser(description='Check exported production Original GLSL programs, power release timelines and gas/soot coupling in an offscreen GLES 3 context.',epilog='Export with FIRE_STUDIO_SHADER_OUTPUT=<directory> node --test --experimental-test-isolation=none tools/fire-studio/original-powers.test.mjs tools/fire-studio/original-startup.test.mjs. Native GPU checks do not measure browser FPS.')
parser.add_argument('output',type=Path,help='Directory containing startup-*.json exports; native report and diagnostic source images are written here.')
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
report={'runtimeRoot':str(SOURCE),'scope':__doc__,'pass':False,'checks':[]};window=None

def compile(vertex,fragment,label):
 p=GL.glCreateProgram()
 for kind,source in [(GL.GL_VERTEX_SHADER,vertex),(GL.GL_FRAGMENT_SHADER,fragment)]:
  s=GL.glCreateShader(kind);GL.glShaderSource(s,source);GL.glCompileShader(s)
  if not GL.glGetShaderiv(s,GL.GL_COMPILE_STATUS):
   (out/(label+'-failed.glsl')).write_text(source);raise RuntimeError(label+': '+GL.glGetShaderInfoLog(s).decode(errors='replace'))
  GL.glAttachShader(p,s);GL.glDeleteShader(s)
 GL.glLinkProgram(p)
 if not GL.glGetProgramiv(p,GL.GL_LINK_STATUS):raise RuntimeError(label+': '+GL.glGetProgramInfoLog(p).decode(errors='replace'))
 return p

def texture(w,h,value=None,internal=GL.GL_RGBA16F,format=GL.GL_RGBA,kind=GL.GL_HALF_FLOAT,nearest=False):
 t=int(GL.glGenTextures(1));GL.glBindTexture(GL.GL_TEXTURE_2D,t)
 for param in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_2D,param,GL.GL_NEAREST if nearest else GL.GL_LINEAR)
 for param in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T]:GL.glTexParameteri(GL.GL_TEXTURE_2D,param,GL.GL_CLAMP_TO_EDGE)
 GL.glTexImage2D(GL.GL_TEXTURE_2D,0,internal,w,h,0,format,kind,value);return t

def target(w,h,attachments=1,float32=False):
 f=int(GL.glGenFramebuffers(1));GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,f);textures=[]
 for i in range(attachments):
  t=texture(w,h,internal=GL.GL_RGBA32F if float32 else GL.GL_RGBA16F,kind=GL.GL_FLOAT if float32 else GL.GL_HALF_FLOAT);textures.append(t)
  GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0+i,GL.GL_TEXTURE_2D,t,0)
 GL.glDrawBuffers(attachments,[GL.GL_COLOR_ATTACHMENT0+i for i in range(attachments)]);assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
 return {'fbo':f,'textures':textures,'w':w,'h':h}

def begin(p,t):GL.glUseProgram(p);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,t['fbo']);GL.glViewport(0,0,t['w'],t['h'])
def clear(t,index,value):GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,t['fbo']);GL.glClearBufferfv(GL.GL_COLOR,index,np.asarray(value,np.float32))
def bind(p,name,t,unit):GL.glActiveTexture(GL.GL_TEXTURE0+unit);GL.glBindTexture(GL.GL_TEXTURE_2D,t);GL.glUniform1i(GL.glGetUniformLocation(p,name),unit)
def uniform(p,name,*values):
 loc=GL.glGetUniformLocation(p,name)
 if len(values)==1:GL.glUniform1f(loc,*values)
 elif len(values)==2:GL.glUniform2f(loc,*values)
 elif len(values)==3:GL.glUniform3f(loc,*values)
 elif len(values)==4:GL.glUniform4f(loc,*values)
def integer(p,name,value):GL.glUniform1i(GL.glGetUniformLocation(p,name),value)
def draw():GL.glDrawArrays(GL.GL_TRIANGLES,0,3);assert GL.glGetError()==GL.GL_NO_ERROR
def read(t,index=0):
 GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,t['fbo']);GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0+index)
 return np.frombuffer(GL.glReadPixels(0,0,t['w'],t['h'],GL.GL_RGBA,GL.GL_FLOAT),np.float32).reshape(t['h'],t['w'],4).copy()
def unpack(data,nx,ny,nz):return data.reshape(nz//8,ny,8,nx,4).transpose(0,2,1,3,4).reshape(nz,ny,nx,4)

try:
 js="""import {writeFileSync} from 'node:fs';globalThis.window={};await import(process.argv[1]);
const {powerSourceGLSL}=await import(process.argv[2]);const {FIRE_PRESETS}=await import(process.argv[3]);const {FuelBrush}=await import(process.argv[4]);
const presets=FIRE_PRESETS.filter(p=>p.power);const trail=presets.find(p=>p.power==='floor-trail');const brush=new FuelBrush({minX:-4,maxX:4,minZ:-2,maxZ:2,radius:.26*trail.effect[1],amount:.85});brush.stamp(0,0);writeFileSync(process.argv[5],new Uint8Array(brush.consume().data.buffer));
process.stdout.write(JSON.stringify({emitters:window.FireEmitters,powerSourceGLSL,presets}));"""
 fixture=json.loads(subprocess.run(['node','--input-type=module','-e',js,(SOURCE/'fire-emitters.js').as_uri(),(SOURCE/'fire-powers.js').as_uri(),(SOURCE/'pyro-gpu/presets.js').as_uri(),(SOURCE/'fuel-ground.js').as_uri(),str(out/'floor-trail-stamp.r16.bin')],check=True,capture_output=True,text=True).stdout)
 files=sorted(out.glob('startup-*.json'));assert len(files)>=11,'Export all six powers and the five existing startup cases first'
 if not glfw.init():raise RuntimeError('GLFW initialization failed')
 glfw.window_hint(glfw.VISIBLE,glfw.FALSE);glfw.window_hint(glfw.CLIENT_API,glfw.OPENGL_ES_API);glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3);glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,0)
 window=glfw.create_window(768,432,'Original powers native QA',None,None)
 if not window:raise RuntimeError('Hidden GLES 3 context unavailable')
 glfw.make_context_current(window);GL.glBindVertexArray(GL.glGenVertexArrays(1));report['renderer']=GL.glGetString(GL.GL_RENDERER).decode();report['version']=GL.glGetString(GL.GL_VERSION).decode()
 cache={};production={};total=0
 for file in files:
  data=json.loads(file.read_text());assert Path(data['runtimeRoot']).resolve()==SOURCE
  case=[]
  for i,item in enumerate(data['programs']):
   key=(item['vertex'],item['fragment'])
   if key not in cache:cache[key]=compile(*key,file.stem+'-'+str(i))
   case.append((item,cache[key]));total+=1
  production[data['preset']]={'domain':data['domain'],'programs':case}
 report['checks'].append({'gate':'all production startup shader compile/link','pass':True,'cases':len(files),'programInstances':total,'uniquePrograms':len(cache)})
 vertex='''#version 300 es
out vec2 uv;void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);uv=p;gl_Position=vec4(p*2.-1.,0.,1.);}'''
 n=64;extent=np.array([8.,8.,4.]);minimum=np.array([-4.,-1.05,-2.]);
 fragment='''#version 300 es
precision highp float;precision highp int;precision highp sampler3D;
in vec2 uv;uniform float clock;uniform sampler2D noiseTex,chemTex;uniform vec2 brushTo;uniform float powerActive;
const vec3 simExtent=vec3(8,8,4),simMin=vec3(-4,-1.05,-2);vec4 field(sampler2D tex,vec3 p){return vec4(0,1,0,0);}
'''+fixture['powerSourceGLSL']+fixture['emitters']+'''
layout(location=0) out vec4 rate;layout(location=1) out vec4 force;
void main(){ivec2 ip=ivec2(gl_FragCoord.xy);int slice=ip.x/64+8*(ip.y/64);vec3 unit=vec3((vec2(ip.x%64,ip.y%64)+.5)/64.,float(slice)/63.);vec3 world=simMin+unit*simExtent;vec3 origin=vec3(simMin.xy+brushTo*simExtent.xy,powerOriginZ);float density=0.;vec3 jet=vec3(0),accel=vec3(0);if(powerActive>.5&&world.y>=0.){emitter(world.xy-origin.xy,world.z,density,jet);accel=powerAcceleration(float(emitterKind-21),world,origin,sourceScale,burstAge,clock,powerDirection,powerStrength);}rate=vec4(jet,density);force=vec4(accel,0);}'''
 helper=compile(vertex,fragment,'production-power-emitter-probe');probe=target(512,512,2,True);noise=texture(1,1,np.array([128]*4,np.uint8),GL.GL_RGBA8,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE);zero=texture(1,1,np.zeros(4,np.float16))
 volumeTex=int(GL.glGenTextures(1));GL.glActiveTexture(GL.GL_TEXTURE15);GL.glBindTexture(GL.GL_TEXTURE_3D,volumeTex)
 for p in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_3D,p,GL.GL_NEAREST)
 for p in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T,GL.GL_TEXTURE_WRAP_R]:GL.glTexParameteri(GL.GL_TEXTURE_3D,p,GL.GL_CLAMP_TO_EDGE)
 GL.glTexImage3D(GL.GL_TEXTURE_3D,0,GL.GL_RGBA16F,1,1,1,0,GL.GL_RGBA,GL.GL_HALF_FLOAT,np.zeros(4,np.float16))
 direction=[math.cos(math.radians(9)),math.sin(math.radians(9)),0.]
 world=np.stack(np.broadcast_arrays((minimum[0]+(np.arange(n)+.5)*extent[0]/n)[None,None,:],(minimum[1]+(np.arange(n)+.5)*extent[1]/n)[None,:,None],(minimum[2]+np.arange(n)*extent[2]/(n-1))[:,None,None]),axis=-1)
 ages={'radial-blast':[0,.15,.3,.44,.5],'fireball':[.1,.4,.8,1.1,1.2],'fire-rain':[.1,.6,1.4,3.2],'fire-tornado':[.1,1.,3.2],'floor-trail':[0,1.,3.2],'combustion-bomb':[0,.7,1.18,1.25,1.4,1.56]}
 fields={};images=[]
 def setup(p,preset,age,active=True):
  origin=np.array(preset['source']);unit=(origin[:2]-minimum[:2])/extent[:2]
  for name,value in [('burstAge',age),('clock',age),('sourceScale',preset['effect'][1]),('powerStrength',1),('powerOriginZ',origin[2]),('powerActive',float(active))]:uniform(p,name,value)
  uniform(p,'brushTo',*unit);uniform(p,'brushFrom',*unit);uniform(p,'powerDirection',*direction);uniform(p,'fuelProfile',1,1,1);integer(p,'emitterKind',int(preset['effect'][0]));integer(p,'sourceEffectKind',int(preset['effect'][0]));
  bind(p,'noiseTex',noise,3);bind(p,'chemTex',zero,1);GL.glActiveTexture(GL.GL_TEXTURE14);GL.glBindTexture(GL.GL_TEXTURE_3D,volumeTex);integer(p,'objectTex',14)
  return origin
 for preset in fixture['presets']:
  name=preset['id'];records=[];representative=None
  for age in ages[name]:
   begin(helper,probe);origin=setup(helper,preset,age);draw();data=unpack(read(probe),n,n,n);accel=unpack(read(probe,1),n,n,n);assert np.isfinite(data).all() and np.isfinite(accel).all()
   mask=data[:,:,:,3]>1e-5;weight=data[:,:,:,3];totalRate=float(weight.sum(dtype=np.float64));record={'age':age,'activeVoxels':int(mask.sum()),'sourceWeightSum':totalRate,'peakWeight':float(weight.max()),'maxAcceleration':float(np.linalg.norm(accel[:,:,:,:3],axis=-1).max())}
   if mask.any():
    record['weightedCenter']=((world*weight[:,:,:,None]).sum(axis=(0,1,2))/totalRate).tolist();record['weightedVelocity']=((data[:,:,:,:3]*weight[:,:,:,None]).sum(axis=(0,1,2))/totalRate).tolist()
    if representative is None or totalRate>representative[0]:representative=(totalRate,age,weight.copy())
   records.append(record)
  if name=='floor-trail':assert all(r['activeVoxels']==0 for r in records),'Trail must use the finite ground reservoir, never an immortal analytic line'
  else:assert any(r['activeVoxels']>0 for r in records),name+' must emit'
  if name in ['radial-blast','fireball','combustion-bomb']:assert records[-1]['activeVoxels']==0,name+' must stop at its finite lifetime'
  if name=='fireball':assert records[2]['weightedCenter'][0]>records[0]['weightedCenter'][0]+1,'The projectile moves through world space'
  if name=='fire-rain':assert all(r.get('weightedVelocity',[0,0])[1]<-2 for r in records)
  if name=='fire-tornado':assert max(r['maxAcceleration'] for r in records)>1
  begin(helper,probe);setup(helper,preset,.2,False);draw();assert not np.any(read(probe)) and not np.any(read(probe,1)),'Stop casting removes fuel and external forces'
  fields[name]=records;report['checks'].append({'gate':name+' release, motion and stopped-state fields','pass':True,'timeline':records})
  if representative:
   totalRate,age,weight=representative;projection=weight.sum(axis=0)[::-1];level=np.clip(projection/max(float(projection.max()),1e-9),0,1)
   rgb=np.stack([level**.45,level**.8*.72,level*.15],axis=-1);image=Image.fromarray((rgb*255+.5).astype(np.uint8)).resize((384,384));canvas=Image.new('RGB',(400,430),(12,14,16));canvas.paste(image,(8,38));ImageDraw.Draw(canvas).text((8,8),name+' | source age '+str(age)+' s',fill='white');canvas.save(out/(name+'-source.png'));images.append((name,canvas))
  else:
   canvas=Image.new('RGB',(400,430),(12,14,16));ImageDraw.Draw(canvas).text((8,8),'floor-trail | finite ground reservoir',fill='white');images.append((name,canvas))
 # Exercise the full production gas shader and the actual finite trail reservoir.
 powerCase=production['radial-blast'];domain=powerCase['domain'];nx,ny,nz=domain['nx'],domain['ny'],domain['depth'];w,h=nx*8,ny*(nz//8)
 select=lambda needle:next(p for item,p in powerCase['programs'] if needle in item['fragment'])
 simulation=select('out vec4 outVF;');ground=select('out vec4 state;');predictorProgram=select('out vec4 outScalars;');chem=target(w,h);vf=target(w,h);gas=target(w,h,2);gasPeer=target(w,h,2);predictor=target(w,h);clear(chem,0,[0,1,0,0]);clear(vf,0,[0,0,0,0]);bed=target(128,128,2,True);clear(bed,0,[0,0,0,0]);clear(bed,1,[0,0,0,0]);oldBed=target(128,128,2,True);clear(oldBed,0,[0,0,0,0]);clear(oldBed,1,[0,0,0,0]);stamp=texture(128,128,np.frombuffer((out/'floor-trail-stamp.r16.bin').read_bytes(),np.float16),GL.GL_R16F,GL.GL_RED)
 begin(ground,bed)
 for unit,key,t in [(0,'groundOld',oldBed['textures'][0]),(1,'groundWearOld',oldBed['textures'][1]),(2,'groundStamp',stamp),(3,'chemTex',chem['textures'][0])]:bind(ground,key,t,unit)
 uniform(ground,'groundBounds',-4,-2,4,2)
 for name,value in [('groundDeposit',1),('groundIgnition',1),('groundCombustion',1),('groundWood',0),('delta',1/30)]:uniform(ground,name,value)
 draw();bedData=read(bed);assert bedData[:,:,0].max()>0 and bedData[:,:,2].max()>0
 gasAges={'radial-blast':.2,'fireball':.35,'fire-rain':.8,'fire-tornado':1.,'floor-trail':.2,'combustion-bomb':1.32}
 for preset in fixture['presets']:
  name=preset['id'];inputVF=vf['textures'][0];inputChem=chem['textures'][0];output=gas;stepsToReaction=0
  for step in range(10):
   # Low-feed sustained sources may warm for several physical steps before
   # ignition. Use the real transport predictor, not synthetic ambient heat.
   begin(predictorProgram,predictor);bind(predictorProgram,'vfTex',inputVF,0);bind(predictorProgram,'chemTex',inputChem,1);bind(predictorProgram,'pressureCorrectionTex',zero,5);uniform(predictorProgram,'delta',1/30);draw()
   begin(simulation,output);setup(simulation,preset,gasAges[name]+step/30)
   for unit,key,t in [(0,'vfTex',inputVF),(1,'chemTex',inputChem),(2,'sourceTex',zero),(3,'noiseTex',noise),(4,'widthTex',zero),(5,'pressureCorrectionTex',zero),(6,'mcPredictorTex',predictor['textures'][0]),(7,'vortexTex',zero),(13,'groundFuelTex',bed['textures'][0])]:bind(simulation,key,t,unit)
   GL.glActiveTexture(GL.GL_TEXTURE15);GL.glBindTexture(GL.GL_TEXTURE_3D,volumeTex);integer(simulation,'turbulenceTex',15)
   for key,value in [('delta',1/30),('sourceEnabled',0),('woodEnabled',0),('brushActive',1),('pointerStrength',0),('smokeOnly',0),('sourceLift',1),('sourceHeat',preset['chemistry'][1]),('coolingScale',1),('presetBuoyancy',4),('groundEnabled',float(name=='floor-trail'))]:uniform(simulation,key,value)
   uniform(simulation,'groundBounds',-4,-2,4,2);uniform(simulation,'vortexOrigin',0,0,0);uniform(simulation,'vortexSpan',1,1,1);uniform(simulation,'pointer',.5,.5);uniform(simulation,'pointerMotion',0,0);draw()
   velocity=read(output,0);chemistry=read(output,1);assert np.isfinite(velocity).all() and np.isfinite(chemistry).all()
   peaks=chemistry.max(axis=(0,1));reaction=float(velocity[:,:,3].max());assert peaks[0]>0 and peaks[2]>0,name+' must release fuel and heat from its cold initial field'
   if peaks[3]>0 and reaction>0:stepsToReaction=step+1;break
   inputVF,inputChem=output['textures'];output=gasPeer if output is gas else gas
  assert stepsToReaction>0,name+' must reach normal combustion and generate coupled soot within ten fixed-buffer steps'
  report['checks'].append({'gate':name+' production gas/combustion coupling','pass':True,'maxFuelOxygenHeatSoot':peaks.astype(float).tolist(),'maxReactionRate':reaction,'reactingVoxels':int(np.count_nonzero(velocity[:,:,3])),'stepsToReaction':stepsToReaction,'transport':'Actual production MacCormack predictor/corrector; pressure and vorticity inputs held at zero to isolate source/reaction coupling'})
 sheet=Image.new('RGB',(1200,900),(8,10,12));drawText=ImageDraw.Draw(sheet);drawText.text((8,4),'Native source release support projections | not a rendered flame or browser performance proof',fill='white')
 for i,(_,im) in enumerate(images):sheet.paste(im,((i%3)*400,32+(i//3)*430))
 sheet.save(out/'power-source-contact.png');report['pass']=True
except Exception as error:
 report['error']=str(error)[:12000];(out/'error.log').write_text(traceback.format_exc())
finally:
 (out/'native-powers-report.json').write_text(json.dumps(report,indent=2))
 if window:glfw.destroy_window(window)
 glfw.terminate()
print(json.dumps({'report':str(out/'native-powers-report.json'),'pass':report['pass'],'checks':len(report['checks']),'error':report.get('error'),'images':len(list(out.glob('*source*.png')))}))
if not report['pass']:raise SystemExit(1)
