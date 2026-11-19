"""Prepare the supplied grocery models, storefront lettering, fonts and footstep sounds."""
from math import cos, pi, sin, tau
from pathlib import Path
from shutil import copy2
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'Saved/BrightonUpgrade/Python'))
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.basePen import BasePen
from shapely.geometry import Polygon
from mapbox_earcut import triangulate_float64
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = ROOT/'Resources/Brighton'
OUT.mkdir(parents=True, exist_ok=True)
FONTS = ROOT/'Content/UI/Dialogue/Fonts'


def fonts():
    source = TTFont(FONTS/'Podkova-Variable.ttf')
    for name, weight in (('Regular', 500), ('Bold', 700)):
        face = instantiateVariableFont(source, {'wght': weight}, inplace=False)
        assert all(ord(char) in face.getBestCmap() for char in 'ВыносливостьЗадачи'), name
        face.save(FONTS/('Podkova-'+name+'.ttf'))


def supplied_models(names=None):
    source = Path.home()/'Desktop/assets'
    if names is None:
        names = (('green_can_obj','can',13.5), ('soda_bottle_obj','bottle',30.0),
                 ('chocolate_bar_obj','bar',14.0), ('cash_register_obj','register',47.0),
                 ('pistol_obj','pistol',20.5))
    for folder, stem, longest in names:
        original = source/folder
        destination = OUT/('Props' if folder=='pistol_obj' else 'Groceries')/folder
        destination.mkdir(parents=True, exist_ok=True)
        for file in original.iterdir():
            if file.is_file():
                copy2(file, destination/file.name)
        lines = (original/(stem+'.obj')).read_text(encoding='utf-8-sig').splitlines()
        points = [tuple(map(float,line.split()[1:4])) for line in lines if line.startswith('v ')]
        low = [min(p[i] for p in points) for i in range(3)]
        high = [max(p[i] for p in points) for i in range(3)]
        factor = longest/max(high[i]-low[i] for i in range(3))
        center = [(low[i]+high[i])/2 for i in range(2)]
        cooked = ['mtllib '+stem+'.mtl', 'o SM_'+folder]
        has_uv=any(line.startswith('vt ') for line in lines)
        if not has_uv: cooked.append('vt .5 .5')
        for line in lines:
            if line.startswith(('mtllib ', 'o ', 'g ', 's ')):
                continue
            if line.startswith('v '):
                x,y,z = map(float,line.split()[1:4])
                line = 'v %.7f %.7f %.7f'%((x-center[0])*factor,-(y-center[1])*factor,(z-low[2])*factor)
            elif line.startswith('vn '):
                x,y,z = map(float,line.split()[1:4])
                line = 'vn %.7f %.7f %.7f'%(x,-y,z)
            elif line.startswith('f '):
                corners=list(reversed(line.split()[1:]))
                if not has_uv:
                    corners=[face.replace('//','/1/') if '//' in face else face+'/1' for face in corners]
                line = 'f '+' '.join(corners)
            cooked.append(line)
        (destination/('SM_'+folder+'.obj')).write_text('\n'.join(cooked)+'\n',encoding='utf-8')
        print('BRIGHTON_SOURCE',folder,'height_cm',round((high[2]-low[2])*factor,2))


class OutlinePen(BasePen):
    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.rings = []
        self.points = []
    def _moveTo(self, point):
        self.points = [point]
    def _lineTo(self, point):
        self.points.append(point)
    def _curveToOne(self, a, b, c):
        start = self._getCurrentPoint()
        for step in range(1,9):
            t = step/8
            self.points.append(tuple((1-t)**3*start[i]+3*(1-t)**2*t*a[i]+3*(1-t)*t*t*b[i]+t**3*c[i] for i in range(2)))
    def _qCurveToOne(self, a, b):
        start = self._getCurrentPoint()
        for step in range(1,9):
            t=step/8
            self.points.append(tuple((1-t)**2*start[i]+2*(1-t)*t*a[i]+t*t*b[i] for i in range(2)))
    def _closePath(self):
        if len(self.points)>2:
            self.rings.append(self.points)
        self.points=[]
    def _endPath(self):
        self._closePath()


