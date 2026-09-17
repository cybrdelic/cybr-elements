"""Build offline HTML with isolated lexical scope for every worker ES module."""
from pathlib import Path
import re,json,argparse
ROOT=Path(__file__).resolve().parents[1]
modules={};parts=[]
IMPORT=re.compile(r'^import\s*\{([^}]+)\}\s*from\s*[\'\"]([^\'\"]+)[\'\"]\s*;\s*',re.M)
def bundle(path):
 path=path.resolve()
 if path in modules:return modules[path]
 text=path.read_text();identifier='__module_'+str(len(modules));modules[path]=identifier
 def dependency(m):
  target=bundle(path.parent/m.group(2));bindings=','.join(re.sub(r'\s+as\s+',':',x.strip()) for x in m.group(1).split(','))
  return 'const {'+bindings+'}='+target+';\n'
 text=IMPORT.sub(dependency,text)
 exports=re.findall(r'\bexport\s+(?:class|function|const|let|var)\s+(\w+)',text)
 text=re.sub(r'\bexport\s+(?=(class|function|const|let|var)\b)','',text)
 if re.search(r'^import\b|^export\b',text,re.M):raise RuntimeError('Unsupported module syntax in '+str(path))
 parts.append('const '+identifier+'=(()=>{\n'+text+'\nreturn {'+','.join(exports)+'};\n})();')
 return identifier
bundle(ROOT/'src/worker.js');worker='\n'.join(parts);workerModuleCount=len(modules)
modules.clear();parts.clear();pipeline=bundle(ROOT/'src/production/scene-graph.js')
(ROOT/'src/production-browser.js').write_text('(()=>{\n'+'\n'.join(parts)+'\nglobalThis.CYBR_PIPELINE='+pipeline+';})();')
html=(ROOT/'index.html').read_text()
html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+(ROOT/m.group(1)).read_text().replace('</script','<\\/script')+'</script>',html)
html=html.replace('<head>','<head><script>window.__STANDALONE__=true;window.__WORKER_SOURCE__='+json.dumps(worker).replace('</script','<\\/script')+';</script>',1)
notices='\n\n'.join((ROOT/name).read_text() for name in ['LICENSE','vendor/THREE-LICENSE.txt','vendor/SCIKIT-IMAGE-LICENSE.txt'])
html=html.replace('</body>','<script type="text/plain" id="license-notices">'+notices.replace('</script','<\\/script')+'</script></body>')
(ROOT/'standalone.html').write_text(html)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'standalone.html');args=parser.parse_args()
output=args.output;output.parent.mkdir(parents=True,exist_ok=True);output.write_text(html)
print(output,output.stat().st_size,'worker modules',workerModuleCount)
