import { createServer } from 'node:http';

import { readFile, stat, mkdir, writeFile } from 'node:fs/promises';

import { writeFileSync } from 'node:fs';

import path from 'node:path';

import { fileURLToPath } from 'node:url';

import { installProbe } from './probe.js';

import { performanceSummary, resolveAsset, simulationAdvanced } from './helpers.mjs';



const here=path.dirname(fileURLToPath(import.meta.url));

const args=new Map(process.argv.slice(2).map(arg=>{const [key,...value]=arg.replace(/^--/,'').split('=');return [key,value.join('=')||true];}));

if(args.has('help')){

  console.log('node run.mjs [--simulation=original|volume|sparse] [--preset=hearth] [--seconds=15] [--matrix] [--channel=chrome|msedge] [--headless] [--url=http://...] [--cdp=http://127.0.0.1:9222] [--out=PATH]');process.exit(0);

}

const seconds=Number(args.get('seconds')||15);

if(!Number.isFinite(seconds)||seconds<2||seconds>120)throw Error('seconds must be between 2 and 120');

const output=path.resolve(args.get('out')||path.join(here,'../../output/playwright/fire-browser',new Date().toISOString().replace(/[:.]/g,'-')));

await mkdir(output,{recursive:true});

const report={startedAt:new Date().toISOString(),headless:args.has('headless'),tests:[],status:'starting',

  note:'A headed Chrome session is the default. Headless results must not be treated as device/demo performance.'};

let browser,server,context,page;

const deadline=setTimeout(()=>{

  report.status='timeout';report.error='Runner deadline reached; no successful benchmark is claimed.';

  writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));

  console.error('Timed out. Report: '+path.join(output,'report.json'));

  // Disconnecting the pipe also terminates the runner-owned Chrome session.

  process.exit(2);

},(args.has('matrix')?360:Math.max(150,String(args.get('presets')||args.get('preset')||'hearth').split(',').length*String(args.get('solvers')||args.get('simulation')||'original').split(',').length*(seconds+90)))*1000);

const bounded=(promise,label,ms=15000)=>{

  let timer;return Promise.race([promise,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error(label+' timed out')),ms))]).finally(()=>clearTimeout(timer));

};

