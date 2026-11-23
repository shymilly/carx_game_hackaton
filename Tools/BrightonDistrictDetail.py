"""Dress Brighton's masonry, freight cars and the four-floor Fedor stairwell."""
from random import Random

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, LIB, P, PROJECT, V, connect, constant, factory_asset, media, node, output, save
from CityLifeEnvironment import CityLayout, STREET_SHIFT
from FedorBuildingAndPursuit import FLOOR


ROOT = '/Game/StreetArtPass/BrightonDetail'
TAG = ue.Name('BrightonDistrictDetail')
CITY = '/Game/Prologue/CityLife/Meshes/SM_'
ACT = '/Game/Story/ActOne/Materials/M_'


def load(path):
    asset = ue.load_asset(path)
    assert asset,path
    return asset


class Detail(CityLayout):
    def actor(self, cls, label, position=(0,0,0), rotation=None):
        actor = super().actor(cls,label,position,rotation)
        actor.tags = [TAG]
        actor.set_folder_path('Brighton/Neighborhood detail')
        return actor

    def decal(self, material, label, position, yaw, size):
        actor = self.actor(ue.DecalActor,label,position,ue.Rotator(yaw=yaw))
        component = actor.get_component_by_class(ue.DecalComponent)
        component.set_decal_material(material)
        component.set_editor_property('decal_size',V(6,size[0]*.5,size[1]*.5))
        component.set_fade_screen_size(.018)

    def grounded(self, label, mesh, point, scale, yaw):
        box = mesh.get_bounding_box()
        self.instance(label,mesh,(point[0],point[1],point[2]-box.min.z*scale),(scale,scale,scale),yaw,cull=6200)

    def save_instance_materials(self):
        materials = {component.get_material(index) for component in self.batches.values()
                     for index in range(component.get_num_materials())}
        for material in materials:
            if isinstance(material,ue.Material) and material.get_path_name().startswith('/Game/'):
                LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
                save(material)


def paint_materials():
    file = PROJECT/'Resources/Brighton/Street/WallArt/T_BrightonGraffiti.png'
    atlas = media(file,ROOT+'/Textures')
    atlas.set_editor_properties(dict(address_x=ue.TextureAddress.TA_CLAMP,address_y=ue.TextureAddress.TA_CLAMP,
        power_of_two_mode=ue.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO,never_stream=True))
    save(atlas)
    palette = {}
    for name,top,bottom in (('Tide',0,319),('Bereg',324,627),('Salt',636,887)):
        material = factory_asset(ROOT+'/Materials','M_Graffiti'+name,ue.Material,ue.MaterialFactoryNew())
        LIB.delete_all_material_expressions(material)
        material.set_editor_properties(dict(material_domain=ue.MaterialDomain.MD_DEFERRED_DECAL,
                                            blend_mode=ue.BlendMode.BLEND_TRANSLUCENT))
        projected = node(material,ue.MaterialExpressionTextureCoordinate)
        # Deferred decals supply UV as local (Z,Y); the atlas is authored left-to-right, top-to-bottom.
        u = node(material,ue.MaterialExpressionComponentMask,r=False,g=True,b=False,a=False)
        z = node(material,ue.MaterialExpressionComponentMask,r=True,g=False,b=False,a=False)
        v = node(material,ue.MaterialExpressionOneMinus)
        scale = node(material,ue.MaterialExpressionMultiply,const_b=(bottom-top)/887)
        offset = node(material,ue.MaterialExpressionAdd,const_b=top/887)
        region = node(material,ue.MaterialExpressionAppendVector)
        connect(projected,u)
        connect(projected,z)
        connect(z,v)
        connect(v,scale,'A')
        connect(scale,offset,'A')
        connect(u,region,'A')
        connect(offset,region,'B')
        image = node(material,ue.MaterialExpressionTextureSample,texture=atlas)
        connect(region,image,'UVs')
        output(image,material,P.MP_BASE_COLOR,'RGB')
        alpha = node(material,ue.MaterialExpressionMultiply,const_b=.81)
        connect(image,alpha,'A','A')
        output(alpha,material,P.MP_OPACITY)
        output(constant(material,.80),material,P.MP_ROUGHNESS)
        LIB.recompile_material(material)
        save(material)
        palette[name] = material
    return palette


def clear():
    old = [actor for actor in ACTORS.get_all_level_actors() if actor.actor_has_tag(TAG)]
    if old:
        assert ACTORS.destroy_actors(old)


