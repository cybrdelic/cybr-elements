const fs=require('fs');
(async()=>{
 const tabs=await(await fetch('http://127.0.0.1:9337/json')).json();const t=tabs.find(x=>x.type==='page'&&x.url.includes('/typefaces/'));
 const ws=new WebSocket(t.webSocketDebuggerUrl);await new Promise(r=>ws.addEventListener('open',r,{once:true}));let id=0;const pending=new Map();
 ws.addEventListener('message',e=>{const p=JSON.parse(e.data);if(p.id&&pending.has(p.id)){const[r,j]=pending.get(p.id);pending.delete(p.id);p.error?j(p.error):r(p.result)}});
 const call=(method,params={})=>new Promise((r,j)=>{const n=++id;pending.set(n,[r,j]);ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async(expression)=>(await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.value;
 await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1400,height:1000,deviceScaleFactor:1,mobile:false});
 const report=await evaluate(`(async()=>{const result=[];for(const name of ['Cybrdelic Sigil','Cybrdelic Cut']){const loaded=await document.fonts.load('100px "'+name+'"');const s=document.createElement('span');s.style.cssText='position:absolute;white-space:nowrap;font-size:100px;font-family:"'+name+'";';document.body.append(s);s.textContent='cybrdelic';s.style.fontFeatureSettings='"dlig" 0';const normal=s.getBoundingClientRect().width;s.style.fontFeatureSettings='"dlig" 1';const ligature=s.getBoundingClientRect().width;s.textContent='\\uE000';const glyph=s.getBoundingClientRect().width;s.remove();result.push({name,loaded:loaded.length>0,normal,ligature,glyph,substitution:Math.abs(ligature-glyph)<.1&&Math.abs(normal-ligature)>1})}return {fonts:result,desktopOverflow:document.documentElement.scrollWidth>innerWidth}})()`);
 if(!report.fonts.every(x=>x.loaded&&x.substitution)||report.desktopOverflow)throw Error(JSON.stringify(report));
 const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('work/brand-font/typefaces-browser.png',Buffer.from(shot.data,'base64'));
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});report.mobileOverflow=await evaluate('document.documentElement.scrollWidth>innerWidth+1');if(report.mobileOverflow)throw Error('mobile overflow');
 report.controls=await evaluate(`(()=>{document.querySelector('#text').value='lily minimum';document.querySelector('#text').dispatchEvent(new Event('input'));return document.querySelector('#sigil').textContent==='lily minimum'&&document.querySelector('#cut').textContent==='lily minimum'})()`);if(!report.controls)throw Error('preview controls');
 fs.writeFileSync('outputs/cybrdelic-fonts/browser-validation.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await call('Browser.close');
})().catch(e=>{console.error(String(e));process.exit(1)});