def letter_row(text, face, width, height, z):
    glyphs = face.getGlyphSet()
    cmap = face.getBestCmap()
    rings=[]
    cursor=0
    for char in text:
        glyph = glyphs[cmap[ord(char)]]
        pen=OutlinePen(glyphs)
        glyph.draw(pen)
        rings.extend([[(x+cursor,y) for x,y in ring] for ring in pen.rings])
        cursor+=glyph.width
    left=min(x for ring in rings for x,y in ring)
    right=max(x for ring in rings for x,y in ring)
    bottom=min(y for ring in rings for x,y in ring)
    top=max(y for ring in rings for x,y in ring)
    scale=min(width/(right-left),height/(top-bottom))
    shapes=[Polygon(ring).buffer(0) for ring in rings]
    result=[]
    for i, shape in enumerate(shapes):
        if shape.is_empty:continue
        nesting=sum(other.contains(shape.representative_point()) and other.area>shape.area for other in shapes)
        if nesting%2:continue
        holes=[other for other in shapes if shape.contains(other.representative_point()) and other.area<shape.area and
               sum(parent.contains(other.representative_point()) and parent.area>other.area for parent in shapes)==nesting+1]
        polygon=shape
        for hole in holes:polygon=polygon.difference(hole)
        for part in getattr(polygon,'geoms',(polygon,)):
            # A constrained triangulation keeps counters and accents intact.
            loops=[list(ring.coords)[:-1] for ring in (part.exterior,*part.interiors)]
            vertices=np.asarray([point for loop in loops for point in loop],dtype=np.float64)
            ends=np.cumsum([len(loop) for loop in loops],dtype=np.uint32)
            indices=triangulate_float64(vertices,ends).reshape(-1,3)
            for triangle in indices:
                p,q,r=vertices[triangle]
                winding=(q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
                if abs(winding)<1e-8:continue
                points=(p,q,r) if winding>0 else (p,r,q)
                result.append([((x-(left+right)/2)*scale,0,(y-(bottom+top)/2)*scale+z) for x,y in points])
    return result


def signs(keys=('SM_SignStreet','SM_NeighborhoodPark','SM_NeighborhoodPrecinct')):
    from NeptuneSignFont import SIGNS
    output=ROOT/'Resources/StreetRefinement'
    for key in keys:
        spec=SIGNS[key]
        face=TTFont(output/'SignFonts'/spec.font)
        if spec.russian:
            triangles=letter_row(spec.russian,face,spec.width,.51*spec.height,.24*spec.height)
            triangles+=letter_row(spec.english,face,spec.width,.40*spec.height,-.25*spec.height)
        else:
            triangles=letter_row(spec.english,face,spec.width,.82*spec.height,0)
        name='SM_N94_'+key
        lines=['# '+spec.text,'o '+name,'usemtl EnamelLetters','vn 0 -1 0']
        for triangle in triangles:
            for x,y,z in triangle:
                lines.append('v %.6f %.6f %.6f'%(x,y,z))
                lines.append('vt %.7f %.7f'%(x/spec.width+.5,z/spec.height+.5))
        for index in range(len(triangles)):
            start=index*3+1
            lines.append('f '+' '.join(f'{corner}/{corner}/1' for corner in range(start,start+3)))
        (output/(name+'.obj')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print('BRIGHTON_SIGN',key,len(triangles))


def labels():
    directory=OUT/'Groceries/Labels'
    directory.mkdir(parents=True,exist_ok=True)
    styles=(('Milk','МОЛОКО\nMILK',(.17,.36,.49)),('Cereal','CORN\nFLAKES',(.64,.22,.095)),
            ('Flour','FLOUR\nМУКА',(.55,.37,.17)),('Buckwheat','ГРЕЧКА\nBUCKWHEAT',(.27,.36,.19)),
            ('Rice','RICE\nРИС',(.49,.17,.11)),('Tomatoes','TOMATOES\nТОМАТЫ',(.59,.12,.07)))
    face=ImageFont.truetype(str(FONTS/'Podkova-Bold.ttf'),43)
    small=ImageFont.truetype(str(FONTS/'Podkova-Regular.ttf'),20)
    for name,text,color in styles:
        ink=tuple(round(c*255) for c in color)
        image=Image.new('RGB',(384,512),(224,213,177))
        draw=ImageDraw.Draw(image)
        draw.rectangle((12,12,371,499),outline=ink,width=6)
        draw.rectangle((24,25,359,83),fill=ink)
        draw.text((192,54),'BRIGHTON • 1994',font=small,anchor='mm',fill=(239,226,190))
        draw.multiline_text((192,185),text,font=face,anchor='mm',align='center',fill=ink,spacing=8)
        draw.line((43,276,341,276),fill=ink,width=3)
        for offset in (-1,0,1):
            draw.line((175+offset*41,382,199+offset*41,302),fill=ink,width=4)
            for i in range(4):
                x=182+offset*41+i*4
                y=357-i*13
                draw.ellipse((x-15,y-9,x+1,y+4),fill=ink)
        draw.text((192,445),'NET WT. 16 OZ',font=small,anchor='mm',fill=ink)
        image.save(directory/('T_'+name+'.png'))


class ProductMesh:
    def __init__(self):
        self.points=[]
        self.faces=[]

    def box(self,center,size,material):
        x,y,z=center
        a,b,c=(side/2 for side in size)
        start=len(self.points)
        self.points.extend((x+dx*a,y+dy*b,z+dz*c)
                           for dx,dy,dz in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                                            (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)))
        for face in ((0,3,2,1),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)):
            self.faces.append((material,[start+index for index in face]))

    def sphere(self,center,size,material):
        start=len(self.points)
        rings,segments=8,16
        for ring in range(rings+1):
            phi=-pi/2+pi*ring/rings
            for segment in range(segments):
                theta=tau*segment/segments
                self.points.append((center[0]+size[0]/2*cos(phi)*cos(theta),
                                    center[1]+size[1]/2*cos(phi)*sin(theta),
                                    center[2]+size[2]/2*sin(phi)))
        for ring in range(rings):
            for segment in range(segments):
                a=start+ring*segments+segment
                b=start+ring*segments+(segment+1)%segments
                self.faces.append((material,[a,b,b+segments,a+segments]))

    def save(self,name):
        directory=OUT/'Groceries/Created'
        directory.mkdir(parents=True,exist_ok=True)
        lines=['o SM_'+name,'vt 0 0','vt 1 0','vt 1 1','vt 0 1']
        lines.extend('v %.5f %.5f %.5f'%(x,-y,z) for x,y,z in self.points)
        previous=None
        for material,face in self.faces:
            if material!=previous:
                lines.append('usemtl '+material)
                previous=material
            lines.append('f '+' '.join('%d/%d'%(vertex+1,index%4+1) for index,vertex in enumerate(reversed(face))))
        (directory/('SM_'+name+'.obj')).write_text('\n'.join(lines)+'\n',encoding='utf-8')


