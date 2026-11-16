"""Original geometric Cyrillic shop alphabet: cut enamel / metal letters, Neptune 1994.

Glyphs are vector strokes, not a bitmap font or a licensed system font. The OBJ
has positive X reading direction and solid paint; lettering does not use UV text.
"""
from math import cos, sin, pi, hypot
from pathlib import Path

def arc(cx,cy,rx,ry,a,b,n=8):
    return [(cx+rx*cos((a+(b-a)*i/n)*pi/180),cy+ry*sin((a+(b-a)*i/n)*pi/180)) for i in range(n+1)]

def paths(ch):
    # Coordinates are normalized to a 0.66 x 1 em condensed sign cell.
    g={
      'А': [[(0,0),(.33,1),(.66,0)],[(.14,.40),(.52,.40)]],
      'Б': [[(.64,1),(0,1),(0,0),(.34,0)]+arc(.34,.25,.31,.25,-90,90)+[(0,.5)]],
      'В': [[(0,0),(0,1),(.33,1)]+arc(.33,.75,.30,.25,90,-90)+[(0,.5)],[(0,.5),(.34,.5)]+arc(.34,.25,.32,.25,90,-90)+[(0,0)]],
      'Г': [[(0,0),(0,1),(.66,1)]],
      'Д': [[(0,0),(.08,.13),(.20,1),(.55,1),(.61,.13),(.66,0)],[(0,.13),(.66,.13)],[(0,.13),(0,-.12)],[(.66,.13),(.66,-.12)]],
      'Е': [[(.66,1),(0,1),(0,0),(.66,0)],[(0,.51),(.53,.51)]],
      'Ж': [[(0,1),(.66,0)],[(.66,1),(0,0)],[(.33,0),(.33,1)]],
      'З': [arc(.25,.76,.35,.24,150,-90)+arc(.27,.25,.37,.25,90,-150)],
      'И': [[(0,1),(0,0),(.66,1),(.66,0)]],
      'К': [[(0,0),(0,1)],[(.66,1),(0,.49),(.66,0)]],
      'Л': [[(0,0),(.10,.04),(.23,1),(.66,1),(.66,0)]],
      'М': [[(0,0),(0,1),(.33,.40),(.66,1),(.66,0)]],
      'Н': [[(0,0),(0,1)],[(.66,0),(.66,1)],[(0,.5),(.66,.5)]],
      'О': [arc(.33,.5,.33,.5,90,450,16)],
      'П': [[(0,0),(0,1),(.66,1),(.66,0)]],
      'Р': [[(0,0),(0,1),(.34,1)]+arc(.34,.75,.31,.25,90,-90)+[(0,.5)]],
      'С': [arc(.37,.5,.37,.5,50,310,13)],
      'Т': [[(0,1),(.66,1)],[(.33,1),(.33,0)]],
      'У': [[(0,1),(.32,.43)],[(.66,1),(.21,.08),(.06,0)]],
      'Ф': [[(.33,-.05),(.33,1.05)],arc(.33,.5,.33,.35,90,450,14)],
      'Х': [[(0,0),(.66,1)],[(0,1),(.66,0)]],
      'Ц': [[(0,1),(0,0),(.61,0),(.61,1)],[(.61,0),(.69,0),(.69,-.12)]],
      'Ч': [[(0,1),(0,.55),(.66,.55)],[(.66,1),(.66,0)]],
      'Ш': [[(0,1),(0,0),(.66,0),(.66,1)],[(.33,1),(.33,0)]],
      'Щ': [[(0,1),(0,0),(.61,0),(.61,1)],[(.31,1),(.31,0)],[(.61,0),(.70,0),(.70,-.12)]],
      'Ь': [[(0,1),(0,0),(.34,0)]+arc(.34,.25,.31,.25,-90,90)+[(0,.5)]],
      'Ы': [[(0,1),(0,0),(.23,0)]+arc(.23,.25,.23,.25,-90,90)+[(0,.5)],[(.66,0),(.66,1)]],
      'Ъ': [[(0,1),(.20,1),(.20,0),(.40,0)]+arc(.40,.25,.26,.25,-90,90)+[(.20,.5)]],
      'Э': [arc(.28,.5,.38,.5,130,-130,13),[(.26,.5),(.66,.5)]],
      'Ю': [[(0,0),(0,1)],[(0,.5),(.23,.5)],arc(.45,.5,.23,.5,90,450,14)],
      'Я': [[(.66,0),(.66,1),(.31,1)]+arc(.31,.75,.31,.25,90,270)+[(.66,.5)],[(.37,.5),(0,0)]],
      '1': [[(.10,.78),(.33,1),(.33,0)],[(.10,0),(.56,0)]],
      '2': [arc(.32,.77,.32,.23,180,-10)+[(.01,0),(.66,0)]],
      '3': [arc(.26,.76,.35,.24,150,-90)+arc(.27,.25,.37,.25,90,-150)],
      '4': [[(.48,0),(.48,1),(0,.32),(.66,.32)]],
      '5': [[(.64,1),(0,1),(0,.52),(.34,.52)]+arc(.34,.26,.31,.26,90,-140)],
      '6': [arc(.34,.5,.32,.5,55,260,11)+arc(.32,.27,.31,.27,260,620,12)],
      '7': [[(0,1),(.66,1),(.12,0)]],
      '8': [arc(.33,.76,.28,.24,90,450,12),arc(.33,.25,.33,.25,90,450,12)],
      '9': [arc(.33,.74,.31,.26,90,450,12),[(.64,.74),(.51,.12),(.24,0)]],
      '/': [[(0,0),(.66,1)]], '-': [[(.10,.5),(.56,.5)]],
      '•': [[(.29,.5),(.37,.5)]], '«': [[(.28,.76),(0,.5),(.28,.24)],[(.62,.76),(.34,.5),(.62,.24)]],
      '»': [[(.04,.76),(.32,.5),(.04,.24)],[(.38,.76),(.66,.5),(.38,.24)]],
    }
    if ch=='Ё': return g['Е']+[[(.15,1.17),(.18,1.17)],[(.48,1.17),(.51,1.17)]]
    if ch=='Й': return g['И']+[[(.14,1.13),(.33,1.05),(.52,1.13)]]
    if ch=='0': return g['О']
    if ch=='.': return [[(.29,.04),(.37,.04)]]
    if ch==' ':return []
    if ch not in g: raise ValueError('Unsupported sign glyph: '+ch)
    return g[ch]

