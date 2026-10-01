"""Compile and link actual exported Original startup programs in native GLES.

Run original-powers.test.mjs and original-startup.test.mjs with
FIRE_STUDIO_SHADER_OUTPUT set to this tool's output directory first. This gate
checks every exported production program. Actual gas fields, rendered timelines
and comparative timings belong to original-powers-render-qa.py; this compiler
never substitutes reduced-grid source probes for production visual evidence.
"""
import argparse,json,os,traceback
from pathlib import Path
import glfw
from OpenGL import GL

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path(os.environ.get('FIRE_STUDIO_ROOT',ROOT/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live')).resolve()
parser=argparse.ArgumentParser(description=__doc__,epilog='Requires the exclusive GPU lease. Reports stay on disk; native compile success does not measure browser FPS or visual quality.')
parser.add_argument('output',type=Path,help='Directory containing startup-*.json exports; native-powers-report.json is written here.')
parser.add_argument('--compile-only',action='store_true',help='Compatibility flag. Compile/link is now the only operation; obsolete six-source probes have been removed.')
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
report={'runtimeRoot':str(SOURCE),'scope':__doc__,'pass':False,'checks':[]};window=None

def compile(vertex,fragment,label):
 program=GL.glCreateProgram()
 for kind,source in [(GL.GL_VERTEX_SHADER,vertex),(GL.GL_FRAGMENT_SHADER,fragment)]:
  shader=GL.glCreateShader(kind);GL.glShaderSource(shader,source);GL.glCompileShader(shader)
  if not GL.glGetShaderiv(shader,GL.GL_COMPILE_STATUS):
   (out/(label+'-failed.glsl')).write_text(source)
   raise RuntimeError(label+': '+GL.glGetShaderInfoLog(shader).decode(errors='replace'))
  GL.glAttachShader(program,shader);GL.glDeleteShader(shader)
 GL.glLinkProgram(program)
 if not GL.glGetProgramiv(program,GL.GL_LINK_STATUS):
  raise RuntimeError(label+': '+GL.glGetProgramInfoLog(program).decode(errors='replace'))
 return program

try:
 files=sorted(out.glob('startup-*.json'))
 assert len(files)>=11,'Export production powers and normal startup cases first'
 if not glfw.init():raise RuntimeError('GLFW initialization failed')
 glfw.window_hint(glfw.VISIBLE,glfw.FALSE);glfw.window_hint(glfw.CLIENT_API,glfw.OPENGL_ES_API)
 glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3);glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,0)
 window=glfw.create_window(768,432,'Original startup GLSL compiler',None,None)
 if not window:raise RuntimeError('Hidden GLES 3 context unavailable')
 glfw.make_context_current(window)
 report['renderer']=GL.glGetString(GL.GL_RENDERER).decode();report['version']=GL.glGetString(GL.GL_VERSION).decode()
 cache={};total=0
 for file in files:
  data=json.loads(file.read_text());assert Path(data['runtimeRoot']).resolve()==SOURCE
  assert data['programs'],'No exported startup programs in '+file.name
  for index,item in enumerate(data['programs']):
   key=(item['vertex'],item['fragment'])
   if key not in cache:cache[key]=compile(*key,file.stem+'-'+str(index))
   total+=1
 report['checks'].append({'gate':'all production startup shader compile/link','pass':True,'cases':len(files),'programInstances':total,'uniquePrograms':len(cache)})
 report['pass']=True
except Exception as error:
 report['error']=str(error)[:12000];(out/'error.log').write_text(traceback.format_exc())
finally:
 (out/'native-powers-report.json').write_text(json.dumps(report,indent=2))
 if window:glfw.destroy_window(window)
 glfw.terminate()
print(json.dumps({'report':str(out/'native-powers-report.json'),'pass':report['pass'],'checks':len(report['checks']),'error':report.get('error'),'images':0}))
if not report['pass']:raise SystemExit(1)