def groceries():
    for name,size in (('Cereal',(15,6,25)),('Rice',(11,6,20)),('Buckwheat',(11,6,20)),('Flour',(12,8,21))):
        model=ProductMesh()
        model.box((0,0,size[2]/2),size,name)
        model.box((0,0,size[2]+.4),(size[0]-.6,1.8,.8),'Paper')
        model.save(name)
    milk=ProductMesh()
    milk.box((0,0,10.5),(9,9,21),'Milk')
    start=len(milk.points)
    milk.points.extend((x,y,z) for x,y,z in ((-4.5,-4.5,21),(4.5,-4.5,21),(4.5,4.5,21),(-4.5,4.5,21),
                                           (-4.5,0,25),(4.5,0,25)))
    for face in ((0,1,5,4),(1,2,5),(2,3,4,5),(3,0,4)):
        milk.faces.append(('Paper',[start+index for index in face]))
    milk.box((0,0,25.3),(9,1,.6),'Paper')
    milk.save('Milk')
    bread=ProductMesh()
    bread.sphere((0,0,4.6),(22,11,9.2),'Crust')
    for x in (-6,-2,2,6):
        bread.box((x,-.1,8.8),(1.1,7,.35),'Crumb')
    bread.save('Bread')
    eggs=ProductMesh()
    eggs.box((0,0,1.5),(28,17,3),'Carton')
    for x in (-10,-6,-2,2,6,10):
        for y in (-4.1,4.1):
            eggs.sphere((x,y,4.3),(3.6,4.3,5.7),'Egg')
    eggs.save('Eggs')


if __name__=='__main__':
    fonts()
    supplied_models()
    signs()
    labels()
    groceries()
    print('BRIGHTON_RESOURCES_OK')
