from PIL import Image, ImageDraw, ImageFont
import os
RP='/home/vscode/.config/REAPER'
B=[('fyah_play','PLAY','▶',1007,'#2e7d32'),('fyah_stop','STOP','■',1016,'#455a64'),('fyah_rec','REC','●',1013,'#c62828'),
('fyah_loop','LOOP','⟲',1068,'#6a1b9a'),('fyah_undo','UNDO','↶',40029,'#37474f'),('fyah_redo','REDO','↷',40030,'#37474f'),
('fyah_split','SPLIT','✂',40012,'#ef6c00'),('fyah_del','DEL','✖',40697,'#8e2424'),('fyah_zinh','ZOOM','↔+',1012,'#1565c0'),
('fyah_zouth','ZOOM','↔−',1011,'#1565c0'),('fyah_zinv','ZOOM','↕+',40111,'#00838f'),('fyah_zoutv','ZOOM','↕−',40112,'#00838f'),
('fyah_fit','FIT','⤢',40295,'#1565c0'),('fyah_trk','+TRACK','≡',40001,'#4e342e'),('fyah_arm','ARM','◉',9,'#b71c1c'),
('fyah_click','CLICK','♩',40364,'#5d4037'),('fyah_mix','MIXER','▥',40078,'#283593'),('fyah_midi','MIDI','♪',40153,'#00695c')]
F='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def mk(path,s,label,glyph,col):
    im=Image.new('RGBA',(s*3,s),(0,0,0,0))
    for i,f in enumerate([1.0,1.25,0.7]):
        c=tuple(min(255,int(int(col[j:j+2],16)*f)) for j in (1,3,5))
        d=ImageDraw.Draw(im); o=i*s; m=max(2,s//32)
        d.rounded_rectangle([o+m,m,o+s-m-1,s-m-1],radius=s//8,fill=c+(255,),outline=(255,255,255,90),width=max(1,s//60))
        g=ImageFont.truetype(F,int(s*0.42)); t=ImageFont.truetype(F,int(s*0.19) if len(label)<6 else int(s*0.15))
        d.text((o+s/2,s*0.40),glyph,font=g,fill='white',anchor='mm'); d.text((o+s/2,s*0.80),label,font=t,fill='white',anchor='mm')
    im.save(path)
for sub,s in [('',62),('150',93),('200',124)]:
    dd=os.path.join(RP,'Data/toolbar_icons',sub)
    for n,l,g,c,col in B: mk(os.path.join(dd,n+'.png'),s,l,g,col)
lines=['[Main toolbar]']
for i,(n,l,g,c,col) in enumerate(B): lines+=[f'item_{i}={c} {l} {g}',f'icon_{i}={n}.png']
lines+=['title=Fyah Touch','','[Floating toolbar 1]']
for i,(n,l,g,c,col) in enumerate(B): lines+=[f'item_{i}={c} {l} {g}',f'icon_{i}={n}.png']
lines+=['title=Fyah Touch']
open(os.path.join(RP,'reaper-menu.ini'),'w').write('\n'.join(lines)+'\n'); print('menu ok',len(B))
