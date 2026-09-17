const {chromium}=require('C:/Users/alexf/AppData/Local/npm-cache/_npx/31e32ef8478fbf80/node_modules/playwright');
const fs=require('fs');const path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Users/alexf/AppData/Local/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-win64/chrome-headless-shell.exe'});
 const page=await browser.newPage({viewport:{width:1280,height:960}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8767/elements/motion/subelements/dynamics/?material=lightning&v=quality');await page.waitForFunction(()=>window.STUDIES?.ready);
 const before=await page.evaluate(()=>({selected:STUDIES.selected,players:STUDIES.videos.length,video:STUDIES.studies.find(s=>s.id==='lightning').video,duration:STUDIES.videos[0].duration,width:STUDIES.videos[0].videoWidth,height:STUDIES.videos[0].videoHeight}));
 if(before.selected.join()!=='lightning'||before.players!==1||before.width!==1920||before.height!==1080)throw Error('Wrong material or dimensions');
 await page.getByRole('button',{name:'Play selection',exact:true}).click();await page.waitForFunction(()=>STUDIES.videos[0].currentTime>.6);const playback=await page.evaluate(()=>({time:STUDIES.videos[0].currentTime,paused:STUDIES.videos[0].paused}));
 await page.evaluate(async()=>{STUDIES.pause();await STUDIES.seek(1.93)});await page.screenshot({path:path.join(__dirname,'gallery-lightning.jpg'),type:'jpeg',quality:85});
 await page.getByRole('button',{name:'Previous material',exact:true}).click();await page.getByRole('button',{name:'Show rebuilt material',exact:true}).waitFor();await page.getByRole('button',{name:'Show rebuilt material',exact:true}).click();await page.getByRole('button',{name:'Previous material',exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow||errors.length)throw Error(JSON.stringify({overflow,errors}));
 fs.writeFileSync(path.join(__dirname,'gallery-verification.json'),JSON.stringify({before,playback,previousToggle:true,mobileOverflow:overflow,errors},null,2));console.log(JSON.stringify({solo:true,playing:!playback.paused,previousToggle:true,dimensions:[before.width,before.height],errors}));await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