def wall_tag(city, actors, palette, label, art, axis, side, along, z, size):
    wall = next((actor for actor in actors if actor.get_actor_label().removeprefix('Third-floor view ')==label),None)
    if not wall:
        return
    center, extent = wall.get_actor_bounds(False)
    x,y,_ = (center-city.offset).to_tuple()
    if axis == 'x':
        x += side * extent.x
        y += along
        yaw = 180 if side>0 else 0
    else:
        y += side * extent.y
        x += along
        yaw = -90 if side>0 else 90
    city.decal(palette[art],f'{art} spray paint on {label}',(x,y,z),yaw,size)


def litter(city, sites):
    rng = Random(941020)
    paper = load(ACT+'paper')
    news = load(ACT+'ivory')
    ink = load(ACT+'charcoal')
    enamel = load(ACT+'tobacco')
    silver = load(ACT+'steel')
    sphere = load('/Engine/BasicShapes/Sphere')
    bin_mesh = load(CITY+'TrashCan')
    for index,(x,y,z) in enumerate(sites):
        if index%2 == 0:
            city.grounded('Street waste bin',bin_mesh,(x,y,z),.77,35+index*60)
            city.instance('Tied refuse bags',sphere,(x+31,y+22,z+11),(.24,.22,.25),surface=ink,cull=5200)
            city.instance('Tied refuse bags',sphere,(x+33,y+22,z+23),(.032,.039,.052),surface=ink,cull=5200)
        for j in range(6):
            p = x+rng.uniform(-49,60),y+rng.uniform(-18,42),z+.24+.06*j
            city.box('Old print scraps',p,(rng.uniform(8,26),rng.uniform(5,15),.26),
                     paper if j%3 else news,rng.randrange(360),pitch=rng.uniform(-3,3),cull=4200)
        city.cylinder_part('Crushed enamel soda cans',(x-42,y+30,z+2.7),(5.6,5.6,10),enamel,pitch=87,cull=4600)
        city.cylinder_part('Metal rims on discarded cans',(x-37,y+30,z+2.6),(5.8,5.8,1),silver,pitch=87,cull=4600)


def train_graffiti(actors, materials):
    total = 0
    for rail in (actor for actor in actors if isinstance(actor,ue.CityRailTraffic)):
        cars = list(rail.get_editor_property('consist'))
        for index,car in enumerate(cars):
            if car.mesh.get_name() != 'SM_FreightBoxcar':
                continue
            name = 'Tide' if index%3 else 'Salt'
            car.graffiti = [ue.CityRailCarGraffiti(material=materials[name if side==1 else 'Bereg'],
                center=V(-185 if side==1 else 181,side*138.6,151),
                size=ue.Vector2D(426 if name=='Tide' else 375,77),projection_yaw=-side*90) for side in (-1,1)]
            cars[index] = car
            total += len(car.graffiti)
        rail.set_editor_property('consist',cars)
    ue.log(f'BRIGHTON_RAIL_ART {total} car-side decals')


def street(materials, from_apartment):
    clear()
    city = Detail({},STREET_SHIFT if from_apartment else (0,0,0))
    actors = ACTORS.get_all_level_actors()
    for label,art,axis,side,along,z,size in (
        ('Park frontage wall below the facade','Tide','y',-1,2,120,(326,69)),
        ('Courtyard west end beside bathroom','Bereg','y',1,50,92,(272,55)),
        ('Courtyard wall brick infill','Salt','y',1,169,128,(252,55)),
        ('Park north perimeter terraces','Salt','x',-1,410,58,(276,63)),
        ('Park south perimeter terrace','Bereg','x',1,-590,66,(237,55)),
    ):
        wall_tag(city,actors,materials,label,art,axis,side,along,z,size)
    litter(city,((-681,-461,-12),(-1315,1615,-12),(1450,2280,-12),(-4740,-1980,-12),
                 (-350,-1769,-12),(1440,-587,-12),(3920,4270,-17),(4030,-4952,-17)))
    city.save_instance_materials()
    train_graffiti(actors,materials)


