"""Short hidden-GLES gate for actual Original startup shaders and floor storage.

Prepare with FIRE_STUDIO_SHADER_OUTPUT=<output> node original-startup.test.mjs.
FIRE_STUDIO_ROOT selects the runtime under test for source and packaged checks.
This proves native shader/storage/pixel behavior, not browser FPS or full flow.
"""
import argparse,json,math,os,time
from pathlib import Path
import glfw
import numpy as np
from OpenGL import GL
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(os.environ.get('FIRE_STUDIO_ROOT',ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live')).resolve()
ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);ap.add_argument('--wood',action='store_true',help='Run current wood stock, floor and posed mesh gates after the base lifecycle gates');args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
data=json.loads((out/'startup-sigil.json').read_text());assert Path(data['runtimeRoot']).resolve()==SOURCE,'Export the runtime selected by FIRE_STUDIO_ROOT first'
report={'runtimeRoot':str(SOURCE),'scope':'Hidden native GLES actual shader assembly, cold inventory, finite ignition, burnout, persistent guide char and material pixels. No browser/mobile/frame-pacing proof.','checks':[],'pass':False}
def compile(v,f,label='fixture'):
 p=GL.glCreateProgram()
 for kind,source in [(GL.GL_VERTEX_SHADER,v),(GL.GL_FRAGMENT_SHADER,f)]:
  s=GL.glCreateShader(kind);GL.glShaderSource(s,source);GL.glCompileShader(s)
  if not GL.glGetShaderiv(s,GL.GL_COMPILE_STATUS):
   stage='vertex' if kind==GL.GL_VERTEX_SHADER else 'fragment';path=out/(str(label)+'-'+stage+'-failed.glsl');path.write_text(source)
   raise RuntimeError(f'{label} {stage} compile failed ({path}): '+GL.glGetShaderInfoLog(s).decode(errors='replace'))
  GL.glAttachShader(p,s);GL.glDeleteShader(s)
 GL.glLinkProgram(p)
 if not GL.glGetProgramiv(p,GL.GL_LINK_STATUS):raise RuntimeError(GL.glGetProgramInfoLog(p).decode(errors='replace'))
 return p
def texture(w,h,value=None,internal=GL.GL_RGBA16F,format=GL.GL_RGBA,kind=GL.GL_HALF_FLOAT,filter=GL.GL_LINEAR):
 t=int(GL.glGenTextures(1));GL.glBindTexture(GL.GL_TEXTURE_2D,t)
 for param in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_2D,param,filter)
 for param in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T]:GL.glTexParameteri(GL.GL_TEXTURE_2D,param,GL.GL_CLAMP_TO_EDGE)
 GL.glTexImage2D(GL.GL_TEXTURE_2D,0,internal,w,h,0,format,kind,value);return t
def target(w,h,float32=False):
 t=texture(w,h,internal=GL.GL_RGBA32F if float32 else GL.GL_RGBA16F,kind=GL.GL_FLOAT if float32 else GL.GL_HALF_FLOAT,filter=GL.GL_NEAREST if float32 else GL.GL_LINEAR);f=int(GL.glGenFramebuffers(1));GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,f);GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT0,GL.GL_TEXTURE_2D,t,0)
 GL.glDrawBuffers(1,[GL.GL_COLOR_ATTACHMENT0]);assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
 GL.glClearBufferfv(GL.GL_COLOR,0,np.zeros(4,np.float32));return t,f,w,h
def clear(t,value):GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,t[1]);GL.glClearBufferfv(GL.GL_COLOR,0,np.array(value,np.float32))
def begin(p,t):GL.glUseProgram(p);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,t[1]);GL.glViewport(0,0,t[2],t[3])
def bind(p,name,t,unit):GL.glActiveTexture(GL.GL_TEXTURE0+unit);GL.glBindTexture(GL.GL_TEXTURE_2D,t);GL.glUniform1i(GL.glGetUniformLocation(p,name),unit)
def u(p,name,*v):
 loc=GL.glGetUniformLocation(p,name)
 if len(v)==1:GL.glUniform1f(loc,*v)
 elif len(v)==2:GL.glUniform2f(loc,*v)
 elif len(v)==3:GL.glUniform3f(loc,*v)
 elif len(v)==4:GL.glUniform4f(loc,*v)
