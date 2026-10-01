"""Focused gates called by ground-fuel-gl-qa.py --wood, using its GLES context.

The program strings are assembled by actual Original startup. No browser,
mesh simplification, fabricated fire, or CPU replacement of stock is involved.
"""
import json,math
import numpy as np
from PIL import Image

def run(g):
 GL=g['GL'];out=g['out'];SOURCE=g['SOURCE'];report=g['report']
 texture,target,begin,bind,u,draw,read,clear=[g[n] for n in ['texture','target','begin','bind','u','draw','read','clear']]
 select=g['select'];ground=select('out vec4 state;')
 # A constant deposit lets every texel be compared with the shared CPU model.
 floor=[target(128,128,True),target(128,128,True)];wear=[target(128,128,True),target(128,128,True)]
 for i in range(2):
  GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,floor[i][1]);GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT1,GL.GL_TEXTURE_2D,wear[i][0],0);GL.glDrawBuffers(2,[GL.GL_COLOR_ATTACHMENT0,GL.GL_COLOR_ATTACHMENT1])
  assert GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)==GL.GL_FRAMEBUFFER_COMPLETE
 stamp=texture(128,128,np.full((128,128),1.5,np.float16),GL.GL_R16F,GL.GL_RED)
 ci=0;chemistry=g['chemistry'];bounds=g['bounds']
 def floor_step(deposit=False,ignite=False,heat=0.,enabled=True,dt=1/30):
  nonlocal ci
  clear(chemistry,[0,1,heat,0]);begin(ground,floor[1-ci])
  for unit,name,t in [(0,'groundOld',floor[ci][0]),(1,'groundStamp',stamp),(2,'chemTex',chemistry[0]),(3,'groundWearOld',wear[ci][0])]:bind(ground,name,t,unit)
  u(ground,'groundBounds',*bounds)
  for name,v in [('groundDeposit',float(deposit)),('groundIgnition',float(ignite)),('groundCombustion',float(enabled)),('groundWood',1),('woodTimeScale',12),('delta',dt)]:u(ground,name,v)
  draw();ci=1-ci
 floor_step(True,dt=0);cold=read(floor[ci]);cold_wear=read(wear[ci]);assert np.all(cold[:,:,0]==1.5)
 cold_k=300+1200*cold[:,:,1];assert np.max(np.abs(cold_k-293.15))<.0001 and np.count_nonzero(cold[:,:,2:])==0
 for _ in range(30):floor_step(heat=1,enabled=False)
 assert np.array_equal(cold,read(floor[ci])) and np.array_equal(cold_wear,read(wear[ci]))
 report['checks'].append({'gate':'Original dropped wood preserves signed293.15K cold state and stock in smoke mode','pass':True,'dryKgM2':1.5,'coldK':float(cold_k[0,0]),'smokeModeMassChanged':False})
 floor_step(ignite=True);first=read(floor[ci]);first_wear=read(wear[ci]);assert first[0,0,1]>cold[0,0,1]
 for _ in range(29):floor_step(heat=1)
 hot=read(floor[ci]);hot_wear=read(wear[ci]);assert np.isfinite(hot).all() and np.isfinite(hot_wear).all()
 assert hot[0,0,0]<1.49 and hot[0,0,3]>0 and hot[0,0,2]>0 and hot_wear[0,0,1]<cold_wear[0,0,1]
 reference=json.loads((out/'floor-wood-reference.json').read_text())
 for title,actual,expected in [('firstStock',first[0,0],reference['first']['stock']),('firstWear',first_wear[0,0],reference['first']['wear']),('hotStock',hot[0,0],reference['hot']['stock']),('hotWear',hot_wear[0,0],reference['hot']['wear'])]:
  error=float(np.max(np.abs(actual-np.array(expected))));assert error<.003,(title,error,actual,expected)
 report['checks'].append({'gate':'Original floor uses shared finite drying/pyrolysis/char equations and bounded ignition','pass':True,'stockAt1s':hot[0,0].astype(float).tolist(),'wearAt1s':hot_wear[0,0].astype(float).tolist(),'sharedCPUReferenceMaxAbsoluteTolerance':.003})
 # The actual Original gas program gets only volatile release from the bed.
 original_inventory,original_ci=g['inventory'],g['ci'];g['inventory']=floor;g['ci']=ci;clear(chemistry,[0,1,0,0])
 for _ in range(12):
  g['gas_step']();GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER,g['gas'][1]);GL.glReadBuffer(GL.GL_COLOR_ATTACHMENT0);GL.glActiveTexture(GL.GL_TEXTURE1);GL.glBindTexture(GL.GL_TEXTURE_2D,chemistry[0]);GL.glCopyTexSubImage2D(GL.GL_TEXTURE_2D,0,0,0,0,0,chemistry[2],chemistry[3])
 gas=read(g['gas']);reaction=read(g['gas_vf'])[:,:,3]
 assert gas[:,:,0].max()>0 and gas[:,:,2].max()>0 and gas[:,:,3].max()>0 and reaction.max()>0
 report['checks'].append({'gate':'Original wood volatiles ignite in normal gas combustion with main source and brush disabled','pass':True,'gasSteps':12,'maxFuelOxygenTemperatureSoot':gas.max(axis=(0,1)).astype(float).tolist(),'maxReaction':float(reaction.max())})
 g['inventory'],g['ci']=original_inventory,original_ci
 # Use the compiled production programs for exact projected wood capacity,
 # current subtree load and mechanics. Logs provide a compact contact fixture.
 record=json.loads((out/'startup-bonfire.json').read_text())
 wanted=['out vec4 capacity;','out vec4 nextStock;','massDonors','woodPhase','scanInit','flat in vec4 rootData','woodMaterialId']
 pairs=[]
 for needle in wanted:
  item=next(s for s in record['programs'] if needle in s['fragment']);pairs.append(g['compile'](item['vertex'],item['fragment'],'wood-'+needle.split()[-1].replace(';','')))
 capacity_p,update_p,mass_p,mechanics_p,scan_p,root_p,mesh_p=pairs
 fixture=json.loads((out/'logs-fixture.json').read_text());graph_data=np.fromfile(out/'logs-graph.f32.bin',np.float32).reshape(fixture['height'],48,4);donor_data=np.fromfile(out/'logs-donors.f32.bin',np.float32).reshape(fixture['massHeight'],256,4)
 def f32tex(a):return texture(a.shape[1],a.shape[0],a,GL.GL_RGBA32F,GL.GL_RGBA,GL.GL_FLOAT,GL.GL_NEAREST)
 graph=[target(48,fixture['height'],True),target(48,fixture['height'],True)]
 def upload(t,a):GL.glBindTexture(GL.GL_TEXTURE_2D,t[0]);GL.glTexSubImage2D(GL.GL_TEXTURE_2D,0,0,0,a.shape[1],a.shape[0],GL.GL_RGBA,GL.GL_FLOAT,a)
 for t in graph:upload(t,graph_data)
 mass_source=f32tex(donor_data);mass=[target(256,fixture['massHeight'],True),target(256,fixture['massHeight'],True)]
 stock=[target(256,256,True),target(256,256,True)];wood_wear=[target(256,256,True),target(256,256,True)];capacity=target(256,256,True)
 roots=target(8,math.ceil((fixture['nodes']+1)/4),True);scan=[target(4,fixture['rows'],True),target(4,fixture['rows'],True)]
 scale=1.;centre=[0,.64];origin=[*centre,0];wood_bounds=[-1.5,-.86,1.5,2.14];sigma=.36
 domain=record['domain'];nx,ny,depth=domain['nx'],domain['ny'],domain['depth'];w,h=nx*8,ny*(depth//8)
 chem=target(w,h);clear(chem,[0,1,0,0])
 source=g['source'];proxy=int(GL.glGenTextures(1));GL.glActiveTexture(GL.GL_TEXTURE14);GL.glBindTexture(GL.GL_TEXTURE_3D,proxy)
 for param in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_3D,param,GL.GL_NEAREST)
 for param in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T,GL.GL_TEXTURE_WRAP_R]:GL.glTexParameteri(GL.GL_TEXTURE_3D,param,GL.GL_CLAMP_TO_EDGE)
 GL.glTexImage3D(GL.GL_TEXTURE_3D,0,GL.GL_RGBA16F,64,64,64,0,GL.GL_RGBA,GL.GL_HALF_FLOAT,np.fromfile(SOURCE/'pyro-gpu/objects/logs/solid.rgba16.bin',np.float16))
 si=0
 def wood_bind(p,mechanics=True):
  for unit,name,t in [(5,'woodStockTex',stock[si][0]),(6,'woodWearTex',wood_wear[si][0]),(7,'woodCapacityTex',capacity[0]),(11,'woodMechanicsTex',graph[0][0]),(12,'woodRootsTex',roots[0])]:bind(p,name,t,unit)
  u(p,'woodBounds',*wood_bounds);u(p,'woodSigma',sigma);u(p,'woodBark',0);u(p,'woodEnabled',1);u(p,'woodMechanicsEnabled',float(mechanics));u(p,'woodRestScale',scale);u(p,'woodRestOrigin',*origin);GL.glUniform1i(GL.glGetUniformLocation(p,'woodNodesCount'),fixture['nodes'])
 def wood_config(p):
  wood_bind(p);u(p,'woodCentre',*centre);u(p,'woodScale',scale);GL.glUniform1i(GL.glGetUniformLocation(p,'woodKind'),3)
 GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,capacity[1])
 for attachment,t in [(GL.GL_COLOR_ATTACHMENT1,stock[0][0]),(GL.GL_COLOR_ATTACHMENT2,wood_wear[0][0])]:GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,attachment,GL.GL_TEXTURE_2D,t,0)
 GL.glDrawBuffers(3,[GL.GL_COLOR_ATTACHMENT0,GL.GL_COLOR_ATTACHMENT1,GL.GL_COLOR_ATTACHMENT2]);begin(capacity_p,capacity);wood_config(capacity_p);u(capacity_p,'woodMoisture',.08)
 bind(capacity_p,'sourceTex',source,2);GL.glActiveTexture(GL.GL_TEXTURE14);GL.glBindTexture(GL.GL_TEXTURE_3D,proxy);GL.glUniform1i(GL.glGetUniformLocation(capacity_p,'objectTex'),14);draw()
 cap=read(capacity);initial_stock=read(stock[0]);assert np.isfinite(cap).all() and initial_stock[:,:,0].max()==1
 initial_kg=float(cap[:,:,0].sum(dtype=np.float64))*(3/256)**2;expected_kg=sum(donor_data.reshape(-1,4)[:fixture['donors'],2].astype(np.float64));assert abs(initial_kg-expected_kg)/expected_kg<.00001
 for i in range(2):
  GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,stock[i][1]);GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER,GL.GL_COLOR_ATTACHMENT1,GL.GL_TEXTURE_2D,wood_wear[i][0],0);GL.glDrawBuffers(2,[GL.GL_COLOR_ATTACHMENT0,GL.GL_COLOR_ATTACHMENT1])
 # Mass from16 current material texels per projected donor, not bond-local
 # consumption. Prefix values are checked against a double CPU reference.
 def mass_step():
  current=0;begin(mass_p,mass[0]);wood_bind(mass_p);bind(mass_p,'massSource',mass_source,0);GL.glUniform1i(GL.glGetUniformLocation(mass_p,'scanInit'),1);GL.glUniform1i(GL.glGetUniformLocation(mass_p,'massDonors'),fixture['donors']);draw()
  offset=1
  while offset<fixture['donors']:
   begin(mass_p,mass[1-current]);bind(mass_p,'scanOld',mass[current][0],0);GL.glUniform1i(GL.glGetUniformLocation(mass_p,'scanInit'),0);GL.glUniform1i(GL.glGetUniformLocation(mass_p,'scanOffset'),offset);draw();current=1-current;offset*=2
  return current
 mi=mass_step();prefix=read(mass[mi]).reshape(-1,4)[:fixture['donors'],0];expected=np.cumsum(donor_data.reshape(-1,4)[:fixture['donors'],2].astype(np.float64));assert np.max(np.abs(prefix-expected))<expected[-1]*2e-6
 report['checks'].append({'gate':'Original projected capacity and current subtree load conserve corrected thermal donor mass','pass':True,'initialModelKg':initial_kg,'massPrefixKg':float(prefix[-1]),'maximumPrefixErrorKg':float(np.max(np.abs(prefix-expected))),'donors':fixture['donors']})
 def mechanics_step(dt=1/30):
  nonlocal mi
  mi=mass_step()
  for phase in range(2):
   begin(mechanics_p,graph[1-phase]);wood_bind(mechanics_p);bind(mechanics_p,'woodMechanicsTex',graph[phase][0],11);bind(mechanics_p,'woodMassTex',mass[mi][0],12);u(mechanics_p,'woodDelta',dt);u(mechanics_p,'woodForce',0,0,0);GL.glUniform1i(GL.glGetUniformLocation(mechanics_p,'woodPhase'),phase);draw()
  current=0;begin(scan_p,scan[0]);bind(scan_p,'woodMechanicsTex',graph[0][0],0);GL.glUniform1i(GL.glGetUniformLocation(scan_p,'scanInit'),1);GL.glUniform1i(GL.glGetUniformLocation(scan_p,'woodNodesCount'),fixture['nodes']);draw();offset=1
  while offset<fixture['nodes']:
   begin(scan_p,scan[1-current]);bind(scan_p,'scanOld',scan[current][0],0);GL.glUniform1i(GL.glGetUniformLocation(scan_p,'scanInit'),0);GL.glUniform1i(GL.glGetUniformLocation(scan_p,'scanOffset'),offset);draw();current=1-current;offset*=2
  begin(root_p,roots);clear(roots,[0,0,0,0]);bind(root_p,'scanOld',scan[current][0],0);bind(root_p,'woodMechanicsTex',graph[0][0],1);u(root_p,'woodRestOrigin',*origin);u(root_p,'woodRestScale',scale);GL.glUniform1i(GL.glGetUniformLocation(root_p,'woodNodesCount'),fixture['nodes']);GL.glDrawArrays(GL.GL_POINTS,0,(fixture['nodes']+1)*2)
 mechanics_step();root_data=read(roots);assert root_data[0,0,0]==0,'Cold logs may not fracture';cold_graph=read(graph[0]);assert np.isfinite(cold_graph).all()
 # Force one bond's failure only for the mechanics fixture; material and mesh
 # ownership must then move with its actual rigid pose. No emitter is active.
 represented=set()
 for donor in donor_data.reshape(-1,4)[:fixture['donors']]:
  x,y=map(int,donor[:2]);z=max(0,min(63,int(math.floor((float(cap[y+1,x+1,1])+1.5)*64/3))));code=x//4+64*(y//4+64*z);represented.add(int(graph_data[fixture['rows']+code//4//48,(code//4)%48,code%4]))
 piece=next(i for i in sorted(represented) if graph_data[i//4,(i%4)*12+2,3]<.5);piece_row,piece_col=piece//4,(piece%4)*12
 broken=graph_data.copy();broken[piece_row,piece_col+7,3]=1.;upload(graph[0],broken);mechanics_step();posed=read(graph[0]);root_data=read(roots);assert root_data[0,0,0]>=1
 moved=float(np.linalg.norm(posed[piece_row,piece_col+4,:3]-graph_data[piece_row,piece_col+4,:3]));assert moved>0
 report['checks'].append({'gate':'Original cold structure stays intact; broken bond compacts an actual moving rigid piece','pass':True,'coldDetachedRoots':0,'brokenDetachedRoots':int(root_data[0,0,0]),'firstPieceDisplacementModelM':moved})
 # Rest inventory stays in material coordinates. Place the failed rigid piece
 #1.2m farther right in the fixture and check both directions of coupling:
 # current gas heats its rest stock; its rest volatile inventory feeds gas
 # at its new position and not at the previous one.
 shifted=posed.copy();shifted[piece_row,piece_col+4,0]+=1.2;upload(graph[0],shifted);mechanics_step(0);shifted=read(graph[0])
 donor_indices=[]
 for i,donor in enumerate(donor_data.reshape(-1,4)[:fixture['donors']]):
  x,y=map(int,donor[:2]);z=max(0,min(63,int(math.floor((float(cap[y+1,x+1,1])+1.5)*64/3))));code=x//4+64*(y//4+64*z);owner=int(graph_data[fixture['rows']+code//4//48,(code//4)%48,code%4]);pose_row,pose_col=owner//4,(owner%4)*12+4
  if int(shifted[pose_row,pose_col,3])==piece:donor_indices.append(i)
 assert donor_indices,'Fixture must have a real projected donor on the failed piece'
 donor=donor_data.reshape(-1,4)[max(donor_indices,key=lambda i:donor_data.reshape(-1,4)[i,2])];x,y=map(int,donor[:2]);px,py=x+1,y+1
 rest=np.array([(px+.5)*3/256-1.5,centre[1]+(py+.5)*3/256-1.5,float(cap[py,px,1])]);current=rest+np.array([1.2,0,0])
 # The rigid piece's quaternion is slightly rotated by actual failure motion.
 root_rest=graph_data[piece_row,piece_col,:3];root_pos=shifted[piece_row,piece_col+4,:3];q=shifted[piece_row,piece_col+5];local=rest-np.array(origin)-root_rest;t=2*np.cross(q[:3],local);current=np.array(origin)+root_pos+local+q[3]*t+np.cross(q[:3],t)
 clear(chem,[0,1,0,0]);GL.glEnable(GL.GL_SCISSOR_TEST)
 minimum=np.array(domain['minimum']);extent=np.array(domain['extent']);dx=.11;lx=max(0,int((current[0]-dx-minimum[0])/extent[0]*nx));hx=min(nx,int((current[0]+dx-minimum[0])/extent[0]*nx)+1);ly=max(0,int((current[1]-dx-minimum[1])/extent[1]*ny));hy=min(ny,int((current[1]+dx-minimum[1])/extent[1]*ny)+1)
 GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,chem[1])
 for layer in range(depth):GL.glScissor((layer%8)*nx+lx,(layer//8)*ny+ly,hx-lx,hy-ly);GL.glClearBufferfv(GL.GL_COLOR,0,np.array([0,1,1,0],np.float32))
 GL.glDisable(GL.GL_SCISSOR_TEST)
 initial_wear=read(wood_wear[0])
 def thermal_step():
  begin(update_p,stock[1]);wood_config(update_p);bind(update_p,'chemTex',chem[0],1);bind(update_p,'sourceTex',source,2);u(update_p,'delta',1/30);u(update_p,'woodAge',100);u(update_p,'woodClock',100);u(update_p,'woodStarter',0);u(update_p,'woodTimeScale',12);GL.glUniform1i(GL.glGetUniformLocation(update_p,'woodVariation'),0);draw();return read(stock[1])
 posed_heat=thermal_step();upload(graph[0],graph_data);unposed_heat=thermal_step();assert posed_heat[py,px,1]>unposed_heat[py,px,1]+.02
 upload(graph[0],shifted);mechanics_step(0)
 emitted=initial_stock.copy();emitted[py,px]=[.9,1.5,.01,.03];upload(stock[0],emitted)
 update_source=next(s for s in record['programs'] if 'out vec4 nextStock;' in s['fragment']);probe_source=update_source['fragment'].split('layout(location=0) out vec4 nextStock;')[0]+'''uniform vec3 qaPoint;layout(location=0) out vec4 value;void main(){float fuel=0.,oxygen=1.,temp=0.;float added=woodFuelGas(qaPoint,1./30.,fuel,oxygen,temp);value=vec4(added,fuel,temp,oxygen);}'''
 probe_p=g['compile'](update_source['vertex'],probe_source,'posed-source-probe');probe_target=target(1,1,True)
 def probe(at):begin(probe_p,probe_target);wood_bind(probe_p);u(probe_p,'qaPoint',*at);draw();return read(probe_target)[0,0]
 rest_release=probe(rest);posed_release=probe(current);assert posed_release[0]>.00001 and rest_release[0]<posed_release[0]*.001,(rest_release,posed_release)
 report['checks'].append({'gate':'Original rigid pieces carry rest stock: actual gas heats moved wood and volatile release follows its pose','pass':True,'posedWoodHeat':float(posed_heat[py,px,1]),'sameStockHeatWithoutPose':float(unposed_heat[py,px,1]),'fuelAtNewLocation':float(posed_release[0]),'fuelAtOldLocation':float(rest_release[0]),'sourcePointOld':rest.tolist(),'sourcePointNew':current.tolist()})
 upload(stock[0],initial_stock);upload(wood_wear[0],initial_wear);upload(graph[0],graph_data)
 # The mesh gate uses exact companion vertices, cap owner pairs and actual
 # tree bark textures. Rendering is kept independent of unverified fire flow.
 render_target=target(640,360);depth_buffer=GL.glGenRenderbuffers(1);GL.glBindRenderbuffer(GL.GL_RENDERBUFFER,depth_buffer);GL.glRenderbufferStorage(GL.GL_RENDERBUFFER,GL.GL_DEPTH_COMPONENT24,640,360);GL.glBindFramebuffer(GL.GL_FRAMEBUFFER,render_target[1]);GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER,GL.GL_DEPTH_ATTACHMENT,GL.GL_RENDERBUFFER,depth_buffer)
 draw_items=[]
 def mesh_buffers(base,manifest):
  result=[]
  for vertices,indices,owners,count in [('vertices.bin','indices.bin','owners.bin',manifest['partitionTriangles']*3),('cap-vertices.bin','cap-indices.bin','cap-owner-pairs.bin',manifest['caps']['triangles']*3)]:
   vao=GL.glGenVertexArrays(1);GL.glBindVertexArray(vao)
   for name,target_kind in [(vertices,GL.GL_ARRAY_BUFFER),(owners,GL.GL_ARRAY_BUFFER),(indices,GL.GL_ELEMENT_ARRAY_BUFFER)]:
    raw=(base/name).read_bytes();buffer=GL.glGenBuffers(1);GL.glBindBuffer(target_kind,buffer);GL.glBufferData(target_kind,len(raw),raw,GL.GL_STATIC_DRAW)
    import ctypes
    if name==vertices:
     for index,size,offset in [(0,3,0),(1,3,12),(3,1,32),(4,2,24)]:GL.glEnableVertexAttribArray(index);GL.glVertexAttribPointer(index,size,GL.GL_FLOAT,False,36,ctypes.c_void_p(offset))
    elif name==owners:GL.glEnableVertexAttribArray(2);GL.glVertexAttribIPointer(2,2,GL.GL_UNSIGNED_INT,8,ctypes.c_void_p(0))
   result.append((vao,count))
  return result
 base=SOURCE/fixture['base'];manifest=json.loads((base/'manifest.json').read_text());draw_items=mesh_buffers(base,manifest)
 white=texture(1,1,np.full((1,1,4),255,np.uint8),GL.GL_RGBA8,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE)
 mesh_materials=[white,white,white];mesh_bark=2
 def mesh_image(name,yaw=16):
  begin(mesh_p,render_target);GL.glClearBufferfv(GL.GL_COLOR,0,np.array([0,0,0,1000],np.float32));GL.glClearBufferfv(GL.GL_DEPTH,0,np.array([1],np.float32));GL.glEnable(GL.GL_DEPTH_TEST);GL.glDepthFunc(GL.GL_LESS);wood_bind(mesh_p);bind(mesh_p,'woodMechanicsTex',graph[0][0],3)
  for i,key in enumerate(['woodBarkTex','woodMicroTex','woodRoughnessTex']):bind(mesh_p,key,mesh_materials[i],i)
  u(mesh_p,'woodBark',mesh_bark);u(mesh_p,'roomEnabled',1);u(mesh_p,'cameraTan',.3443276);u(mesh_p,'ambientLight',2,2,2);u(mesh_p,'inspectionLight',0);u(mesh_p,'fireLightGain',0);u(mesh_p,'customLighting',1)
  angle=math.radians(yaw);eye=np.array([math.sin(angle)*6,2.6,math.cos(angle)*6]);forward=np.array([0,.6,0])-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,forward)
  for key,value in [('Eye',eye),('Forward',forward),('Right',right),('Up',up)]:u(mesh_p,'camera'+key,*value)
  for vao,count in draw_items:GL.glBindVertexArray(vao);GL.glDrawElements(GL.GL_TRIANGLES,count,GL.GL_UNSIGNED_INT,None)
  GL.glDisable(GL.GL_DEPTH_TEST);GL.glBindVertexArray(GL.glGenVertexArrays(1));pixels=read(render_target);assert np.isfinite(pixels).all();visible=pixels[:,:,3]<1000;assert visible.sum()>100
  # Presentation gamma is kept explicit for this surface-only diagnostic.
  rgb=np.clip(pixels[:,:,:3],0,1);rgb=np.where(rgb<=.0031308,rgb*12.92,1.055*rgb**(1/2.4)-.055);Image.fromarray((np.clip(rgb[::-1],0,1)*255+.5).astype(np.uint8)).save(out/(name+'.png'));return visible,pixels
 upload(graph[0],graph_data);initial_mask,initial_image=mesh_image('logs-intact');upload(graph[0],posed);moved_mask,moved_image=mesh_image('logs-posed');assert np.count_nonzero(initial_image!=moved_image)>100
 report['checks'].append({'gate':'Exact Original companion mesh and caps render with physical stock and rigid pose','pass':True,'triangles':manifest['partitionTriangles']+manifest['caps']['triangles'],'intactPixels':int(initial_mask.sum()),'posedPixels':int(moved_mask.sum()),'changedPixels':int(np.count_nonzero(np.any(initial_image!=moved_image,axis=2)))})
 # Reviewed forest geometry and its three actual bark images stay intact in
 # the independent mesh stage. All triangles render; no display proxy is used.
 tree_record=json.loads((out/'startup-cybr-tree.json').read_text());tree_shader=next(s for s in tree_record['programs'] if 'woodMaterialId' in s['fragment']);mesh_p=g['compile'](tree_shader['vertex'],tree_shader['fragment'],'reviewed-tree-mesh')
 fixture=json.loads((out/'cybr-tree-fixture.json').read_text());graph_data=np.fromfile(out/'cybr-tree-graph.f32.bin',np.float32).reshape(fixture['height'],48,4);graph=[target(48,fixture['height'],True)];upload(graph[0],graph_data)
 centre=[0,1.35];origin=[*centre,0];wood_bounds=[-1.5,-.15,1.5,2.85]
 GL.glActiveTexture(GL.GL_TEXTURE14);GL.glBindTexture(GL.GL_TEXTURE_3D,proxy);GL.glTexSubImage3D(GL.GL_TEXTURE_3D,0,0,0,0,64,64,64,GL.GL_RGBA,GL.GL_HALF_FLOAT,np.fromfile(SOURCE/'pyro-gpu/objects/forest-tree/wood-solid.rgba16.bin',np.float16))
 begin(capacity_p,capacity);wood_config(capacity_p);u(capacity_p,'woodMoisture',.06060606);GL.glActiveTexture(GL.GL_TEXTURE14);GL.glBindTexture(GL.GL_TEXTURE_3D,proxy);draw()
 base=SOURCE/fixture['base'];manifest=json.loads((base/'manifest.json').read_text());draw_items=mesh_buffers(base,manifest);mesh_bark=1
 white_mask,white_image=mesh_image('tree-without-authored-bark',16)
 mesh_materials=[]
 for index,name in enumerate(['bark-color.png','bark-micro.png','bark-roughness.png']):
  with Image.open(SOURCE/'pyro-gpu/objects/forest-tree'/name) as image:rgba=np.asarray(image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)).copy()
  t=texture(rgba.shape[1],rgba.shape[0],rgba,GL.GL_SRGB8_ALPHA8 if index==0 else GL.GL_RGBA8,GL.GL_RGBA,GL.GL_UNSIGNED_BYTE);GL.glBindTexture(GL.GL_TEXTURE_2D,t)
  for p in [GL.GL_TEXTURE_MIN_FILTER,GL.GL_TEXTURE_MAG_FILTER]:GL.glTexParameteri(GL.GL_TEXTURE_2D,p,GL.GL_LINEAR)
  for p in [GL.GL_TEXTURE_WRAP_S,GL.GL_TEXTURE_WRAP_T]:GL.glTexParameteri(GL.GL_TEXTURE_2D,p,GL.GL_REPEAT)
  mesh_materials.append(t)
 actual_mask,actual_image=mesh_image('tree-authored-bark',16);mesh_image('tree-authored-bark-side',74)
 changed=int(np.count_nonzero(np.any(actual_image[:,:,:3]!=white_image[:,:,:3],axis=2)));assert changed>500 and np.array_equal(actual_mask,white_mask)
 report['checks'].append({'gate':'Original retains exact reviewed tree mesh and actual color/micro/roughness bark maps','pass':True,'ordinaryTriangles':manifest['partitionTriangles'],'capTriangles':manifest['caps']['triangles'],'barkChangedPixels':changed,'meshSilhouetteIdentical':True,'viewsDegrees':[16,74]})
 assert GL.glGetError()==GL.GL_NO_ERROR