try {

  const {chromium}=await import('playwright-core');

  let base=args.get('url');

  if(!base){

    const root=path.resolve(here,'../../outputs/cybrdelic-type');

    const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.bin':'application/octet-stream'};

    server=createServer(async(req,res)=>{

      try{

        if(req.method!=='GET'&&req.method!=='HEAD'){res.writeHead(405).end();return;}

        let file=resolveAsset(root,new URL(req.url,'http://localhost').pathname);

        if((await stat(file)).isDirectory())file=path.join(file,'index.html');

        if(args.has('overlay')){
          const fireRoot=path.join(root,'elements/motion/bending/sigils/02/fire-live');
          const relative=path.relative(fireRoot,file);
          if(!relative.startsWith('..')&&!path.isAbsolute(relative)){
            const overlayFile=path.resolve(String(args.get('overlay')),relative);
            if(await stat(overlayFile).then(s=>s.isFile()).catch(()=>false))file=overlayFile;
          }
        }
        const bytes=await readFile(file);
        res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});

        res.end(req.method==='HEAD'?undefined:bytes);

      }catch{res.writeHead(404).end('Not found');}

    });

    await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});

    base=`http://127.0.0.1:${server.address().port}/elements/motion/bending/sigils/02/fire-live/`;

  }

  if(!['http:','https:'].includes(new URL(base).protocol))throw Error('Only HTTP and HTTPS pages are supported');

  const contextOptions={viewport:{width:1280,height:720},...(args.has('video')?{recordVideo:{dir:path.join(output,'raw-video'),size:{width:1280,height:720}}}:{})};

  if(args.has('cdp')){

    browser=await chromium.connectOverCDP(String(args.get('cdp')),{timeout:15000});

    context=browser.contexts()[0];if(!context)throw Error('Connected browser has no context');

    report.browser='Connected browser; only runner-created pages are closed';

  }else{

    const gpuArgs=args.has('high-performance-gpu')?['--force-high-performance-gpu','--force_high_performance_gpu','--use-webgpu-power-preference=force-high-performance']:[];
    report.launchGpuArgs=gpuArgs;
    browser=await chromium.launch({channel:String(args.get('channel')||'chrome'),headless:args.has('headless'),args:gpuArgs,timeout:30000});

    context=await browser.newContext(contextOptions);

    report.browser=await browser.version();

  }

  const scenarios=args.has('matrix')?

    [['original','hearth'],['original','torch'],['volume','bonfire'],['sparse','bonfire']]:

    String(args.get('solvers')||args.get('simulation')||'original').split(',').flatMap(simulation=>

      String(args.get('presets')||args.get('preset')||'hearth').split(',').map(preset=>[simulation,preset]));

  for(const [caseIndex,[simulation,preset]] of scenarios.entries()){

    if(caseIndex>0&&!args.has('cdp')){await context.close();context=await browser.newContext(contextOptions);}

    const result={simulation,preset,status:'starting',errors:[],console:[],failedRequests:[],httpErrors:[]};

    report.tests.push(result);

    const slug=simulation+'-'+preset.replace(/[^a-z0-9-]/gi,'_');

    const pageCreatedAt=Date.now();page=await context.newPage();const video=page.video();await page.addInitScript(installProbe);

    page.on('pageerror',error=>{if(result.errors.length<100)result.errors.push(error.message);});

    page.on('console',message=>{if(['error','warning'].includes(message.type())&&result.console.length<100)result.console.push({type:message.type(),text:message.text().slice(0,2000)});});

    page.on('requestfailed',request=>{if(result.failedRequests.length<100)result.failedRequests.push({url:request.url(),error:request.failure()?.errorText});});

    page.on('response',response=>{if(response.status()>=400&&result.httpErrors.length<100)result.httpErrors.push({url:response.url(),status:response.status()});});

    const target=new URL(base);target.searchParams.set('simulation',simulation);target.searchParams.set('preset',preset);target.searchParams.set('firePreset',preset);

    if(args.has('age')){const age=Number(args.get('age'));if(!Number.isFinite(age)||age<=0||age>15)throw Error('age must be in (0,15]');target.searchParams.set('capture',age);target.searchParams.set('stop',age);}

    target.searchParams.set('room','1');target.searchParams.set('lighting','fully-lit');
    target.searchParams.set('audit','1');

    for(const [key,value] of new URLSearchParams(String(args.get('query')||'')))target.searchParams.set(key,value);

    if(args.has('video'))target.searchParams.set('present','1');

    result.url=target.href;const started=Date.now();
      const state=()=>page.evaluate(()=>({visibility:document.visibilityState,documentHidden:document.hidden,fuel:document.querySelector('#fuel')?.value,color:document.querySelector('#flame-color')?.value,title:document.querySelector('#view-state-title')?.textContent,

        metrics:document.querySelector('#metrics')?.textContent,simulationTime:document.querySelector('#metrics')?.dataset.simTime===undefined?null:Number(document.querySelector('#metrics').dataset.simTime),occupancyReduction:document.querySelector('#metrics')?.dataset.occupancyReduction,maxSpeed:Number(document.querySelector('#metrics')?.dataset.maxSpeed),substeps:Number(document.querySelector('#metrics')?.dataset.substeps),flowRefinement:document.querySelector('#metrics')?.dataset.refinedTiles,flowMode:document.querySelector('#metrics')?.dataset.flowMode,gpuStatus:document.querySelector('#gpu-status')?.textContent,

        message:document.querySelector('#message')?.textContent,pauseDisabled:document.querySelector('#pause')?.disabled,

        errorDescription:document.querySelector('#view-state-description')?.textContent,

        sessionState:document.querySelector('#session-status')?.dataset.state,

        deviceRequests:window.__fireBrowser?.deviceRequests,pipelineCompiles:window.__fireBrowser?.pipelineCompiles,renderer:window.__fireBrowser?.renderer,adapter:window.__fireBrowser?.adapter}));



    try{

      await page.bringToFront();

      await page.goto(target.href,{waitUntil:'domcontentloaded',timeout:20000});

      await page.waitForFunction(()=>{

        const title=document.querySelector('#view-state-title')?.textContent||'';

        return /unavailable|another tab/i.test(title)||document.querySelector('#session-status')?.dataset.state==='ready';

      },null,{timeout:60000});

      result.startupMs=Date.now()-started;

      result.startup=await bounded(state(),'Startup state');

      if(result.startup.sessionState!=='ready')throw Error(result.startup.errorDescription||result.startup.gpuStatus||'Simulation did not start');

      const selected=await page.locator('#preset').inputValue();
      if(selected!==preset.replace(/^legacy:/,''))throw Error('Requested source '+preset+' loaded '+selected+' instead');

      if(preset==='free')await page.locator('#fire').click({position:{x:448,y:330}});

      if(args.has('age')){await page.waitForFunction(()=>document.querySelector('#pause')?.textContent==='Resume',null,{timeout:120000});result.comparisonAge=Number(args.get('age'));result.comparisonState=await state();await bounded(page.locator('#fire').screenshot({path:path.join(output,slug+'-age.png')}),'Same-age scene screenshot');if(!args.has('sim-window'))await page.locator('#pause').click();}
      await bounded(page.screenshot({path:path.join(output,slug+'-start.png')}),'Startup screenshot');

      await page.waitForTimeout(3000);

      if(args.has('switches')){

        if(await page.locator('#demo-mode').textContent()==='Exit presentation')await page.locator('#demo-mode').click();

        await page.locator('button[data-panel=scene]').click();

        result.switches=[];

        for(const next of String(args.get('switches')).split(',')){

          const before=Date.now();
          if(!await page.locator('#preset option').evaluateAll((options,id)=>options.some(o=>o.value===id),next))await page.locator('#show-experiments').check();
          await page.locator('#preset').selectOption(next);

          await page.waitForFunction(id=>{

            const select=document.querySelector('#preset'),selected=select?.selectedOptions[0];

            return select?.value===id&&document.querySelector('#session-status')?.dataset.state==='ready'&&

              document.querySelector('#message')?.textContent.includes(selected.textContent.replace(/ · blockout$/, ''));

          },next,{timeout:60000});

          const readyMs=Date.now()-before;

          await page.waitForTimeout(3000);const switched=await state();

          if(switched.sessionState!=='ready')throw Error('Preset switch failed: '+next+' · '+switched.errorDescription);

          result.switches.push({preset:next,readyMs,startupMs:Date.now()-before,state:switched});

        }

      }

      if(args.has('switches')&&args.has('video'))await page.locator('#demo-mode').click();

      result.measurementStart=await bounded(state(),'Warmup state');

      await page.evaluate(()=>{window.__fireBrowser.measuring=true;});

      // The app benchmark resets the solver. Request it explicitly; a live

      // measurement must preserve the scene age and normal frame scheduling.

      if(args.has('benchmark')){

        await page.locator('#diagnostics').evaluate(el=>{el.open=true;});

        await page.locator('#benchmark').click({timeout:5000});

      }

      const sampleStart=Date.now();
      if(args.has('sim-window')){
        const span=Number(args.get('sim-window'));
        if(!args.has('age')||!Number.isFinite(span)||span<=0||span>10||!Number.isFinite(result.measurementStart.simulationTime))throw Error('sim-window requires a measurable paused age and a span in (0,10]');
        result.simulationWindow={start:result.measurementStart.simulationTime,target:result.measurementStart.simulationTime+span};
        await page.locator('#pause').click();
      }
      if(video)result.recording={startSeconds:(sampleStart-pageCreatedAt)/1000,durationSeconds:seconds};

      if(args.has('from-ignition')){

        if(args.has('age'))throw Error('from-ignition and age are separate capture modes');

        result.recordingOrigin='ignition';await page.locator('#restart').click();

      }

      if(args.has('exercise-controls')){
        if(args.has('video')||args.has('sim-window')||seconds<4)throw Error('exercise-controls needs a normal UI capture of at least four seconds');
        result.controls={before:await state()};
        await page.waitForTimeout(1000);
        const box=await page.locator('#fire').boundingBox();
        await page.mouse.move(box.x+box.width*.5,box.y+box.height*.72);await page.mouse.down();
        for(let i=0;i<8;i++){
          await page.mouse.move(box.x+box.width*(.5+.12*(i+1)/8),box.y+box.height*.72);
          await page.waitForTimeout(80);
        }
        await page.mouse.up();await page.waitForTimeout(750);
        result.controls.dragged=await state();
        await bounded(page.locator('#fire').screenshot({path:path.join(output,slug+'-dragged.png')}),'Dragged scene');
        await page.locator('#extinguish').click();
        result.controls.stopped=await state();
        if(!/stopped/i.test(result.controls.stopped.message))throw Error('Stop source control did not acknowledge the action');
      }

      if(preset==='free'&&args.has('video')){

        const box=await page.locator('#fire').boundingBox();

        await page.mouse.move(box.x+box.width*.5,box.y+box.height*.66);await page.mouse.down();

        for(let i=0;i<64;i++){

          const t=i/63;await page.mouse.move(box.x+box.width*(.5+.17*Math.sin(t*Math.PI*2)),box.y+box.height*(.66-.08*Math.sin(t*Math.PI)));

          await page.waitForTimeout(65);

        }

        await page.mouse.up();

      }

      if(args.has('sim-window'))await page.waitForFunction(target=>Number(document.querySelector('#metrics')?.dataset.simTime)>=target, result.simulationWindow.target,{timeout:120000});
      else await page.waitForTimeout(Math.max(0,seconds*1000-(Date.now()-sampleStart)));
      const data=await bounded(page.evaluate(()=>{window.__fireBrowser.measuring=false;return window.__fireBrowser;}),'Read measurements');

      result.performance=performanceSummary(data,(Date.now()-sampleStart)/1000);
      result.measurementWallSeconds=(Date.now()-sampleStart)/1000;
      result.end=await bounded(state(),'Final state');
      if(result.simulationWindow){
        result.simulationWindow.end=result.end.simulationTime;
        result.simulationWindow.toWallRatio=(result.end.simulationTime-result.simulationWindow.start)/result.measurementWallSeconds;
      }

      result.appBenchmark=result.end.gpuStatus;

      result.simulationProgressed=simulationAdvanced(result.measurementStart,result.end);

      result.status=result.errors.length||result.end.sessionState!=='ready'||!result.simulationProgressed||!data.frames.length||result.performance.softwareRenderer?'failed':'completed';

      await bounded(page.screenshot({path:path.join(output,slug+'-end.png')}),'Final screenshot');

      await bounded(page.locator('#fire').screenshot({path:path.join(output,slug+'-scene.png')}),'Scene screenshot');

    }catch(error){result.status='failed';result.error=error.message;
      try{result.failureState=await bounded(state(),'Failure state',5000);}catch(diagnosticError){result.failureStateError=diagnosticError.message;}

      try{await bounded(page.screenshot({path:path.join(output,slug+'-failure.png')}),'Failure screenshot',5000);}catch{}

    }finally{

      await bounded(page.close(),'Page close',5000).catch(()=>{});page=null;

      if(video){result.video=path.join(output,slug+'.webm');await bounded(video.saveAs(result.video),'Save recording',20000).catch(error=>{result.videoError=error.message;result.status='failed';});}

      await writeFile(path.join(output,slug+'.json'),JSON.stringify(result,null,2));

      console.log(`${slug}: ${result.status}${result.error?' â€” '+result.error:''}`);

    }

  }

  report.status=report.tests.every(t=>t.status==='completed')?'completed':'failed';

}catch(error){report.status='failed';report.error=error.message;}

finally{

  clearTimeout(deadline);

  await writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));

  if(browser&&!args.has('cdp'))await bounded(browser.close(),'Browser close',5000).catch(()=>{});

  if(server)await new Promise(resolve=>server.close(resolve));

  console.log('Report: '+path.join(output,'report.json'));

  process.exitCode=report.status==='completed'?0:1;

}