def draw():GL.glDrawArrays(GL.GL_TRIANGLES,0,3)
def read(t):
 GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,t[1]);return np.frombuffer(GL.glReadPixels(0,0,t[2],t[3],GL.GL_RGBA,GL.GL_FLOAT),np.float32).reshape(t[3],t[2],4).copy()
window=None
try:
 if not glfw.init():raise RuntimeError('GLFW initialization failed')
 glfw.window_hint(glfw.VISIBLE,glfw.FALSE);glfw.window_hint(glfw.CLIENT_API,glfw.OPENGL_ES_API);glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3);glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,0)
 window=glfw.create_window(896,504,'Original finite fuel QA',None,None)
 if not window:raise RuntimeError('Hidden GLES 3 context unavailable')
 glfw.make_context_current(window);GL.glBindVertexArray(GL.glGenVertexArrays(1))
 report['renderer']=GL.glGetString(GL.GL_RENDERER).decode();report['version']=GL.glGetString(GL.GL_VERSION).decode()
 programs=[(item,compile(item['vertex'],item['fragment'],'sigil-program-'+str(i))) for i,item in enumerate(data['programs'])]
 burst=json.loads((out/'startup-explosion.json').read_text());assert Path(burst['runtimeRoot']).resolve()==SOURCE
 burst_programs=[compile(item['vertex'],item['fragment'],'burst-program-'+str(i)) for i,item in enumerate(burst['programs'])]
 report['checks'].append({'gate':'actual normal/burst startup shader compile/link','pass':True,'programs':len(programs)+len(burst_programs)})
 select=lambda needle:next(p for item,p in programs if needle in item['fragment'])
 ground=select('out vec4 state;');guide=select('out vec4 damage;');render=select('bool fineDepth=');present=select('uniform sampler2D projection;');simulation=select('out vec4 outVF;')
 sim_source=next(item for item,p in programs if p==simulation);old_fragment=sim_source['fragment'].replace('if(soot<0.00002)soot=0.;','if(soot<0.)soot=0.;')
 assert old_fragment!=sim_source['fragment'],'The legacy comparison disables only the new invisible residue cutoff'
 old_simulation=compile(sim_source['vertex'],old_fragment)
 domain=data['domain'];nx,ny,depth=domain['nx'],domain['ny'],domain['depth'];w,h=nx*8,ny*(depth//8)
 chemistry=target(w,h);clear(chemistry,[0,1,0,0]);velocity=target(w,h)
 inventory=[target(128,128,True),target(128,128,True)];damage=[target(256,144),target(256,144)]
 lo=domain['minimum'];extent=domain['extent'];bounds=(lo[0],lo[2],lo[0]+extent[0],lo[2]+extent[2])
 x=np.linspace(bounds[0],bounds[2],128,endpoint=False)+extent[0]/256;z=np.linspace(bounds[1],bounds[3],128,endpoint=False)+extent[2]/256
 q=(x[None,:]/.22)**2+(z[:,None]/.22)**2;packet=(.65*np.maximum(0,1-q)**2).astype(np.float16)
 stamp=texture(128,128,packet,GL.GL_R16F,GL.GL_RED);ci=0
 def step(deposit=False,ignite=False,combustion_enabled=True):
  global ci
  begin(ground,inventory[1-ci]);bind(ground,'groundOld',inventory[ci][0],0);bind(ground,'groundStamp',stamp,1);bind(ground,'chemTex',chemistry[0],2)
  u(ground,'groundBounds',*bounds);u(ground,'groundDeposit',float(deposit));u(ground,'groundIgnition',float(ignite));u(ground,'groundCombustion',float(combustion_enabled));u(ground,'delta',1/30);draw();ci=1-ci
 step(deposit=True);cold=read(inventory[ci]);initial=float(cold[:,:,0].sum(dtype=np.float64));assert initial>0 and np.count_nonzero(cold[:,:,1:])==0
 for _ in range(30):step()
 cold_again=read(inventory[ci]);assert np.array_equal(cold,cold_again)
 report['checks'].append({'gate':'cold additive fuel stays unlit for 31 ground steps','pass':True,'massSum':initial})
 # The actual production combustion shader receives no emitter/brush heat.
 # Predictor/current chemistry are the identical cold field and pressure,
 # vorticity and flow are zero, isolating the ground reservoir coupling.
 zero=target(128,128);noise=texture(1,1,np.array([128,128,128,128],np.uint8),GL.GL_RGBA8,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
 gas=target(w,h);gas_vf=target(w,h);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,gas_vf[1]);GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT1,GL.GL_TEXTURE_2D,gas[0],0);GL.glDrawBuffers(2,[GL.GL_COLOR_ATTACHMENT0,GL.GL_COLOR_ATTACHMENT1]);assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
 turbulence=int(GL.glGenTextures(1));GL.glActiveTexture(GL.GL_TEXTURE15);GL.glBindTexture(GL.GL_TEXTURE_3D,turbulence)
 for param in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_3D,param,GL.GL_NEAREST)
 for param in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T,GL.GL_TEXTURE_WRAP_R]:GL.glTexParameteri(GL.GL_TEXTURE_3D,param,GL.GL_CLAMP_TO_EDGE)
 GL.glTexImage3D(GL.GL_TEXTURE_3D,0,GL.GL_RGBA16F,1,1,1,0,GL.GL_RGBA,GL.GL_HALF_FLOAT,np.zeros(4,np.float16))
 def gas_step(ground_enabled=True,program=simulation):
  begin(program,gas_vf)
  for unit,name,t in [(0,'vfTex',velocity[0]),(1,'chemTex',chemistry[0]),(2,'sourceTex',zero[0]),(3,'noiseTex',noise),(4,'widthTex',zero[0]),(5,'pressureCorrectionTex',zero[0]),(6,'mcPredictorTex',chemistry[0]),(7,'vortexTex',zero[0]),(13,'groundFuelTex',inventory[ci][0])]:bind(program,name,t,unit)
  GL.glActiveTexture(GL.GL_TEXTURE15);GL.glBindTexture(GL.GL_TEXTURE_3D,turbulence);GL.glUniform1i(GL.glGetUniformLocation(program,'turbulenceTex'),15);GL.glUniform1i(GL.glGetUniformLocation(program,'objectTex'),15)
  for name,value in [('delta',1/30),('clock',0),('sourceEnabled',0),('brushActive',0),('pointerStrength',0),('smokeOnly',0),('sourceScale',1.48),('sourceLift',.82),('sourceHeat',1),('coolingScale',1),('presetBuoyancy',4),('groundEnabled',float(ground_enabled)),('burstAge',100)]:u(program,name,value)
  u(program,'groundBounds',*bounds);u(program,'vortexOrigin',0,0,0);u(program,'vortexSpan',1,1,1);u(program,'fuelProfile',1,1,1);u(program,'pointer',.5,.5);u(program,'pointerMotion',0,0);u(program,'brushFrom',.5,.5);u(program,'brushTo',.5,.5)
  GL.glUniform1i(GL.glGetUniformLocation(program,'emitterKind'),1);GL.glUniform1i(GL.glGetUniformLocation(program,'sourceEffectKind'),1);draw();assert GL.glGetError()==GL.GL_NO_ERROR
 gas_step();cold_gas=read(gas);assert np.count_nonzero(cold_gas[:,:,[0,2,3]])==0;del cold_gas
 step(ignite=True);ignited=read(inventory[ci]);has_fuel=cold[:,:,0]>0
 assert np.all(ignited[:,:,1][has_fuel]>1) and np.count_nonzero(ignited[:,:,1][~has_fuel])==0 and ignited[:,:,2].max()>0
 report['checks'].append({'gate':'finite explicit ignition only affects existing inventory','pass':True,'peakHeat':float(ignited[:,:,1].max())})
 gas_step();coupled_gas=read(gas);coupled_vf=read(gas_vf)
 assert np.isfinite(coupled_gas).all() and np.isfinite(coupled_vf).all()
 maxima=coupled_gas.max(axis=(0,1)).astype(float);reaction=float(coupled_vf[:,:,3].max())
 assert maxima[0]>0 and maxima[2]>0 and maxima[3]>0 and reaction>0
 report['checks'].append({'gate':'actual production gas combustion from reservoir only; source and brush disabled','pass':True,'maxFuelOxygenTemperatureSoot':maxima.tolist(),'maxReaction':reaction,'reactingVoxels':int(np.count_nonzero(coupled_vf[:,:,3])),'mainSourceEnabled':False,'mainBrushActive':False,'coldDepositGasFuelHeatSootNonzero':0})
 del coupled_gas,coupled_vf
 step();after=read(inventory[ci]);assert after[:,:,1].max()<ignited[:,:,1].max()
 clear(chemistry,[0,1,1,0]);released=0.
 for _ in range(300):
  step();a=read(inventory[ci]);released+=float(a[:,:,2].sum(dtype=np.float64))/30
 remaining=float(a[:,:,0].sum(dtype=np.float64));assert np.isfinite(a).all() and remaining<initial*.001
 char_sum=float(a[:,:,3].sum(dtype=np.float64));residual=abs(remaining+char_sum-initial)/initial;assert residual<.00001
 report['checks'].append({'gate':'RGBA32F finite inventory burns out and conserves surface mass','pass':True,'remainingFraction':remaining/initial,'charSum':char_sum,'relativeMassResidual':residual,'measuredReleasedDuringHotSteps':released})
 source=texture(896,504,np.frombuffer((SOURCE/'source/source-native.rgba8.bin').read_bytes(),np.uint8),GL.GL_RGBA8,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
 gi=0
 for _ in range(90):
  begin(guide,damage[1-gi]);bind(guide,'guideOld',damage[gi][0],0);bind(guide,'sourceTex',source,1);bind(guide,'chemTex',chemistry[0],2);u(guide,'delta',1/30);draw();gi=1-gi
 char=read(damage[gi]);assert char[:,:,0].max()>.1
 clear(chemistry,[0,1,0,0]);begin(guide,damage[1-gi]);bind(guide,'guideOld',damage[gi][0],0);bind(guide,'sourceTex',source,1);bind(guide,'chemTex',chemistry[0],2);u(guide,'delta',1/30);draw();gi=1-gi;assert np.array_equal(char,read(damage[gi]))
 report['checks'].append({'gate':'static-art substrate char accumulates from chemistry and persists after cooling','pass':True,'maxChar':float(char[:,:,0].max())})
 black=target(128,128);white=target(480,96);clear(white,[4,4,4,1]);projection=target(896,504);image=target(896,504)
 yaw=16*math.pi/180;eye=np.array([math.sin(yaw)*13,3.5,math.cos(yaw)*13]);forward=np.array([0,2.4,0])-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
 def image_case(name,guide_visible,fuel_visible,coupled=False):
  begin(render,projection)
  for unit,key,t in [(0,'vfTex',gas_vf[0] if coupled else velocity[0]),(1,'chemTex',gas[0] if coupled else chemistry[0]),(2,'sourceTex',source),(4,'sourceGuideTex',damage[gi][0]),(8,'smokeLightTex',black[0]),(9,'roomPowerTex',black[0]),(10,'roomMomentTex',black[0]),(11,'roomSmokeTex',black[0]),(12,'roomReceiverTex',white[0]),(13,'groundFuelTex',inventory[ci][0])]:bind(render,key,t,unit)
  u(render,'groundBounds',*bounds);u(render,'groundEnabled',float(fuel_visible));u(render,'sourceGuide',float(guide_visible));u(render,'roomEnabled',1);u(render,'customLighting',1);u(render,'viewZoom',1);u(render,'viewPan',0,0);u(render,'inspectSmoke',0);u(render,'inspectionLight',0);u(render,'cameraTan',.3443276133);u(render,'cameraEye',*eye);u(render,'cameraForward',*forward);u(render,'cameraRight',*right);u(render,'cameraUp',*up);u(render,'ambientLight',1,1,1);u(render,'fireLightGain',1)
  # White inspection receiver values isolate surface shading from lighting-cache
  # generation. They do not certify the UI lighting preset or cast shadows.
  for i,(angle,height,power) in enumerate([(-40,5.5,180),(140,5,140)]):
   az=math.radians(angle);p=np.array([math.sin(az)*5,height,1.2+math.cos(az)*3]);d=np.array([0,2,0])-p;d/=np.linalg.norm(d)
   u(render,f'spotPosition[{i}]',*p);u(render,f'spotDirection[{i}]',*d);u(render,f'spotPower[{i}]',power,power,power);u(render,f'spotCone[{i}]',math.cos(math.radians(42.5)),math.cos(math.radians(42.5*.7)))
  GL.glUniform1i(GL.glGetUniformLocation(render,'visibleEmitter'),0);draw()
  begin(present,image);bind(present,'projection',projection[0],0);draw();pixels=(np.clip(read(image)[::-1,:,:3],0,1)*255+.5).astype(np.uint8);Image.fromarray(pixels).save(out/(name+'.png'));return pixels
 bare=image_case('bare-floor',False,False);substrate=image_case('sigil-substrate',True,False);puddle=image_case('sigil-charred-fuel',True,True)
 image_case('ground-ignition-first-step',False,True,True)
 assert np.count_nonzero(np.any(substrate!=bare,axis=2))>1000 and np.count_nonzero(np.any(puddle!=substrate,axis=2))>10
 report['checks'].append({'gate':'actual render/presentation show guide and finite floor material','pass':True,'guideChangedPixels':int(np.count_nonzero(np.any(substrate!=bare,axis=2))),'groundChangedPixels':int(np.count_nonzero(np.any(puddle!=substrate,axis=2)))})
 for t in inventory:clear(t,[0,0,0,0])
 ci=0;clear(chemistry,[0,1,0,0]);step(True);disabled_mass=read(inventory[ci])[:,:,0].copy();clear(chemistry,[0,1,1,0])
 for i in range(30):step(ignite=i==0,combustion_enabled=False)
 disabled=read(inventory[ci]);assert np.array_equal(disabled[:,:,0],disabled_mass) and np.count_nonzero(disabled[:,:,2:])==0
 report['checks'].append({'gate':'smoke simulation preserves heated floor inventory and rejects ignition','pass':True,'releaseNonzero':0,'charNonzero':0,'fuelMassUnchanged':True})
 clear(chemistry,[0,1,0,float(np.float16(1.621246337890625e-5))]);gas_step(False);residue=read(gas)
 assert np.count_nonzero(residue[:,:,3])==0;del residue
 gas_step(False,old_simulation);legacy_residue=read(gas);legacy_peak=float(legacy_residue[:,:,3].max());assert legacy_peak>0;del legacy_residue
 clear(chemistry,[0,1,0,.1]);gas_step(False);visible=read(gas)
 # Atlas row two / column zero addresses interior depth layer 16, and the
 # middle of that tile avoids the absorbing x/y outlet collars.
 center_soot=float(visible[2*ny+ny//2,nx//2,3]);expected=float(np.float16(np.float32(np.float16(.1))*np.float32(math.exp(-.055/30))))
 gas_step(False,old_simulation);legacy_visible=read(gas)
 # The absorbing outlet intentionally creates sub-cutoff soot even from a
 # visible uniform input. All other chemistry and all visible soot must match;
 # only invisible soot may differ, and it must become exactly zero. Account
 # for the one binary16 storage quantization of the cutoff itself.
 cutoff_ceiling=float(np.float16(2e-5))
 if cutoff_ceiling<2e-5:cutoff_ceiling=float(np.nextafter(np.float16(2e-5),np.float16(np.inf)))
 changed=visible[:,:,3]!=legacy_visible[:,:,3];visible_cells=legacy_visible[:,:,3]>cutoff_ceiling
 assert np.array_equal(visible[:,:,:3],legacy_visible[:,:,:3]) and np.array_equal(visible[visible_cells],legacy_visible[visible_cells]) and center_soot>0
 assert np.all(legacy_visible[:,:,3][changed]<=cutoff_ceiling) and np.count_nonzero(visible[:,:,3][changed])==0
 report['checks'].append({'gate':'cold binary16 soot plateau clears; visible smoke is bit identical to native legacy shader','pass':True,'plateauInput':1.621246337890625e-5,'plateauOutputNonzero':0,'legacyPlateauPeakAfterStep':legacy_peak,'visibleSootInput':float(np.float16(.1)),'visibleSootCenterAfterStep':center_soot,'cpuF16DecayReference':expected,'freshVisibleSootBitIdentical':True,'otherChemistryBitIdentical':True,'invisibleOutletCellsCleared':int(np.count_nonzero(changed)),'largestLegacySootCleared':float(legacy_visible[:,:,3][changed].max()) if changed.any() else 0.,'binary16CutoffCeiling':cutoff_ceiling})
 del visible
 assert GL.glGetError()==GL.GL_NO_ERROR
 if args.wood:
  import importlib.util
  spec=importlib.util.spec_from_file_location('original_wood_gl_gates',ROOT/'tools/fire-studio/original-wood-gl-gates.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.run(globals())
 report['pass']=True
except Exception as e:
 import traceback
 report['error']=str(e)[:12000];(out/'error.log').write_text(traceback.format_exc())
finally:
 (out/'native-report.json').write_text(json.dumps(report,indent=2))
 if window:glfw.destroy_window(window)
 glfw.terminate()
print(json.dumps({'path':str(out/'native-report.json'),'pass':report['pass'],'checks':len(report['checks']),'error':report.get('error'),'images':[str(p) for p in out.glob('*.png')]}))
if not report['pass']:raise SystemExit(1)
