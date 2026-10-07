import path from 'node:path';
export function stats(values) {
  if(!values.length)return null;
  const ordered=[...values].sort((a,b)=>a-b);
  const percentile=p=>ordered[Math.min(ordered.length-1,Math.ceil(ordered.length*p)-1)];
  return {count:values.length,mean:values.reduce((a,b)=>a+b,0)/values.length,
    median:percentile(.5),p95:percentile(.95),max:ordered.at(-1)};
}
export function resolveAsset(root,pathname) {
  const decoded=decodeURIComponent(pathname);
  if(decoded.includes('\0'))throw Error('Invalid path');
  const file=path.resolve(root,'.'+decoded);
  const relative=path.relative(root,file);
  if(relative.startsWith('..')||path.isAbsolute(relative))throw Error('Path outside server root');
  return file;
}
export function performanceSummary(probe,seconds) {
  const intervals=stats(probe.frames);
  return {webGpuStageMs:Object.fromEntries(['total','source','flow','pressure','chemistry','auxiliary','lighting','render'].map((name,i)=>[name,stats((probe.gpuStages||[]).map(row=>row[i]))])),browserRafFps:intervals?1000/intervals.mean:null,frameIntervalMs:intervals,
    framesOver50ms:probe.frames.filter(v=>v>50).length,
    drawsPerSecond:probe.draws/seconds,sampledOriginalSubmissionGpuMs:stats(probe.gpu),
    cpuLongTaskMs:stats(probe.longTasks),renderer:probe.renderer,adapter:probe.adapter,
    softwareRenderer:/swiftshader|llvmpipe|software|basic render/i.test(probe.renderer||'')||probe.adapter?.fallback===true,
    gpuStageSource:probe.gpuStageSource||'HUD snapshots',
    notes:['Browser RAF cadence is not simulation FPS.','GPU samples cover Original submissions from first draw to flush; WebGPU stages use completed timestamp readbacks when the diagnostic API is available.']};
}

export function simulationAdvanced(start,end){
  if(Number.isFinite(start.simulationTime)&&Number.isFinite(end.simulationTime))return end.simulationTime>start.simulationTime;
  return end.metrics!==start.metrics;
}
