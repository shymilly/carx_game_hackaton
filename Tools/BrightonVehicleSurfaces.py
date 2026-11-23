"""Build window openings and the paint, glazing and cabin finishes for the Brighton fleet."""
from functools import cache
from math import cos, sin, tau
from typing import NamedTuple

import unreal as ue

from BrightonUpgrade import LIB, P, color, constant, factory_asset, node, output, save


class Cabin(NamedTuple):
    belt: tuple  # Rear, front, half-width and height, in metres.
    roof: tuple
    pillars: tuple


CABINS = {
    'sedan': Cabin((-1.43,1.29,.818,.963),(-.91,.69,.714,1.57),(.47,)),
    'coupe': Cabin((-1.48,1.29,.805,.880),(-.54,.48,.690,1.40),(.57,)),
    'station_wagon': Cabin((-2.15,1.185,.818,.950),(-1.97,.58,.730,1.59),(.31,.59)),
    'pickup': Cabin((-.65,1.145,.807,1.000),(-.49,.56,.727,1.64),()),
    'van': Cabin((-2.32,1.31,.881,1.025),(-2.16,.75,.816,1.83),(.31,.63)),
}


BODY_TOPS = {
    'sedan': ((-2.45,.66),(-2.29,.825),(-1.48,.943),(1.27,.963),(1.86,.868),(2.42,.66)),
    'coupe': ((-2.38,.55),(-2.15,.79),(-1.28,.88),(1.22,.88),(2.19,.73),(2.32,.55)),
    'station_wagon': ((-2.43,.62),(-2.29,.92),(-2.15,.95),(1.2,.95),(2.21,.835),(2.35,.61)),
    'pickup': ((-2.44,.705),(-.7,.705),(-.60,.99),(1.16,1.0),(2.24,.853),(2.36,.65)),
    'van': ((-2.38,.89),(-2.32,1.025),(1.31,1.025),(1.75,.92),(2.03,.79),(2.16,.58)),
}


def face(vertices, faces, material, points, flip=False):
    indices = list(range(len(vertices),len(vertices)+len(points)))
    vertices.extend(points)
    faces.append((material,list(reversed(indices)) if flip else indices))


def box(vertices, faces, material, center, size):
    x,y,z = center
    a,b,c = (value*.5 for value in size)
    corners = [(x+i*a,y+j*b,z+k*c) for k in (-1,1) for j in (-1,1) for i in (-1,1)]
    for quad in ((0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)):
        face(vertices,faces,material,[corners[i] for i in quad])


def frame(vertices,faces,corners,bars):
    a,b,c,d = corners

    def sample(u,v):
        return tuple((x*(1-u)+y*u)*(1-v)+(w*(1-u)+z*u)*v for x,y,z,w in zip(a,b,c,d))

    def strip(material,u0,u1,v0,v1):
        face(vertices,faces,material,[sample(u0,v0),sample(u1,v0),sample(u1,v1),sample(u0,v1)])

    bottom,top = .09,.91
    strip('paint',0,1,0,bottom)
    strip('paint',0,1,top,1)
    edges = [(0,.05),*((at-.016,at+.016) for at in bars),(.95,1)]
    for left,right in edges:
        strip('paint',left,right,bottom,top)
    for (_,u0),(u1,_) in zip(edges,edges[1:]):
        # The narrow rubber perimeter seals a real opening in the painted frame.
        inset = .010
        strip('trim',u0,u1,bottom,bottom+inset)
        strip('trim',u0,u1,top-inset,top)
        strip('trim',u0,u0+inset,bottom+inset,top-inset)
        strip('trim',u1-inset,u1,bottom+inset,top-inset)
        strip('glass',u0+inset,u1-inset,bottom+inset,top-inset)