def fedor_stairwell(materials):
    clear()
    city = Detail({})
    plaster = load('/Game/StreetRefinement/Materials/M_GreyPaintedPlaster')
    pale_terrazzo = load('/Game/StreetRefinement/Materials/M_WeatheredConcrete')
    enamel = make_material(ROOT,'StairwellEnamel',(.076,.124,.093),.64)
    brass = load(ACT+'brass')
    black = load(ACT+'charcoal')
    wood = load(ACT+'dark_wood')
    metal = load(ACT+'steel')
    tan = load(ACT+'paper')
    letter = load(ACT+'ivory')
    actors = ACTORS.get_all_level_actors()
    for actor in actors:
        label = actor.get_actor_label()
        if label in ('Lobby rear plaster wall','Stairwell outer plaster wall','Landings beside the apartments'):
            actor.get_component_by_class(ue.StaticMeshComponent).set_material(0,plaster)
        if label in ('Lobby ground floor','Full-width main landing','Intermediate landing between flights',
                     'Concrete stair tread and riser'):
            actor.get_component_by_class(ue.StaticMeshComponent).set_material(0,pale_terrazzo)
        if label == 'Tungsten landing lamp':
            lamp = actor.get_component_by_class(ue.PointLightComponent)
            lamp.set_intensity(29)

    for floor in range(4):
        z = floor*FLOOR
        for y in (-134,130):
            city.box('Two-tone stairwell entrance paint',(506.1,y,z+53),(1.3,99,105),enamel)
            city.box('Baseboard by the landing',(508,y,z+6),(4.7,99,12),wood)
        city.box('Dado against the outer wall',(579,-189.3,z+47),(142,1.6,92),enamel)
        city.box('Outer-wall skirting',(579,-186.8,z+7),(143,5,14),wood)
        city.box('Stamped floor-number plate',(514,112,z+149),(3,34,39),black)
        city.box('Vintage landing lamp backplate',(507,-24,z+205),(5,41,34),metal)
        for rib in (-10,0,10):
            city.box('Protective cage over the lamp',(524,-24+rib,z+205),(4,2.4,29),metal,cull=3500)
        if floor<3:
            city.box('Landing return paint band',(1048,18,z+181),(1.4,313,93),enamel)
            city.box('Turn-landing runner',(964,-37,z+135.62),(91,201,1.5),black)
            for side in (-1,1):
                city.box('Runner woven edge',(964,side*95-37,z+136.42),(91,2.5,.3),tan)
        for y in (-172,-160):
            city.cylinder_part('Painted conduit clamps',(532,y,z+228),(16,16,6),metal)

    for y in (-172,-160):
        city.cylinder_part('Old vertical service conduit',(532,y,546),(4.1,4.1,1092),metal)
    city.box('Metal mailbox housing',(508,-128,123),(11,99,77),metal)
    for row in range(3):
        for column in range(4):
            y,z = -165+column*24.5,99+row*24
            city.box('Mailbox doors with rounded labels',(515,y,z),(3,22.8,21),enamel)
            city.box('Brass mailbox number tabs',(517,y-2,z+4),(1.1,11.2,4.6),brass)
            city.box('Mailbox lock and keyhole',(517.1,y+6,z-4),(1.2,3.5,3.5),black)
    city.box('Weathered notice board frame',(507,127,141),(8,81,88),wood)
    city.box('Cork notice board face',(512,127,141),(1.7,72,79),tan)
    for y,z,width,height in ((111,147,25,44),(140,151,26,35),(126,114,36,13)):
        city.box('Pinned building notices',(513.5,y,z),(.8,width,height),letter)
        for line in range(3):
            city.box('Handwritten notice strokes',(514,y,z-4-line*3.5),(.2,width*.65,1.1),metal)
        city.box('Brass notice pin',(514.4,y,z+height*.36),(1.6,2,2),brass)
    city.box('Rubber entrance mat',(559,1,1),(87,115,1.8),black)
    for line in range(-47,48,8):
        city.box('Mat drainage ribs',(558,line,2.1),(76,2,.5),metal)
    city.box('Intercom casing outside the front door',(479,107,142),(9,25,35),metal)
    for z in (134,141,148):
        city.box('Intercom grille',(473.5,107,z),(2,16,1.8),black)
    city.box('Intercom call button',(472.8,107,128),(2.8,4.7,4.7),brass)
    city.decal(materials['Salt'],'Faded hand tag on courtyard retaining wall',(126,545.5,64),90,(203,43))
    litter(city,((-620,509,0),(348,-520,0)))
    city.save_instance_materials()
    ue.log('FEDOR_DETAIL_OK four landings, mailbox bank, notice board, intercom and conduits')


def alley(materials):
    clear()
    city = Detail({})
    actors = ACTORS.get_all_level_actors()
    wall_tag(city,actors,materials,'Entry retaining wall','Salt','x',1,244,103,(200,53))
    wall_tag(city,actors,materials,'Wall sealing the back of the first bend','Bereg','x',1,27,124,(242,65))
    wall_tag(city,actors,materials,'Solid rear wall joining the last corner','Tide','x',1,-80,148,(280,64))
