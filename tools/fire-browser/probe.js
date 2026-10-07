// Runs before the app. Diagnostics stay bounded and do not read back textures.
export function installProbe() {
  const data = window.__fireBrowser = {
    renderer: null, adapter: null, frames: [], gpu: [], longTasks: [],
    deviceRequests: 0, pipelineCompiles: [], gpuStages: [], draws: 0, measuring: false, timerAvailable: false, timerFailures: 0,
  };
  let lastGpuFrame=-1;
  setInterval(()=>{
    const sample=window.FireAudit?.telemetry?.();
    if(!sample?.gpu||sample.gpuSampleFrame===undefined)return;
    if(!data.measuring){lastGpuFrame=sample.gpuSampleFrame;return;}
    data.gpuStageSource='completed timestamp readbacks';
    if(sample.gpuSampleFrame===lastGpuFrame||data.gpuStages.length>=256)return;
    lastGpuFrame=sample.gpuSampleFrame;const g=sample.gpu;
    data.gpuStages.push([g.simulation+g.lighting+g.render,g.source,g.velocity,g.pressure,g.transport,g.auxiliary,g.lighting,g.render,sample.time]);
  },25);
  addEventListener('DOMContentLoaded',()=>{
    let previous='';
    new MutationObserver(()=>{
      if(!data.measuring||data.gpuStages.length>=256||data.gpuStageSource==='completed timestamp readbacks')return;
      const text=document.querySelector('#metrics')?.textContent||'';
      if(text===previous)return;previous=text;
      const m=text.match(/GPU ([\d.]+) ms.*source ([\d.]+) \/ flow ([\d.]+).*pressure ([\d.]+).*chemistry ([\d.]+).*auxiliary ([\d.]+).*lighting ([\d.]+).*render ([\d.]+) ms .*([\d.]+) s/);
      if(m)data.gpuStages.push(m.slice(1).map(Number));
    }).observe(document.body,{childList:true,characterData:true,subtree:true});
  });
  let last = null;
  function observe(now) {
    if (data.measuring) {
      if (last !== null && data.frames.length < 20000) data.frames.push(now-last);
      last = now;
    } else last = null;
    requestAnimationFrame(observe);
  }
  requestAnimationFrame(observe);
  try { new PerformanceObserver(list => {
    if (data.measuring) for(const entry of list.getEntries()) {
      if(data.longTasks.length < 1000) data.longTasks.push(entry.duration);
    }
  }).observe({entryTypes:['longtask']}); } catch {}
  if (navigator.gpu) {
    const request = navigator.gpu.requestAdapter.bind(navigator.gpu);
    navigator.gpu.requestAdapter = async options => {
      const adapter = await request(options);
      data.adapter = adapter ? {
        vendor: adapter.info?.vendor, device: adapter.info?.device,
        description: adapter.info?.description, fallback: adapter.isFallbackAdapter ?? null,
      } : {unavailable:true};
      if(adapter){
        const requestDevice=adapter.requestDevice.bind(adapter);
        adapter.requestDevice=async descriptor=>{
          data.deviceRequests++;
          const device=await requestDevice(descriptor);
          const compile=device.createComputePipelineAsync.bind(device);
          device.createComputePipelineAsync=async descriptor=>{
            const start=performance.now();
            try{return await compile(descriptor);}finally{
              if(data.pipelineCompiles.length<160)data.pipelineCompiles.push({label:descriptor.label||'',ms:performance.now()-start});
            }
          };
          return device;
        };
      }
      return adapter;
    };
  }
  const original = HTMLCanvasElement.prototype.getContext;
  const seen = new WeakSet();
  HTMLCanvasElement.prototype.getContext = function(type, ...args) {
    const gl = original.call(this,type,...args);
    if(type!=='webgl2'||!gl||seen.has(gl)) return gl;
    seen.add(gl);
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    data.renderer = gl.getParameter(debug ? debug.UNMASKED_RENDERER_WEBGL : gl.RENDERER);
    const ext = gl.getExtension('EXT_disjoint_timer_query_webgl2');
    data.timerAvailable=!!ext;
    let query=null, submissions=0;
    const pending=[];
    for(const method of ['drawArrays','drawElements']) {
      const draw=gl[method].bind(gl);
      gl[method]=function(...parameters) {
        if(data.measuring) {
          data.draws++;
          // Sample one complete Original submission every 30 submissions.
          // Never nest timers with an application's own active timer query.
          if(ext&&!query&&submissions%30===0&&pending.length<4&&
             !gl.getQuery(ext.TIME_ELAPSED_EXT,gl.CURRENT_QUERY)) {
            query=gl.createQuery();gl.beginQuery(ext.TIME_ELAPSED_EXT,query);
          }
        }
        return draw(...parameters);
      };
    }
    const flush=gl.flush.bind(gl);
    gl.flush=function(...parameters) {
      if(query){gl.endQuery(ext.TIME_ELAPSED_EXT);pending.push(query);query=null;}
      if(data.measuring)submissions++;
      return flush(...parameters);
    };
    setInterval(()=>{
      if(gl.isContextLost()){pending.length=0;query=null;return;}
      while(pending.length&&gl.getQueryParameter(pending[0],gl.QUERY_RESULT_AVAILABLE)) {
        const completed=pending.shift();
        if(gl.getParameter(ext.GPU_DISJOINT_EXT))data.timerFailures++;
        else if(data.gpu.length<1000)data.gpu.push(gl.getQueryParameter(completed,gl.QUERY_RESULT)/1e6);
        gl.deleteQuery(completed);
      }
    },100);
    return gl;
  };
}
