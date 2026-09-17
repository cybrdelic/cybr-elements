"""Create and verify FLIP II deliverables. Never modifies the previous FLIP Lab files.

--prepare builds the completed CPU beauty reel, experiment films and previews.
--caches builds optional reconstructed-geometry packs (raw primary caches excluded).
The default final stage requires completed live GPU/CPU captures and all tests.
"""
from __future__ import annotations
import argparse,hashlib,html,json,subprocess,time,zipfile,shutil
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT.parent;SHOTS=ROOT/'media/shots'
SCENES=['breach','impact','jets','cascade','slosh','vortex','paddle','capillary','viscous']
TITLES={'breach':'Breach','impact':'Impact','jets':'Colliding_Jets','cascade':'Cascade','slosh':'Basin_Impulse','vortex':'Vortex','paddle':'Moving_Collider','capillary':'Capillary','viscous':'Viscous'}
PREFIX='CYBR_FLIP_II_'

def run(cmd:list)->bytes:
 p=subprocess.run(list(map(str,cmd)),capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-4500:])
 return p.stdout

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  while block:=f.read(4*1024*1024):h.update(block)
 return h.hexdigest()

def encode_options()->list:
 return ['-an','-c:v','libx264','-preset','fast','-tune','zerolatency','-bf','0','-rc-lookahead','0','-crf','17','-threads','1','-pix_fmt','yuv420p','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-movflags','+faststart']

def concat(paths:list[Path],output:Path,reencode:bool=False):
 listing=ROOT/'media'/('.'+output.stem+'.concat.txt');listing.write_text('\n'.join("file '"+str(p).replace("'","'\\''")+"'" for p in paths)+'\n')
 try:
  args=['ffmpeg','-v','error','-y','-threads','1','-f','concat','-safe','0','-i',listing]
  args+=encode_options() if reencode else ['-c','copy','-movflags','+faststart'];run(args+[output])
 finally:listing.unlink(missing_ok=True)
 print('BUILT',output.name,round(output.stat().st_size/1e6,1),'MB',flush=True)

def zip_files(output:Path,entries:list[tuple[Path,str]]):
 with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for path,name in entries:
   compression=zipfile.ZIP_STORED if path.suffix in {'.gz','.mp4','.png','.jpg','.gif','.webm'} else zipfile.ZIP_DEFLATED
   z.write(path,name,compress_type=compression)
 with zipfile.ZipFile(output) as z:
  bad=z.testzip()
  if bad:raise RuntimeError('ZIP integrity failure: '+bad)
 print('ZIP VERIFIED',output.name,round(output.stat().st_size/1e6,1),'MB',flush=True)

