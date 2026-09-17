from PIL import Image,ImageDraw
import gesture_motion as old
import font_motion as new
im=Image.new('RGB',(1500,720),'#111111');d=ImageDraw.Draw(im)
for row,mod,label in [(0,old,'Previous path'),(1,new,'New connected italic script — nozzle centerline')]:
    d.text((40,row*350+15),label,fill='white')
    pts=[(750+x*135,row*350+295-z*78) for x,z in mod.p]
    d.line(pts,fill='#f7ad59',width=3)
im.save('work/font-path-review.jpg',quality=94)
print({'duration':new.WRITE,'length':new.distance[-1],'speedRange':[float(new.speed.min()),float(new.speed.max())]})
