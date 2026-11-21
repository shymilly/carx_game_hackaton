"""Dress the road-facing park wall and the adjoining blind return."""
from random import Random

import unreal as ue

from ApartmentScene import make_material
from BrightonOuterBlocks import OuterBlocks
from BrightonUpgrade import ACTORS, LIB, P, PROJECT, V, media, node, output, save

TAG = ue.Name('BrightonParkFrontage')
ART = '/Game/StreetArtPass/ParkFrontage'


class Frontage(OuterBlocks):
    def actor(self, cls, name, position=(0,0,0), rotation=None):
        actor = super().actor(cls,name,position,rotation)
        actor.tags = [TAG]
        actor.set_folder_path(ue.Name('Brighton/Park frontage'))
        return actor


def artwork():
    result = {}
    for name, title, is_paint in (('Video','TapeBanner',False),('Market','SwapBanner',False),('Tag','B4Tag',True)):
        texture = media(PROJECT/'Resources/Brighton/Street/WallArt'/('T_Brighton'+title+'.png'),ART+'/Textures')
        material = make_material(ART,name,(.6,.6,.6),.90)
        sample = LIB.get_material_property_input_node(material,P.MP_BASE_COLOR)
        if not isinstance(sample,ue.MaterialExpressionTextureSample):
            sample = node(material,ue.MaterialExpressionTextureSample,texture=texture)
            output(sample,material,P.MP_BASE_COLOR,'RGB')
        if is_paint:
            material.set_editor_properties(dict(blend_mode=ue.BlendMode.BLEND_MASKED,opacity_mask_clip_value=.28))
            output(sample,material,P.MP_OPACITY_MASK,'A')
        LIB.recompile_material(material)
        save(material)
        result[name]=material
    return result


def picture(city,label,material,position,width,height,reverse_texture=False):
    plane = city.individual(label,ue.load_asset('/Engine/BasicShapes/Plane'),position)
    sign=-1 if reverse_texture else 1
    plane.set_actor_rotation(ue.MathLibrary.make_rot_from_xy(V(0,sign,0),V(0,0,sign)),False)
    plane.set_actor_scale3d(V(width/100,height/100,1))
    mesh = plane.get_component_by_class(ue.StaticMeshComponent)
    mesh.set_material(0,material)
    mesh.set_cull_distance(6500)
    mesh.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False))


def windows(city,wall,bays,levels):
    frame = city.materials['frame']
    dark = city.materials['dark_glass']
    bright = ue.load_asset('/Game/Prologue/Street/Materials/M_lit_window')
    assert bright
    for row,z in enumerate(levels):
        for bay,y in enumerate(bays):
            label='Upper sash windows along the park'
            glass=bright if (row*3+bay)%7 in (2,5) else dark
            city.part(label+' stone reveal',(wall+2.5,y,z),(115,7,158),'stone',90,cull=10500)
            city.box(label+' panes',(wall+7,y,z),(96,2,140),glass,90,cull=10500)
            for edge in (-1,1):
                city.box(label+' side frame',(wall+9,y+edge*50,z),(5.5,4,148),frame,90,cull=10500)
                city.box(label+' lintel',(wall+9,y,z+edge*71),(102,4,4.5),frame,90,cull=10500)
            city.box(label+' sash',(wall+9,y,z),(3.8,3.4,142),frame,90,cull=10500)
            city.box(label+' crossbar',(wall+9,y,z+7),(98,3.4,3.8),frame,90,cull=10500)
            city.part(label+' edge sill',(wall+11,y,z-80),(124,26,7),'stone',90,cull=10500)


def dress_park_frontage(is_apartment,art):
    from CityLifeEnvironment import STREET_SHIFT
    city=Frontage(STREET_SHIFT if is_apartment else (0,0,0))
    actors = ACTORS.get_all_level_actors()
    old = [a for a in actors if a.actor_has_tag(TAG)]
    if old:
        assert ACTORS.destroy_actors(old)
    facade = next(a for a in actors if a.get_actor_label().removeprefix('Third-floor view ')=='Park north perimeter terraces')
    center,extent = facade.get_actor_bounds(False)
    face = center.x-city.offset.x+extent.x
    facade.get_component_by_class(ue.StaticMeshComponent).set_material(0,city.materials['stucco'])
    windows(city,face,[515+181*i for i in range(12)],(445,735))
    windows(city,1620,(2684,2895,3107),(445,735))
    city.part('Park frontage limestone belt',(face+3,1515,288),(2196,13,13),'stone',90)
    city.part('Park frontage base kickplate',(face+2,1515,27),(2196,7,79),'dark_stone',90)
    for y,kind,w,z in ((690,'Video',277,166),(2090,'Market',294,154)):
        city.part('Painted sign mounting',(face+3.2,y,z),(w+6,7,w/2+6),'frame',90,cull=8000)
        picture(city,'Vintage bilingual '+kind+' banner',art[kind],(face+7.1,y,z),w,w/2,True)
    picture(city,'Faded B4 alley tag',art['Tag'],(face+.72,1404,131),339,127.1,True)
    for index,(pos,width,number) in enumerate(((960,61,2),(1025,48,5),(1734,51,7),(1799,65,12),(2272,46,21),(2826,55,17))):
        poster = ue.load_asset(f'/Game/ImportedAssets/Posters/AmericanRetro/AppliedMaterials/MI_Poster_{number:02}')
        assert poster
        texture = LIB.get_material_instance_texture_parameter_value(poster,ue.Name('PosterImage'))
        assert texture
        height=width*texture.blueprint_get_size_y()/texture.blueprint_get_size_x()
        x=face if pos<2600 else 1620
        picture(city,'Weathered local paper notice',poster,(x+.65,pos,114+index%3*13),width,height)

    rng=Random(1494)
    litter=ue.load_asset('/Game/Story/ActOne/Materials/M_paper')
    bag=ue.load_asset('/Game/Story/ActOne/Materials/M_charcoal')
    assert litter and bag
    sphere=ue.load_asset('/Engine/BasicShapes/Sphere')
    for y in (569,1105,1527,2206,2950):
        wall=face if y<2600 else 1620
        for index in range(5):
            city.box('Paper scraps by the wall',(wall+rng.uniform(15,88),y+rng.uniform(-47,47),-11.1),
                     (rng.uniform(7,24),rng.uniform(5,14),.35),litter,rng.uniform(0,360),cull=4200)
        for index in range(3):
            position=(wall+26+index*17,y+index*27,2+index*1.5)
            city.instance('Tied refuse bags',sphere,position,(.43,.31,.30),rng.uniform(0,360),bag,cull=6800)
    city.grounded('Dumpster against the park wall','Dumpster',(face+55,2352,-12),.62,90,cull=8700)
    for y in (1120,1845):
        city.grounded('Park frontage metal waste bin','TrashCan',(face+41,y,-12),.84,0,cull=6800)
    for mat in {litter,bag}:
        LIB.set_material_usage(mat,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        save(mat)
    ue.log('PARK_FRONTAGE_READY windows=30 banners=2 graffiti=1')