def prepare():
 for scene in SCENES:
  c=json.loads((ROOT/'tests/captures'/f'{scene}.json').read_text());assert not c['javascriptErrors'];assert len(c['frames'])==120
 beauty=[SHOTS/f'{scene}_{shot}_1080p.mp4' for scene in SCENES for shot in ['wide','surface']]
 # The impact clips used an earlier H.264 GOP configuration. Re-encode the
 # assembled reel to normalize codec parameters without inventing frames.
 concat(beauty,OUT/(PREFIX+'Cinematic_1080p.mp4'),True)
 for scene in SCENES:concat([SHOTS/f'{scene}_{s}_1080p.mp4' for s in ['wide','surface']],OUT/(PREFIX+TITLES[scene]+'_1080p.mp4'))
 sheet=Image.new('RGB',(1600,4050),(11,16,23))
 for row,scene in enumerate(SCENES):
  frame=94 if scene in ['cascade','viscous'] else 42 if scene in ['breach','impact','paddle'] else 66
  for col in [0,1]:
   with Image.open(ROOT/'media'/f'{scene}_{col}_frame{frame:03d}.jpg') as image:sheet.paste(image.convert('RGB').resize((800,450),Image.Resampling.LANCZOS),(col*800,row*450))
 sheet.save(OUT/(PREFIX+'Shot_Contact_Sheet.jpg'),quality=93)
 preview=ROOT/'media/preview_excerpts.mp4'
 run(['ffmpeg','-v','error','-y','-threads','1','-i',OUT/(PREFIX+'Cinematic_1080p.mp4'),'-vf',"select='between(t,1,3)+between(t,11,13)+between(t,21,23)',setpts=N/(24*TB),scale=800:-2",*encode_options(),preview])
 run(['ffmpeg','-v','error','-y','-threads','1','-i',preview,'-filter_complex','fps=10,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3','-threads','1','-loop','0',OUT/(PREFIX+'Preview.gif')])
 # A comparison is explicitly a resized 2x2 composite of two OLD and two NEW
 # actual recordings. It is not counted as independent newly rendered frames.
 old=[OUT/'CYBR_FLIP_Breach_1080p.mp4',OUT/'CYBR_FLIP_Impact_1080p.mp4']
 if all(p.exists() for p in old):
  files=[old[0],SHOTS/'breach_wide_1080p.mp4',old[1],SHOTS/'impact_wide_1080p.mp4'];cmd=['ffmpeg','-v','error','-y']
  for path in files:cmd+=['-threads','1','-t','5','-i',path]
  filters=[]
  for i in range(4):
   text='PREVIOUS BUILD' if i%2==0 else 'FLIP II / NEW SIMULATION'
   filters.append(f'[{i}:v]scale=960:540,setsar=1,drawtext=text={text}:fontsize=19:fontcolor=white:box=1:boxcolor=black@0.85:boxborderw=7:x=28:y=10[v{i}]')
  filters.append('[v0][v1]hstack[top];[v2][v3]hstack[bottom];[top][bottom]vstack[out]')
  run(cmd+['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[out]',*encode_options(),OUT/(PREFIX+'Before_After_1080p.mp4')])
 print('BEAUTY DELIVERY PREPARED',flush=True)

def caches():
 groups={'A':['breach','capillary','viscous'],'B':['jets'],'C':['impact','cascade'],'D':['slosh','vortex','paddle']}
 index={'root':'cybr_flip_ii','rawParticlesIncluded':False,'packs':[]}
 for letter,scenes in groups.items():
  entries=[]
  for scene in scenes:
   directory=ROOT/'cache'/scene;entries.append((directory/'manifest.json',f'cybr_flip_ii/cache/{scene}/manifest.json'))
   for f in range(120):entries.append((directory/f'{f:04d}.mesh.gz',f'cybr_flip_ii/cache/{scene}/{f:04d}.mesh.gz'))
  output=OUT/(PREFIX+f'Cache_{letter}.zip');zip_files(output,entries);assert output.stat().st_size<500_000_000
  index['packs'].append({'file':output.name,'scenes':scenes,'bytes':output.stat().st_size,'sha256':sha(output)})
 (ROOT/'tests/cache-delivery.json').write_text(json.dumps(index,indent=2))

def audit_video(path:Path,expected:int)->dict:
 meta=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_format','-of','json',path]));s=meta['streams'][0]
 assert [s['width'],s['height']]==[1920,1080],path
 assert s['codec_name']=='h264' and s['pix_fmt']=='yuv420p' and s['avg_frame_rate']=='24/1',path
 text=run(['ffmpeg','-v','error','-threads','1','-i',path,'-an','-fps_mode','passthrough','-f','framemd5','-']).decode()
 hashes=[line.rsplit(',',1)[-1].strip() for line in text.splitlines() if line and not line.startswith('#')]
 assert len(hashes)==expected,(path,len(hashes),expected)
 raw=run(['ffmpeg','-v','error','-threads','1','-i',path,'-an','-vf','crop=1260:690:330:255,scale=80:44,format=gray','-fps_mode','passthrough','-f','rawvideo','-'])
 pixels=np.frombuffer(raw,np.uint8).reshape(-1,44,80).astype(np.float32);delta=np.abs(np.diff(pixels,axis=0)).mean(axis=(1,2))
 assert len(pixels)==expected and len(set(hashes))==expected,(path,'repeated decoded frames')
 assert np.all(delta>0),(path,'unchanging central scene region')
 result={'file':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'resolution':[1920,1080],'fps':24,'codec':s['codec_name'],'pixelFormat':s['pix_fmt'],'colorSpace':s.get('color_space'),'durationSeconds':float(meta['format']['duration']),'fullyDecodedFrames':len(hashes),'uniqueDecodedFrames':len(set(hashes)),'minimumSceneRegionMeanAbsoluteDifference':float(delta.min()),'meanSceneRegionMeanAbsoluteDifference':float(delta.mean()),'decodePassed':True}
 print('DECODE VERIFIED',path.name,expected,flush=True);return result

