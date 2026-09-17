const {chromium}=require('C:/Users/alexf/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright');
const fs=require('fs');
const path=require('path');
const base='http://127.0.0.1:8767/elements/sigils/';
const preview=process.argv.includes('--preview');
(async()=>{
 const b=await chromium.launch({headless:true,executablePath:'C:/Users/alexf/AppData/Local/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-win64/chrome-headless-shell.exe'});
 const page=await b.newPage({viewport:{width:1440,height:1100}}),errors=[];
 let expectedCount=52;
 if(preview){
  const materials=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../../outputs/cybrdelic-type/elements/motion/subelements/dynamics/studies.json'),'utf8'));
  const available=materials.flatMap(m=>['01','02'].filter(v=>fs.existsSync(__dirname+'/media/'+m.id+'-'+v+'.json')).map(v=>({id:m.id+'-'+v,material:m.id,variant:v,title:m.title,group:m.group,video:m.id+'-'+v+'.mp4',poster:m.id+'-'+v+'.jpg'})));
  expectedCount=available.length;
  await page.route(base+'**',route=>{
   const tail=new URL(route.request().url()).pathname.slice('/elements/sigils/'.length);
   if(!tail)return route.fulfill({path:__dirname+'/gallery.html',contentType:'text/html'});
   if(tail==='studies.json')return route.fulfill({json:available});
   const file=__dirname+'/media/'+path.basename(tail);
   if(tail.endsWith('.mp4')){
    const buffer=fs.readFileSync(file),range=route.request().headers().range,headers={'Accept-Ranges':'bytes'};
    if(range){const match=/bytes=(\d+)-(\d*)/.exec(range),start=Number(match[1]),end=match[2]?Math.min(Number(match[2]),buffer.length-1):buffer.length-1;headers['Content-Range']=`bytes ${start}-${end}/${buffer.length}`;return route.fulfill({status:206,headers,contentType:'video/mp4',body:buffer.subarray(start,end+1)})}
    return route.fulfill({headers,contentType:'video/mp4',body:buffer});
   }
   return route.fulfill({path:file,contentType:'image/jpeg'});
  });
 }
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);
 await page.waitForFunction(()=>window.SIGILS?.ready||window.SIGILS_ERROR,{},{timeout:60000});
 if(await page.evaluate(()=>window.SIGILS_ERROR))throw Error(await page.evaluate(()=>SIGILS_ERROR));
 const entries=await page.evaluate(()=>SIGILS.items);
 if(entries.length!==expectedCount||await page.locator('.tile').count()!==expectedCount/2)throw Error('Incomplete library');
 await page.evaluate(()=>SIGILS.seek(8));
 await page.evaluate(()=>SIGILS.play());
 await page.waitForFunction(()=>SIGILS.players[0].currentTime>8.6);
 await page.evaluate(()=>SIGILS.pause());
 const times=await page.evaluate(()=>SIGILS.players.map(v=>v.currentTime));
 if(Math.max(...times)-Math.min(...times)>.1)throw Error('Pair drift');
 await page.locator('video').nth(1).evaluate(v=>v.play());
 await page.waitForFunction(()=>!SIGILS.players[1].paused&&SIGILS.players[1].currentTime>9);
 const solo=await page.evaluate(()=>SIGILS.players.map(v=>({paused:v.paused,time:v.currentTime})));
 if(!solo[0].paused||solo[1].paused)throw Error('Native solo failed');
 await page.evaluate(()=>SIGILS.pause());
 const metadata=[];
 for(const item of entries){
  await page.evaluate(s=>SIGILS.pick(s.material,s.variant),item);
  await page.evaluate(()=>SIGILS.seek(8));
  const m=await page.evaluate(()=>({id:SIGILS.selected[0].id,width:SIGILS.players[0].videoWidth,height:SIGILS.players[0].videoHeight,duration:SIGILS.players[0].duration,time:SIGILS.players[0].currentTime,error:SIGILS.players[0].error?.message}));
  if(m.width!==1920||m.height!==1080||Math.abs(m.duration-15)>.05||Math.abs(m.time-8)>.04||m.error)throw Error('Invalid film '+JSON.stringify(m));
  metadata.push(m);
 }
 await page.getByRole('button',{name:'Fire',exact:true}).click();
 const fireTiles=await page.locator('.tile').count();
 if(fireTiles!==new Set(entries.filter(s=>s.group==='Fire').map(s=>s.material)).size)throw Error('Fire filter '+fireTiles);
 await page.locator('[data-kind="combustion"][data-variant="02"]').click();
 await page.waitForFunction(()=>SIGILS.ready&&SIGILS.selected[0].id==='combustion-02'&&!SIGILS.players[0].paused&&SIGILS.players[0].currentTime>.2);
 if(await page.locator('.player').count()!==1)throw Error('Solo selection failed');
 await page.evaluate(()=>SIGILS.pause());
 await page.getByRole('button',{name:'All',exact:true}).click();
 const comparison=preview?'blue-fire':'glass';
 await page.locator('[data-kind="'+comparison+'"][data-variant="both"]').click();
 await page.waitForFunction(kind=>SIGILS.ready&&SIGILS.selected.length===2&&SIGILS.selected[0].material===kind&&SIGILS.players[0].currentTime>.2,comparison);
 await page.evaluate(()=>SIGILS.seek(8));
 await page.getByRole('button',{name:'Restart',exact:true}).click();
 await page.waitForFunction(()=>SIGILS.players[0].currentTime>.2&&SIGILS.players[0].currentTime<1);
 await page.evaluate(()=>SIGILS.seek(8));
 await page.evaluate(()=>scrollTo(0,0));
 await page.screenshot({path:__dirname+(preview?'/preview-review.jpg':'/gallery-review.jpg'),type:'jpeg',quality:87});
 const links=await page.locator('header a,footer a,.player h2 a').evaluateAll(a=>a.map(x=>x.href));
 if(!preview)for(const link of links){const response=await page.request.head(link);if(!response.ok())throw Error('Broken link '+link+' '+response.status())}
 await page.setViewportSize({width:390,height:844});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 await page.screenshot({path:__dirname+(preview?'/preview-mobile.jpg':'/gallery-mobile.jpg'),type:'jpeg',quality:85});
 if(overflow||errors.length)throw Error(JSON.stringify({overflow,errors}));
 fs.writeFileSync(__dirname+(preview?'/preview-verification.json':'/gallery-verification.json'),JSON.stringify({count:metadata.length,metadata,times,solo,fireTiles,links,mobileOverflow:overflow,errors},null,2));
 console.log(JSON.stringify({count:metadata.length,times,fireTiles,mobileOverflow:overflow,errors}));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