def cabin_geometry(vertices,faces,model):
    cabin = CABINS[model]
    r,f,w,z = cabin.belt
    rr,fr,wr,roof = cabin.roof
    # The glazing meets the roof along its lower edge. Centre crown softens the roof silhouette.
    eave = roof-.042
    base = [(r,-w,z),(f,-w,z),(f,w,z),(r,w,z)]
    upper = [(rr,-wr,eave),(fr,-wr,eave),(fr,wr,eave),(rr,wr,eave)]
    crown = [(rr+.035,-wr*.94,roof),(fr-.035,-wr*.94,roof),
             (fr-.035,wr*.94,roof),(rr+.035,wr*.94,roof)]
    for i in range(4):
        j = (i+1)%4
        bars = cabin.pillars if i==0 else tuple(1-b for b in reversed(cabin.pillars)) if i==2 else ()
        frame(vertices,faces,(base[i],base[j],upper[j],upper[i]),bars)
        face(vertices,faces,'paint',(upper[i],upper[j],crown[j],crown[i]))
    face(vertices,faces,'paint',crown)

    # Seats, dashboard and wheel stay within the sill and can be seen through the panes.
    width = min(.49,w*.61)
    head_z = roof-.15
    for side in (-1,1):
        y = w*.44*side
        seat = fr-.60
        box(vertices,faces,'interior',(seat,y,z-.18),(.46,width,.14))
        box(vertices,faces,'interior',(seat-.22,y,(z-.15+head_z)*.5),(.13,width,head_z-z+.15))
        box(vertices,faces,'seat',(seat-.145,y,(z-.08+head_z-.105)*.5),(.035,width*.79,head_z-z-.025))
        box(vertices,faces,'interior',(seat-.23,y,head_z+.035),(.15,width*.53,.10))
    if model!='pickup':
        rear = rr+.30
        box(vertices,faces,'interior',(rear,0,z-.14),(.46,w*1.69,.14))
        box(vertices,faces,'seat',(rear-.20,0,z+.09),(.13,w*1.65,.43))
    box(vertices,faces,'interior',(f-.26,0,z-.015),(.39,w*1.77,.16))
    center = (f-.50,-w*.46,z+.106)
    for i in range(16):
        angles = (tau*i/16,tau*(i+1)/16)
        points = [(center[0]-sin(a)*v*.31,center[1]+cos(a)*v,center[2]+sin(a)*v)
                  for a,v in ((angles[0],.163),(angles[1],.163),(angles[1],.142),(angles[0],.142))]
        face(vertices,faces,'trim',points,True)
    box(vertices,faces,'trim',center,(.026,.225,.035))


def material(folder,name,tint,roughness,metallic=0):
    value = factory_asset(folder,'M_'+name,ue.Material,ue.MaterialFactoryNew())
    LIB.delete_all_material_expressions(value)
    output(color(value,tint),value,P.MP_BASE_COLOR)
    output(constant(value,roughness),value,P.MP_ROUGHNESS)
    if metallic:
        output(constant(value,metallic),value,P.MP_METALLIC)
    return value


@cache
def cabin_finishes(folder):
    glass = material(folder,'AutomotiveGlazing',(.027,.042,.061),.19,.12)
    glass.set_editor_properties(dict(blend_mode=ue.BlendMode.BLEND_OPAQUE,two_sided=True,
        shading_model=ue.MaterialShadingModel.MSM_DEFAULT_LIT))
    output(constant(glass,.64),glass,P.MP_SPECULAR)
    materials = {'glass':glass}
    for key,tint,roughness in (('trim',(.027,.032,.038),.60),
                              ('interior',(.064,.063,.055),.83),('seat',(.123,.104,.080),.91)):
        materials[key] = material(folder,'Automotive_'+key.capitalize(),tint,roughness)
    for surface in materials.values():
        LIB.recompile_material(surface)
        save(surface)
    return materials


def exterior_materials(folder,model,tint):
    paint = material(folder,model.title().replace('_','')+'_Enamel',tint,.35,.10)
    paint.set_editor_property('shading_model',ue.MaterialShadingModel.MSM_CLEAR_COAT)
    LIB.recompile_material(paint)
    save(paint)
    return {'paint':paint,**cabin_finishes(folder)}