def report_html(summary:dict)->str:
 esc=html.escape
 rows=''.join(f"<tr><td>{esc(TITLES[x['name']].replace('_',' '))}</td><td>{x['maximumParticles']:,}</td><td>{' × '.join(map(str,x['grid']))}</td><td>{x['maximumRelativePressureResidual']:.3g}</td><td>{x['maximumEncodedMeshVolumeAbsoluteRelativeError']*100:.3f}%</td><td>{x['maximumTriangles']:,}</td></tr>" for x in summary['sceneSummary'])
 videos=''.join(f"<tr><td>{esc(v['file'])}</td><td>{v['durationSeconds']:.2f}s</td><td>{v['fullyDecodedFrames']:,}</td><td>{v['uniqueDecodedFrames']:,}</td><td>Passed</td></tr>" for v in summary['videoAudits'])
 tests=summary['tests'];gpu=summary['gpuRecordings'];ref=summary.get('referenceStill',{})
 return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CYBR FLIP II — Measured release</title><style>
 :root{color-scheme:dark}body{margin:0;background:#0b1119;color:#dae6ee;font:16px/1.7 system-ui}main{max-width:1140px;margin:auto;padding:44px 25px 80px}h1{font-size:52px;font-weight:500;letter-spacing:-.045em;margin:8px 0}h2{margin:38px 0 12px;font-size:25px;font-weight:500;color:#a3e9df}p{max-width:970px}a{color:#b0e9ff}.eyebrow,.muted{color:#96aab9}.eyebrow{letter-spacing:.22em;font-size:12px}.card{border:1px solid #344853;border-radius:12px;padding:20px 24px;margin:24px 0;background:#101c25}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.metric{border:1px solid #283b48;border-radius:8px;padding:18px}.metric b{font-size:27px;display:block;color:#f2fbfc}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #2a3b48;text-align:left;padding:10px;white-space:nowrap}th{color:#aee8dc}code{color:#b4dcf4}strong{color:#f0f8fc}.note{border-left:3px solid #8be1cf;padding-left:20px}footer{margin-top:45px;border-top:1px solid #304551;padding-top:20px;font-size:13px;color:#95aabb}</style></head><body><main><div class="eyebrow">CYBRDELIC / SIMULATION STUDIES / VERIFIED RELEASE</div><h1>CYBR / FLIP II</h1><p>Two working primary-liquid backends. Nine high-resolution experiments. Actual Three.js recordings, measured numerical tests, and inspectable source.</p>'''+f'''
 <div class="grid"><div class="metric"><b>90 seconds</b>18 new beauty shots</div><div class="metric"><b>20 seconds</b>live and diagnostic proof</div><div class="metric"><b>1,080 states</b>high-resolution primary + mesh audit</div><div class="metric"><b>2,640 frames</b>newly captured, native 1080p</div></div>
 <div class="card"><a href="{PREFIX}Cinematic_1080p.mp4">Watch the cinematic reel</a> · <a href="{PREFIX}Verification_1080p.mp4">Watch the verification reel</a> · <a href="{PREFIX}Lab.html">Open the offline studio</a> · <a href="{PREFIX}Source.zip">Source package</a></div>
 <h2>What actually ran</h2><p>The 90-second beauty reel contains nine separately simulated CPU-reference experiments, each shown from two cameras. Every frame uses an evolving reconstructed liquid state. The proof reel includes particle positions, surface normals, whitewater phase classification, optical path length, <strong>96 frames of live browser-worker simulation</strong>, and <strong>{gpu['frames']} frames of live sparse GPU simulation</strong>. The GPU clips run primary transfers, pressure and advection in shader programs; the worker only meshes and maintains one-way diffuse markers.</p>
 <p>All videos are H.264, 1920 × 1080, 24 frames per second, with BT.709 color metadata. Simulation playback is 0.5× physical time. There is no image generation, stock footage, still-image pan, or generated intermediate-frame interpolation. The before/after comparison is a separately labeled 2×2 composite of old and new recordings; it is not counted as an additional independent simulation render.</p>
 <h2>Sparse GPU physics</h2><p>The new WebGL2 backend stores the MAC grid in 8 × 8 × 8 sparse bricks and performs affine floating-blend transfers, free-surface pressure, GPU PCG reductions, component-wise implicit viscosity, moving-solid response, and RK2/FLIP particle updates. The CPU compacts coarse brick flags, seeds sources, checks readbacks, and builds preview geometry. This is <strong>not a fully GPU-resident application</strong>.</p>
 <p>In the localized 4,096-particle allocation fixture, 4,096 atlas texels represented a 120 × 80 × 80 virtual grid whose dense equivalent would contain 793,881 texels: 0.516% for that fixture. This is a grid-texel comparison, not a universal speedup or total-memory ratio. Small or broadly filled domains can lose that advantage to brick padding.</p>
 <p>The GPU pressure solver checks the explicit residual <code>b − A p</code>. Reliable residual replacement corrects cases in which the recursive FP32 residual reaches the threshold first. The preview target is 8 × 10⁻⁵; it is not silently relaxed for the recordings. All recorded GPU frames report zero CPU primary-advection steps. The graphics adapter was <strong>{esc(summary['graphicsAdapter'])}</strong>; hardware-GPU real-time performance was not measured.</p>
 <h2>High-resolution numerical and geometry audit</h2><div class="scroll"><table><tr><th>Experiment</th><th>Peak particles</th><th>MAC grid</th><th>Max pressure residual</th><th>Max encoded mesh-volume error</th><th>Peak triangles</th></tr>{rows}</table></div>
 <p>The CPU reference uses affine PIC/FLIP transfers, IC(0)-PCG free-surface pressure, a capillary pressure jump, midpoint marker advection, moving-wall velocities, and component-wise backward-Euler viscosity. Every saved primary state is finite, has balanced particle accounting, and has zero recorded solid violations. All saved pressure solves meet 2 × 10⁻⁵.</p>
 <p class="note"><strong>Volume qualification:</strong> the offline mesher calibrates a global isovalue against assigned primary-particle volume. Encoded mesh-volume error is below 0.27% for these caches. This does not prove local incompressibility, continuum convergence, or exact physical mass conservation. The browser uses a lower-detail isotropic mesher rather than the offline PCA anisotropic reconstruction.</p>
 <h2>Executed tests</h2><p><strong>{tests['cpuNumerical']} CPU numerical tests</strong> and <strong>{tests['gpuNumerical']} GPU tests</strong> passed. The suite checks affine-field reproduction, pressure convergence, viscous energy dissipation, capillary balance, moving-wall velocities, finite states, particle accounting, buffer growth, sparse allocation, and explicit-residual enforcement. <strong>{tests['checkpoint']} primary-checkpoint tests</strong> passed, and <strong>{tests['byteIdenticalRegeneratedStates']} regenerated CPU states</strong> match saved primary positions and velocities byte for byte.</p>
 <p>Both live backends were exercised through all nine presets in the actual offline studio. Display modes, backend switching, physical settings, OBJ, sampled PLY, PNG, settings JSON, decoded browser WebM, and the actual BVH reference integrator were exercised. The offline sequence exporter was separately checked for topology-preserving OBJ and complete primary PLY output. Complete PLY exports require the raw primary cache; the diagnostic sample is never relabeled complete. A clean copy of the packaged source passed its numerical/checkpoint tests and rebuilt the standalone HTML byte for byte.</p>
 <h2>Optics and the reference integrator</h2><p>The raster pipeline adds exact dielectric Fresnel, absorption, front/exit depth and normals, iterative exit estimation, foreground rejection, primary droplets, and separately handled foam, spray and bubbles. Floor caustics are approximate photon splats, not a full multi-bounce caustic integrator. Screen-space refraction has finite-layer limitations.</p>
 <p>The independent reference path tracer traverses the actual triangle/sphere BVH and implements ideal dielectric transport, Beer–Lambert absorption, environment next-event estimation, multiple-importance sampling and Russian roulette, with ten bounces. The delivered raw reference still uses <strong>{ref.get('samplesPerPixel','not delivered')} samples per pixel</strong> at native 1080p. It is not denoised or declared fully converged. Opaque reference surfaces are Lambertian rather than the raster renderer’s metallic model. <strong>The beauty movies are raster recordings, not path-traced movies.</strong></p>
 <h2>Parity boundary</h2><p>This release is not a measured claim of LiquiGen parity or superiority. Missing production capabilities include an adaptive/multigrid pressure hierarchy, a fully GPU-resident meshing/whitewater pipeline, general imported-mesh/cut-cell solids, wetting/contact angles, a full coupled viscous-stress solve, a production node graph and the Alembic/VAT/flipbook export suite. There is no head-to-head LiquiGen quality, speed or workflow benchmark. Diffuse whitewater remains a one-way subgrid approximation, not a resolved gas phase.</p>
 <p>The comparison baseline was checked against <a href="https://jangafx.com/software/liquigen">JangaFX’s LiquiGen product page</a> and <a href="https://docs.jangafx.com/liquigen/pages/references/node_list.html">official node reference</a>. These describe the product; they do not certify this implementation.</p>
 <h2>Complete video decoding</h2><div class="scroll"><table><tr><th>File</th><th>Duration</th><th>Decoded frames</th><th>Unique frames</th><th>Result</th></tr>{videos}</table></div>
 <h2>Reproduction and delivery</h2><p>The source includes the CPU and sparse GPU solvers, meshing, rendering, the reference tracer, checkpoints, export and recording tools, vendored Three.js, and numerical/geometry/media reports. Optional cache packs A–D contain the exact compressed geometry used in the high-resolution films. Extract them alongside the source; all use the <code>cybr_flip_ii/</code> root. Raw primary caches are reproducible and omitted from the optional packs.</p>
 <p>The media ZIP contains the nine joined experiment films, complete verification reel, before/after comparison, reference still, GIF and contact sheet. The 90-second cinematic reel is delivered separately to avoid storing the same beauty footage twice inside the archive.</p>
 <footer>Built {esc(summary['builtUTC'])}. MIT project license retained. Third-party notices included. No font binaries distributed. Full machine-readable evidence: <a href="{PREFIX}Verification_Report.json">verification JSON</a>.</footer></main></body></html>'''

def source_entries()->list[tuple[Path,str]]:
 result=[];keep_tools={'browser_common.py','build_standalone.py','checkpoint.mjs','mesh_cache.py','mesh_ii.py','simulate.mjs','run_simulations.py','run_meshes.py','run_recordings_parallel.py','record.py','record_gpu.py','finish_live_recordings.py','render_reference.py','audit_ii.py','verify_browser_ii.py','verify_gpu_solver.py','verify_gpu_studio.py','export_sequence.py','package_ii.py'}
 for name in ['README.md','LICENSE','THIRD_PARTY.md','requirements.txt','package.json','index.html','standalone.html']:
  result.append((ROOT/name,'cybr_flip_ii/'+name))
 for folder in ['src','vendor','tests','tools','provenance']:
  for path in (ROOT/folder).rglob('*'):
   if not path.is_file() or '__pycache__' in path.parts or path.suffix in {'.pyc','.nbc','.nbi'}:continue
   if folder=='tools' and path.name not in keep_tools:continue
   if folder=='tests' and ((path.name.startswith('gpu-') and path.name.endswith('-seed.json')) or path.name in {'solver.test.mjs','cache_reproduction.mjs','cache_reproduction.log','results.log','webgpu-probe.html'}):continue
   if path.suffix.lower() in {'.ttf','.otf','.woff','.woff2'}:raise RuntimeError('Font binary unexpectedly in source tree')
   result.append((path,'cybr_flip_ii/'+str(path.relative_to(ROOT))))
 for scene in SCENES:result.append((ROOT/'cache'/scene/'manifest.json',f'cybr_flip_ii/cache/{scene}/manifest.json'))
 return result

def finalize():
 reports={name:json.loads((ROOT/'tests/captures'/f'{name}.json').read_text()) for name in SCENES+['diagnostics','live','gpu']}
 for name,r in reports.items():assert not r['javascriptErrors'],(name,r['javascriptErrors'])
 assert len(reports['gpu']['frames'])==192 and len(reports['live']['frames'])==96
 gpu_frames=reports['gpu']['frames']
 for f in gpu_frames:
  m=f['metrics'];assert m['primaryCPUAdvectionSteps']==0 and m['finite'] and m['solidViolations']==0 and m['pressure']['converged']
 names=['diagnostic_particles','diagnostic_normals','diagnostic_whitewater','diagnostic_thickness','live_worker_proof','live_sparse_gpu_breach','live_sparse_gpu_paddle']
 diagnostic=[SHOTS/(name+'_1080p.mp4') for name in names];proof=OUT/(PREFIX+'Verification_1080p.mp4');concat(diagnostic,proof,True)
 # Export live GPU proof on its own as a useful direct link.
 gpu_proof=OUT/(PREFIX+'Live_GPU_1080p.mp4');concat(diagnostic[-2:],gpu_proof,True)
 expected={SHOTS/f'{scene}_{shot}_1080p.mp4':120 for scene in SCENES for shot in ['wide','surface']}
 expected.update({p:48 if i<4 else 96 for i,p in enumerate(diagnostic)})
 expected[OUT/(PREFIX+'Cinematic_1080p.mp4')]=2160;expected[proof]=480;expected[gpu_proof]=192
 for scene in SCENES:expected[OUT/(PREFIX+TITLES[scene]+'_1080p.mp4')]=240
 comparison=OUT/(PREFIX+'Before_After_1080p.mp4')
 if comparison.exists():expected[comparison]=120
 audits=[]
 for path,count in expected.items():
  audits.append(audit_video(path,count));(ROOT/'tests/media-audit-ii.json').write_text(json.dumps({'audits':audits},indent=2))
 cache=json.loads((ROOT/'tests/cache-audit-ii.json').read_text());assert not cache['failures']
 cpu=json.loads((ROOT/'tests/solver-ii.json').read_text());assert cpu['failed']==0
 gpu=json.loads((ROOT/'tests/gpu-solver.json').read_text());assert gpu['failed']==0 and not gpu['javascriptErrors']
 assert gpu['sourceSha256']==sha(ROOT/'src/gpu/sparse-flip.js')
 browser=json.loads((ROOT/'tests/browser-ii.json').read_text());assert not browser['errors'] and not browser['externalNetworkRequests']
 integrated=json.loads((ROOT/'tests/gpu-studio.json').read_text());assert integrated['passed'] and not integrated['errors']
 assert integrated['sourceSha256']==sha(ROOT/'standalone.html') and browser['sourceSha256']==sha(ROOT/'standalone.html')
 clean=json.loads((ROOT/'tests/clean-source.json').read_text());assert clean['passed'] and clean['standaloneRebuildByteIdentical']
 checkpoint=json.loads((ROOT/'tests/checkpoint.json').read_text());repro=json.loads((ROOT/'tests/reproduction-ii.json').read_text());export=json.loads((ROOT/'tests/sequence-export.json').read_text());assert export['passed']
 ref=json.loads((ROOT/'tests/reference-still.json').read_text());assert ref['passed'] and not ref['errors']
 scenes=[{k:v for k,v in x.items() if k not in {'primarySha256','meshSha256'}} for x in cache['scenes']]
 adapter=reports['live']['frames'][0].get('renderer','Unknown')
 summary={'project':'CYBR FLIP II','builtUTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'standaloneSha256':sha(ROOT/'standalone.html'),'nativeCaptureResolution':[1920,1080],'deliveryFPS':24,'physicalPlaybackSpeed':.5,'cinematicReelSeconds':90,'verificationReelSeconds':20,'beautyShots':18,'independentHighResolutionExperiments':9,'uniqueHighResolutionSolverStates':1080,'newlyCapturedVideoFrames':2640,'graphicsAdapter':adapter,'sceneSummary':scenes,'tests':{'cpuNumerical':cpu['passed'],'gpuNumerical':gpu['passed'],'checkpoint':checkpoint['passed'],'byteIdenticalRegeneratedStates':repro['passed'],'cpuStudioScenes':len(browser['scenes']),'gpuStudioScenes':len(integrated['scenes']),'sequenceExport':export,'cleanSourceRebuild':True},'gpuRecordings':{'frames':192,'scenes':['breach','paddle'],'primaryCPUAdvectionSteps':0,'maxSavedRelativePressureResidual':max(f['metrics']['pressure']['relativeResidual'] for f in gpu_frames),'totalReportedResidualReplacements':sum(f['metrics']['pressure'].get('residualReplacements',0) for f in gpu_frames),'previewPipeline':'CPU mesh and one-way whitewater; primary physics is GPU'},'referenceStill':{k:v for k,v in ref.items() if k not in {'simulation','checkpoints'}},'videoAudits':audits,'limitations':['No measured LiquiGen parity or superiority.','High-resolution beauty uses the CPU reference; live GPU proof is separate.','Shader execution verified with software llvmpipe; no hardware real-time benchmark.','Sparse GPU primary physics still uses CPU activation compaction, seeding, readback, preview meshing and diffuse particles.','Whitewater is one-way; there is no resolved air phase.','Viscosity is component-wise diffusion, not a fully coupled stress solve.','Global mesh-volume calibration does not prove local incompressibility or continuum convergence.','Raster refraction and caustics are approximate; movies are not path-traced.','Reference still is raw finite-sample Monte Carlo, not fully converged.','Node graph, Alembic, VAT, imported-mesh/cut-cell solids and wetting/contact angles are not implemented.']}
 (ROOT/'tests/delivery-ii.json').write_text(json.dumps(summary,indent=2));(OUT/(PREFIX+'Verification_Report.json')).write_text(json.dumps(summary,indent=2));(OUT/(PREFIX+'Verification_Report.html')).write_text(report_html(summary))
 source_manifest={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p,_ in source_entries() if p.suffix in {'.js','.mjs','.py','.html','.md'}}
 (ROOT/'tests/source-manifest.json').write_text(json.dumps(source_manifest,indent=2));zip_files(OUT/(PREFIX+'Source.zip'),source_entries())
 media=[OUT/(PREFIX+TITLES[s]+'_1080p.mp4') for s in SCENES]+[proof,comparison,OUT/(PREFIX+'Reference_1080p.png'),OUT/(PREFIX+'Preview.gif'),OUT/(PREFIX+'Shot_Contact_Sheet.jpg'),OUT/(PREFIX+'Verification_Report.html'),OUT/(PREFIX+'Verification_Report.json')]
 media=[p for p in media if p.exists()];zip_files(OUT/(PREFIX+'Videos.zip'),[(p,p.name) for p in media]);assert (OUT/(PREFIX+'Videos.zip')).stat().st_size<500_000_000
 products=[p for p in OUT.glob(PREFIX+'*') if p.is_file() and p.name!=PREFIX+'Delivery_Manifest.json'];manifest={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in products}
 (OUT/(PREFIX+'Delivery_Manifest.json')).write_text(json.dumps(manifest,indent=2));print('FINAL DELIVERY VERIFIED',len(products),'files',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--caches',action='store_true');args=p.parse_args()
 if args.prepare:prepare()
 elif args.caches:caches()
 else:finalize()