def write_obj(path, text, height_cm, maximum_width=None):
    """Create closed bevel-ended stroke prisms. No negative scale or UV lettering."""
    advances=[.44 if c==' ' else .84 for c in text]
    width=sum(advances)-.18
    size=min(height_cm,maximum_width/width if maximum_width else height_cm)
    verts,faces=[],[]
    cursor=-width*size/2
    for ch,advance in zip(text,advances):
        for stroke in paths(ch):
            for a,b in zip(stroke,stroke[1:]):
                dx,dz=b[0]-a[0],b[1]-a[1]
                length=hypot(dx,dz)
                if length<.0001:continue
                ux,uz=dx/length,dz/length
                # Eight-point chamfered outline: softer than bitmap/pixel lettering.
                r=.047
                points=[(-r*.45,-r),(length+r*.45,-r),(length+r,-r*.45),(length+r,r*.45),
                        (length+r*.45,r),(-r*.45,r),(-r,r*.45),(-r,-r*.45)]
                start=len(verts)
                for y in (-.45,.45):
                    for along,across in points:
                        x=a[0]+along*ux-across*uz
                        z=a[1]+along*uz+across*ux
                        verts.append((cursor+x*size,y,(z-.5)*size))
                faces.extend([tuple(start+i+1 for i in range(8)),tuple(start+16-i for i in range(8))])
                for i in range(8):
                    j=(i+1)%8
                    faces.append((start+i+1,start+j+1,start+j+9,start+i+9))
        cursor+=advance*size
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    lines=['# Original Neptune-94 vector sign alphabet; centimeters; +X reading baseline.','o '+path.stem,'usemtl EnamelLetters','vt 0.5 0.5']
    lines.extend('v %.6f %.6f %.6f'%v for v in verts)
    lines.extend('f '+' '.join(str(i)+'/1' for i in face) for face in faces)
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')
    return dict(text=text,width_cm=width*size,height_cm=size,vertices=len(verts),triangles=sum(len(f)-2 for f in faces))
