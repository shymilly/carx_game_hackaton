"""Targeted storefront, facade and weather authoring for the active Brighton maps."""
from math import cos, floor, radians, sin, sqrt
from pathlib import Path
from random import Random
import json
import re

import unreal as ue

from ApartmentScene import make_material
from RefineStreetVisuals import LEFT, RIGHT, FAR, FOLDER, bounds, typography
from StreetMaterials import custom_input

ROOT='/Game/Prologue/Brighton'
GROCERY='/Game/Prologue/Furniture/Grocery'
TAG=ue.Name('BrightonUpgrade_v1')
PROJECT=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
SOURCE=PROJECT/'Resources/Brighton'
ASSETS=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
ACTORS=ue.get_editor_subsystem(ue.EditorActorSubsystem)
LEVELS=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
TOOLS=ue.AssetToolsHelpers.get_asset_tools()
LIB=ue.MaterialEditingLibrary
P=ue.MaterialProperty
V=ue.Vector


def vector(value):
    return value.x,value.y,value.z


def save(asset):
    assert ASSETS.save_loaded_asset(asset,False),asset


def factory_asset(folder,name,cls,factory):
    path=folder+'/'+name
    if ASSETS.does_asset_exist(path):return ue.load_asset(path)
    ASSETS.make_directory(folder)
    result=TOOLS.create_asset(name,folder,cls,factory)
    assert result,path
    return result


def media(file,folder,name=None,replace_existing=False):
    name=name or file.stem
    destination=folder+'/'+name
    if ASSETS.does_asset_exist(destination) and not replace_existing:return ue.load_asset(destination)
    task=ue.AssetImportTask()
    task.set_editor_properties(dict(filename=str(file),destination_path=folder,destination_name=name,
                                    automated=True,save=False,replace_existing=replace_existing))
    if file.suffix=='.obj':
        options=ue.FbxImportUI()
        options.set_editor_properties(dict(import_materials=False,import_textures=False,import_as_skeletal=False))
        options.get_editor_property('static_mesh_import_data').set_editor_property('combine_meshes',True)
        task.set_editor_property('options',options)
    TOOLS.import_asset_tasks([task])
    result=ue.load_asset(destination)
    assert result,destination
    save(result)
    return result


def node(material,cls,**properties):
    value=LIB.create_material_expression(material,cls,0,0)
    if properties:value.set_editor_properties(properties)
    return value


def constant(material,value):
    return node(material,ue.MaterialExpressionConstant,r=value)


def color(material,value):
    return node(material,ue.MaterialExpressionConstant3Vector,constant=ue.LinearColor(*value,1))


def connect(source,target,input_name='',output=''):
    assert LIB.connect_material_expressions(source,output,target,input_name),(source,target,input_name,output)


def output(expression,material,property_name,pin=''):
    assert LIB.connect_material_property(expression,pin,property_name)


def weather_collection():
    collection=factory_asset(ROOT+'/Materials','MPC_Weather',ue.MaterialParameterCollection,ue.MaterialParameterCollectionFactoryNew())
    if not collection.get_editor_property('scalar_parameters'):
        parameter=ue.CollectionScalarParameter()
        parameter.set_editor_properties(dict(parameter_name=ue.Name('Wetness'),default_value=0))
        collection.set_editor_property('scalar_parameters',[parameter])
        save(collection)
    return collection


def wet_value(material,collection):
    return node(material,ue.MaterialExpressionCollectionParameter,collection=collection,parameter_name=ue.Name('Wetness'))


def weather_material(source,collection):
    name='M_Wet_'+source.get_name().removeprefix('M_')
    path=ROOT+'/Materials/'+name
    if ASSETS.does_asset_exist(path):return ue.load_asset(path)
    material=ASSETS.duplicate_asset(source.get_path_name(),path)
    assert material,path
    base=LIB.get_material_property_input_node(material,P.MP_BASE_COLOR)
    normal=LIB.get_material_property_input_node(material,P.MP_NORMAL)
    wet=wet_value(material,collection)
    position=node(material,ue.MaterialExpressionWorldPosition)
    mask=node(material,ue.MaterialExpressionCustom,inputs=[custom_input('Position')],
        output_type=ue.CustomMaterialOutputType.CMOT_FLOAT1,description='World-space shallow puddles',code='''
float2 p=Position.xy*0.006;
float n=sin(p.x+0.8*sin(p.y*1.7))*sin(p.y*1.24-0.4*cos(p.x*1.8));
return smoothstep(0.05,0.61,n);
''')
    connect(position,mask,'Position')
    puddles=node(material,ue.MaterialExpressionMultiply)
    connect(wet,puddles,'A')
    connect(mask,puddles,'B')
    rough=node(material,ue.MaterialExpressionLinearInterpolate,const_a=.79,const_b=.14)
    connect(wet,rough,'Alpha')
    glossy=node(material,ue.MaterialExpressionLinearInterpolate,const_b=.045)
    connect(rough,glossy,'A')
    connect(puddles,glossy,'Alpha')
    output(glossy,material,P.MP_ROUGHNESS)
    if base:
        dark=node(material,ue.MaterialExpressionMultiply,const_b=.64)
        channel='RGB' if isinstance(base,ue.MaterialExpressionTextureSample) else ''
        connect(base,dark,'A',channel)
        blend=node(material,ue.MaterialExpressionLinearInterpolate)
        connect(base,blend,'A',channel)
        connect(dark,blend,'B')
        connect(wet,blend,'Alpha')
        output(blend,material,P.MP_BASE_COLOR)
    if normal:
        blend=node(material,ue.MaterialExpressionLinearInterpolate)
        connect(normal,blend,'A','RGB' if isinstance(normal,ue.MaterialExpressionTextureSample) else '')
        connect(color(material,(0,0,1)),blend,'B')
        connect(puddles,blend,'Alpha')
        output(blend,material,P.MP_NORMAL)
    LIB.recompile_material(material)
    save(material)
    return material


def custom_alpha_material(name,code,tint,instance_fade=False):
    material=make_material(ROOT,name,tint,.3)
    LIB.delete_all_material_expressions(material)
    material.set_editor_properties(dict(blend_mode=ue.BlendMode.BLEND_TRANSLUCENT,
        shading_model=ue.MaterialShadingModel.MSM_UNLIT,two_sided=True))
    uv=node(material,ue.MaterialExpressionTextureCoordinate)
    inputs=[custom_input('UV')]
    if instance_fade: inputs.append(custom_input('Coverage'))
    alpha=node(material,ue.MaterialExpressionCustom,inputs=inputs,
        code=code,output_type=ue.CustomMaterialOutputType.CMOT_FLOAT1)
    connect(uv,alpha,'UV')
    if instance_fade:
        opacity=node(material,ue.MaterialExpressionPerInstanceCustomData,data_index=0,const_default_value=0.)
        interpolator=node(material,ue.MaterialExpressionVertexInterpolator)
        assert LIB.connect_material_expressions(opacity,'',interpolator,'') or LIB.connect_material_expressions(opacity,'',interpolator,'VS')
        connect(interpolator,alpha,'Coverage')
    output(alpha,material,P.MP_OPACITY)
    output(color(material,tint),material,P.MP_EMISSIVE_COLOR)
    LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    LIB.recompile_material(material)
    save(material)
    return material


def weather_effects():
    splash=custom_alpha_material('RainRing','''
float2 p = (UV-.5)*2;
float r = length(p);
float outer = 1-smoothstep(.024,.075,abs(r-.79));
float inner = (1-smoothstep(.017,.045,abs(r-.49)))*.22;
float irregular = .82+.18*sin(atan2(p.y,p.x)*7+2*r);
float glint = (1-smoothstep(.03,.17,r))*.13;
return ((outer+inner)*irregular*.27+glint)*Coverage;
''',(.43,.51,.60),True)
    streak=custom_alpha_material('RainStreak','''
float tip=smoothstep(0,.17,UV.y)*(1-smoothstep(.52,1,UV.y));
return tip*(.32+.12*smoothstep(.12,.48,UV.x));
''',(.49,.59,.71))
    return splash,streak


def projection_material():
    path=ROOT+'/Materials/M_WindowProjection'
    material=make_material(ROOT,'WindowProjection',(1,1,1),1)
    LIB.delete_all_material_expressions(material)
    material.set_editor_property('material_domain',ue.MaterialDomain.MD_LIGHT_FUNCTION)
    uv=node(material,ue.MaterialExpressionTextureCoordinate)
    mask=node(material,ue.MaterialExpressionCustom,inputs=[custom_input('UV')],
        output_type=ue.CustomMaterialOutputType.CMOT_FLOAT1,code='''
float2 p=abs(UV-0.5);
float border=(1-smoothstep(0.27,0.30,p.x))*(1-smoothstep(0.30,0.33,p.y));
float mullion=smoothstep(0.017,0.026,p.x)*smoothstep(0.014,0.023,abs(UV.y-0.55));
return border*mullion;
''')
    connect(uv,mask,'UV')
    output(mask,material,P.MP_EMISSIVE_COLOR)
    LIB.recompile_material(material)
    save(material)
    return material


def environment_data(collection):
    factory=ue.DataAssetFactory()
    factory.set_editor_property('data_asset_class',ue.BrightonEnvironmentData)
    data=factory_asset(ROOT,'DA_Environment',ue.BrightonEnvironmentData,factory)
    surfaces={}
    for kind in ('Wood','Tile','Asphalt','Wet'):
        group=ue.BrightonFootsteps()
        sounds=[media(SOURCE/'Audio'/(kind+str(i)+'.wav'),ROOT+'/Audio') for i in range(4)]
        group.set_editor_property('variations',sounds)
        surfaces[ue.Name(kind)]=group
    data.set_editor_properties(dict(footsteps=surfaces,weather_parameters=collection))
    save(data)
    original=ue.load_asset('/Game/Audio/DimaApartment/S_DimaApartmentAmbient')
    assert original
    scenario=ue.load_asset('/Game/Story/DimaApartment/DA_DimaApartmentScenario')
    scenario.set_editor_properties(dict(ambient=original,ambient_volume=.4))
    save(scenario)


def material_from_mtl(folder,name,spec,texture=None):
    path=folder+'/Materials/M_'+name
    if ASSETS.does_asset_exist(path):
        material=ue.load_asset(path)
        LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        save(material)
        return material
    metal=.72 if name.lower() in ('metal','darkmetal') else 0
    roughness=.27 if metal else .54
    material=make_material(folder,name,spec.get('color',(.4,.4,.4)),roughness)
    if texture:
        sample=node(material,ue.MaterialExpressionTextureSample,texture=texture)
        output(sample,material,P.MP_BASE_COLOR,'RGB')
    if metal:output(constant(material,metal),material,P.MP_METALLIC)
    if name=='Glass':
        material.set_editor_properties(dict(blend_mode=ue.BlendMode.BLEND_TRANSLUCENT,two_sided=True))
        output(constant(material,.28),material,P.MP_OPACITY)
        output(constant(material,.17),material,P.MP_ROUGHNESS)
    LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
    LIB.recompile_material(material)
    save(material)
    return material


def grocery_meshes():
    meshes={}
    names={'green_can_obj':'can','soda_bottle_obj':'bottle','chocolate_bar_obj':'bar','cash_register_obj':'register'}
    for key,stem in names.items():
        directory=SOURCE/'Groceries'/key
        folder=GROCERY+'/'+key
        model=media(directory/('SM_'+key+'.obj'),folder)
        definitions={}
        current=None
        for line in (directory/(stem+'.mtl')).read_text(encoding='utf-8').splitlines():
            fields=line.split()
            if not fields:continue
            if fields[0]=='newmtl':
                current=fields[1]
                definitions[current]={}
            elif current and fields[0]=='Kd':definitions[current]['color']=tuple(map(float,fields[1:4]))
            elif current and fields[0]=='map_Kd':definitions[current]['texture']=fields[-1]
        for index,slot in enumerate(model.get_editor_property('static_materials')):
            name=str(slot.get_editor_property('imported_material_slot_name'))
            spec=definitions.get(name,{})
            texture=media(directory/spec['texture'],folder+'/Textures') if spec.get('texture') else None
            model.set_material(index,material_from_mtl(folder,name,spec,texture))
        save(model)
        meshes[key]=model
    colors={'Paper':(.72,.68,.52),'Crust':(.34,.14,.038),'Crumb':(.59,.36,.13),
            'Egg':(.72,.62,.43),'Carton':(.35,.31,.23)}
    for key in ('Milk','Cereal','Rice','Buckwheat','Flour','Bread','Eggs'):
        folder=GROCERY+'/Created'
        model=media(SOURCE/'Groceries/Created'/('SM_'+key+'.obj'),folder)
        for index,slot in enumerate(model.get_editor_property('static_materials')):
            name=str(slot.get_editor_property('imported_material_slot_name'))
            picture=SOURCE/'Groceries/Labels'/('T_'+name+'.png')
            texture=media(picture,folder+'/Textures') if picture.exists() else None
            model.set_material(index,material_from_mtl(folder,name,dict(color=colors.get(name,(.66,.58,.42))),texture))
        save(model)
        meshes[key]=model
    return meshes


class Builder:
    def __init__(self,folder):
        self.folder=folder
        self.batches={}
        self.shapes={shape:ue.load_asset('/Engine/BasicShapes/'+shape) for shape in ('Cube','Plane','Cylinder','Sphere')}

    def actor(self,cls,name,position=(0,0,0),rotation=None):
        actor=ACTORS.spawn_actor_from_class(cls,V(*position),rotation or ue.Rotator())
        assert actor,name
        actor.set_actor_label(name)
        actor.set_folder_path(ue.Name(self.folder))
        actor.tags=list(actor.tags)+[TAG]
        return actor

    def box(self,name,position,size,material,collision=False):
        actor=self.actor(ue.StaticMeshActor,name,position)
        component=actor.get_component_by_class(ue.StaticMeshComponent)
        component.set_static_mesh(self.shapes['Cube'])
        component.set_material(0,material)
        component.set_collision_profile_name(ue.Name('BlockAll' if collision else 'NoCollision'))
        component.set_cull_distance(26000)
        actor.set_actor_scale3d(V(*(v/100 for v in size)))
        return actor

    def instance(self,key,position,size,material,yaw=0,mesh=None):
        model=mesh or self.shapes['Cube']
        batch_key=(key,model.get_path_name(),material.get_path_name() if material else '')
        if batch_key not in self.batches:
            actor=self.actor(ue.StreetMeshInstances,key)
            component=actor.get_editor_property('instances')
            component.set_static_mesh(model)
            if material:component.set_material(0,material)
            else:
                for index,slot in enumerate(model.get_editor_property('static_materials')):
                    component.set_material(index,slot.get_editor_property('material_interface'))
            component.set_collision_profile_name(ue.Name('NoCollision'))
            component.set_cull_distances(19000,26000)
            self.batches[batch_key]=component
        transform=ue.Transform(location=V(*position),rotation=ue.Rotator(yaw=yaw),scale=V(*size))
        self.batches[batch_key].add_instance(transform,True)


def clear_generated():
    obsolete=[actor for actor in ACTORS.get_all_level_actors() if actor.actor_has_tag(TAG)]
    if obsolete:assert ACTORS.destroy_actors(obsolete)


def configure_weather(splash,streak):
    for actor in ACTORS.get_all_level_actors():
        if isinstance(actor,ue.ActOneDirector):
            rain=actor.get_editor_property('rain')
            rain.set_material(0,streak)
            rings=actor.get_editor_property('rain_splashes')
            rings.set_static_mesh(ue.load_asset('/Engine/BasicShapes/Plane'))
            rings.set_material(0,splash)


def fill_grocery(meshes):
    builder=Builder('Brighton/Groceries')
    current=list(ACTORS.get_all_level_actors())
    old=[a for a in current if a.get_actor_label()=='Cash register housing' or a.get_actor_label().startswith('Register key')]
    if old:assert ACTORS.destroy_actors(old)
    register=builder.actor(ue.StaticMeshActor,'Imported cash register',(246,129,109.7),ue.Rotator(yaw=-90))
    register.get_component_by_class(ue.StaticMeshComponent).set_static_mesh(meshes['cash_register_obj'])
    register.get_component_by_class(ue.StaticMeshComponent).set_collision_profile_name(ue.Name('NoCollision'))
    for index,slot in enumerate(meshes['cash_register_obj'].get_editor_property('static_materials')):
        register.get_component_by_class(ue.StaticMeshComponent).set_material(index,slot.get_editor_property('material_interface'))
    shelves=[a for a in current if a.get_actor_label().startswith('Scuffed empty shelf')]
    catalog=('green_can_obj','soda_bottle_obj','Milk','Cereal','Rice','Buckwheat','Flour','Bread','Eggs','chocolate_bar_obj')
    count=0
    for shelf_index,shelf in enumerate(shelves):
        p,e=shelf.get_actor_bounds(False)
        east=e.y>e.x
        width=2*(e.y if east else e.x)-18
        base=p.z+e.z+.2
        for item in range(max(4,int(width//24))):
            key=catalog[(item//3+shelf_index*2)%len(catalog)]
            distance=-width/2+12+item*24
            location=(p.x-10 if east else p.x+distance,p.y+distance if east else p.y+8,base)
            builder.instance('Shelf stock '+key,location,(1,1,1),None,yaw=180 if east else -90,mesh=meshes[key])
            count+=1
    for index in range(7):
        builder.instance('Chocolate beside the till',(201+index*9,196,109.8),(1,1,1),None,90,meshes['chocolate_bar_obj'])
    for position,power,radius in (((-200,-185,190),38,610),((366,-57,210),34,580),((130,110,209),27,480)):
        lamp=builder.actor(ue.PointLight,'Soft fluorescent reflection on the grocery shelves',position)
        lamp.get_component_by_class(ue.PointLightComponent).set_editor_properties(dict(
            mobility=ue.ComponentMobility.MOVABLE,cast_shadows=False,use_inverse_squared_falloff=False,
            intensity=power,attenuation_radius=radius,light_falloff_exponent=2.2,source_radius=34))
        lamp.get_component_by_class(ue.PointLightComponent).set_light_color(ue.LinearColor(.89,.96,1,1))
    ue.log('BRIGHTON_GROCERY_OK '+str(count)+' products on '+str(len(shelves))+' shelves')


def instance_dimensions(transform):
    q=transform.rotation
    s=transform.scale3d
    matrix=((1-2*(q.y*q.y+q.z*q.z),2*(q.x*q.y-q.z*q.w),2*(q.x*q.z+q.y*q.w)),
            (2*(q.x*q.y+q.z*q.w),1-2*(q.x*q.x+q.z*q.z),2*(q.y*q.z-q.x*q.w)),
            (2*(q.x*q.z-q.y*q.w),2*(q.y*q.z+q.x*q.w),1-2*(q.x*q.x+q.y*q.y)))
    scale=(abs(s.x)*100,abs(s.y)*100,abs(s.z)*100)
    return tuple(sum(abs(matrix[row][column])*scale[column] for column in range(3)) for row in range(3))


def remove_old_windows():
    folders=(FOLDER,'Street/05 Enclosed courtyard','Street/02 Apartment facade')
    windows=[]
    batches=[]
    for actor in ACTORS.get_all_level_actors():
        if str(actor.get_folder_path()) not in folders:continue
        component=actor.get_component_by_class(ue.InstancedStaticMeshComponent)
        if not component or not component.get_material(0):continue
        material=component.get_material(0).get_name()
        batches.append((component,material))
        if material not in ('M_dark_glass','M_lit_window'):continue
        for index in reversed(range(component.get_instance_count())):
            transform=component.get_instance_transform(index,True)
            size=instance_dimensions(transform)
            if min(size[:2])<15 and 60<max(size[:2])<195 and 60<size[2]<210:
                p=transform.translation
                windows.append((p,size))
                component.remove_instance(index)
    for component,material in batches:
        if material not in ('M_stone','M_frame','M_curtain'):continue
        for index in reversed(range(component.get_instance_count())):
            transform=component.get_instance_transform(index,True)
            p=transform.translation
            size=instance_dimensions(transform)
            if max(size[:2])>220 or size[2]>220:continue
            if any(abs(p.x-at.x)<extent[0]/2+35 and abs(p.y-at.y)<extent[1]/2+35 and
                   abs(p.z-at.z)<extent[2]/2+22 for at,extent in windows):component.remove_instance(index)
    ue.log('BRIGHTON_WINDOWS_REPLACED '+str(len(windows)))


def facade_material(name,tint,clapboard=False):
    path=ROOT+'/Materials/M_'+name
    if ASSETS.does_asset_exist(path):return ue.load_asset(path)
    original=ue.load_asset('/Game/StreetRefinement/Materials/M_GreyPaintedPlaster')
    material=ASSETS.duplicate_asset(original.get_path_name(),path)
    base=LIB.get_material_property_input_node(material,P.MP_BASE_COLOR)
    multiply=node(material,ue.MaterialExpressionMultiply)
    connect(base,multiply,'A','RGB' if isinstance(base,ue.MaterialExpressionTextureSample) else '')
    connect(color(material,tint),multiply,'B')
    if clapboard:
        position=node(material,ue.MaterialExpressionWorldPosition)
        seams=node(material,ue.MaterialExpressionCustom,inputs=[custom_input('Position')],
            output_type=ue.CustomMaterialOutputType.CMOT_FLOAT1,code='''
float edge=frac(Position.z/15.5);
return 0.81+0.19*smoothstep(0.025,0.105,edge);
''')
        connect(position,seams,'Position')
        blend=node(material,ue.MaterialExpressionMultiply)
        connect(multiply,blend,'A')
        connect(seams,blend,'B')
        multiply=blend
    output(multiply,material,P.MP_BASE_COLOR)
    LIB.recompile_material(material)
    save(material)
    return material


def house_groups():
    result=[]
    palette=[ue.load_asset('/Game/StreetRefinement/Materials/M_FadedOchreRender'),
        facade_material('PaintedSage',(.70,.94,.74)),facade_material('CreamClapboard',(1.12,1.03,.81),True),
        ue.load_asset('/Game/StreetRefinement/Materials/M_AgedRedBrick'),
        facade_material('BlueClapboard',(.54,.79,.91),True),
        ue.load_asset('/Game/StreetRefinement/Materials/M_WeatheredConcrete'),
        facade_material('WarmPaintedMasonry',(.99,.83,.63)),
        ue.load_asset('/Game/StreetRefinement/Materials/M_SootBrownBrick')]
    for actor in ACTORS.get_all_level_actors():
        name=actor.get_actor_label()
        b=bounds(actor)
        normal=None
        if str(actor.get_folder_path())==FOLDER:
            if name in LEFT:normal=(0,1)
            elif name in RIGHT:normal=(0,-1)
            elif name in FAR:normal=(-1,0)
            elif name.startswith('Cross-street depth row'):normal=(1,0)
        elif str(actor.get_folder_path())=='Street/05 Enclosed courtyard' and b[5]>470:
            if any(word in name.lower() for word in ('terraces','perimeter','homes','walk-up')):
                dx,dy=-310-(b[0]+b[1])/2,1110-(b[2]+b[3])/2
                normal=(1 if dx>0 else -1,0) if abs(dx)>abs(dy) else (0,1 if dy>0 else -1)
        if not normal:continue
        component=actor.get_component_by_class(ue.StaticMeshComponent)
        if not component or isinstance(component,ue.InstancedStaticMeshComponent):continue
        component.set_material(0,palette[len(result)%len(palette)])
        axis=1 if normal[0] else 0
        width=b[axis*2+1]-b[axis*2]
        center=(b[axis*2]+b[axis*2+1])/2
        front=b[1] if normal[0]>0 else b[0] if normal[0]<0 else b[3] if normal[1]>0 else b[2]
        result.append(dict(name=name,normal=normal,width=width,center=center,front=front,height=b[5],
                           storefront=name in ('Grocery walk-up','Pharmacy walk-up','Bar Lighthouse shell')))
    return result


def place_window(builder,name,center,normal,width,height,lit,materials,projection):
    x,y,z=center
    nx,ny=normal
    def part(label,tangent,forward,vertical,w,d,h,material):
        position=(x-ny*tangent+nx*forward,y+nx*tangent+ny*forward,z+vertical)
        size=(d,w,h) if nx else (w,d,h)
        builder.instance(name+' '+label,position,tuple(v/100 for v in size),material)
    part('stone reveal',0,4,0,width+17,9,height+17,materials['stone'])
    part('glazing',0,9.2,0,width,1.8,height,materials['lit' if lit else 'glass'])
    for side in (-1,1):
        part('side jamb',side*width/2,12,0,5,7,height+8,materials['frame'])
        part('horizontal jamb',0,12,side*height/2,width+8,7,5,materials['frame'])
    part('center mullion',0,13,0,4.5,5,height,materials['frame'])
    part('transom',0,13,-height*.06,width,5,4.5,materials['frame'])
    part('projecting sill',0,13,-height/2-8,width+26,25,10,materials['stone'])
    if lit:
        part('drawn curtain',width*.32,11,2,width*.19,1,height*.91,materials['curtain'])
        if z<260:
            p=V(x+nx*18,y+ny*18,z-9)
            rotation=ue.MathLibrary.make_rot_from_x(V(nx*.72,ny*.72,-.69))
            actor=builder.actor(ue.SpotLight,name+' projected window light',vector(p),rotation)
            actor.tags=list(actor.tags)+[ue.Name('WindowProjection')]
            light=actor.get_component_by_class(ue.SpotLightComponent)
            light.set_editor_properties(dict(mobility=ue.ComponentMobility.MOVABLE,cast_shadows=True,
                intensity=230,attenuation_radius=670,outer_cone_angle=32,inner_cone_angle=31,
                light_function_material=projection,light_function_scale=V(1,1.15,1),
                max_draw_distance=2600,max_distance_fade_range=450,source_radius=4))
            light.set_light_color(ue.LinearColor(1,.76,.44,1))


def build_facades(groups,projection):
    builder=Builder('Brighton/Facades')
    materials={key:ue.load_asset('/Game/Prologue/Street/Materials/M_'+asset) for key,asset in
        (('stone','stone'),('frame','frame'),('lit','lit_window'),('glass','dark_glass'),('curtain','curtain'))}
    for group_index,group in enumerate(groups):
        nx,ny=group['normal']
        count=max(2,int((group['width']-90)//180))
        spacing=min(180,(group['width']-110)/count)
        for floor_index,z in enumerate(range(164,int(group['height'])-100,320)):
            if floor_index==0 and group['storefront']:continue
            for index in range(count):
                tangent=group['center']+(index-(count-1)/2)*spacing
                x,y=(group['front'],tangent) if nx else (tangent,group['front'])
                lit=(index+floor_index+group_index)%4==1
                place_window(builder,group['name'],(x,y,z),(nx,ny),103 if group_index%3 else 117,
                             153 if group_index%3 else 164,lit,materials,projection)
    dima=Builder('Brighton/Dima facade')
    for y,ny,xs in ((-414,-1,(-296,-97,103,298,493,690)),(508,1,(-653,-445,-246,-47,161,350))):
        for floor_index,z in enumerate((492,812)):
            for index,x in enumerate(xs):
                place_window(dima,'Dima third-storey facade',(x,y,z),(0,ny),98,132,
                             (index+floor_index)%4==1,materials,projection)
    for actor in ACTORS.get_all_level_actors():
        if str(actor.get_folder_path())!='Street/02 Apartment facade':continue
        name=actor.get_actor_label()
        if name=='Upper walk-up dwelling':
            low=bounds(actor)[4]
            scale=actor.get_actor_scale3d()
            scale.z=(950-low)/100
            actor.set_actor_scale3d(scale)
            p=actor.get_actor_location()
            p.z=(950+low)/2
            actor.set_actor_location(p,False,True)
        elif name=='Flat roof and parapet':
            p=actor.get_actor_location()
            p.z=969
            actor.set_actor_location(p,False,True)
    return materials


def extend_city(materials):
    builder=Builder('Brighton/Distant city')
    asphalt=ue.load_asset('/Game/Prologue/Street/Materials/M_NeptuneAsphalt')
    pavement=ue.load_asset('/Game/StreetRefinement/Materials/M_WeatheredConcrete')
    walls=[ue.load_asset('/Game/StreetRefinement/Materials/M_FadedOchreRender'),
           facade_material('BlueClapboard',(.54,.79,.91),True),facade_material('CreamClapboard',(1.12,1.03,.81),True)]
    routes=[((-8800,-1425),(-18500,-1425)),((2400,6500),(2400,16200)),((2400,-6500),(2400,-15400))]
    projection=projection_material()
    for road_index,(start,end) in enumerate(routes):
        vertical=start[0]==end[0]
        length=abs(end[1]-start[1]) if vertical else abs(end[0]-start[0])
        center=((start[0]+end[0])/2,(start[1]+end[1])/2)
        builder.box('Road continues past the playable boundary',(*center,-35),(1500,length,14) if vertical else (length,1180,14),asphalt)
        for side in (-1,1):
            edge=(center[0]+side*905,center[1],-15) if vertical else (center[0],center[1]+side*760,-15)
            builder.box('Distant raised sidewalk',edge,(310,length,25) if vertical else (length,320,25),pavement)
            for index in range(7):
                u=(index+.5)/7
                along=start[1]+(end[1]-start[1])*u if vertical else start[0]+(end[0]-start[0])*u
                x,y=(start[0]+side*1550,along) if vertical else (along,start[1]+side*1430)
                height=910+(index%3)*180
                size=(1000,1060,height) if vertical else (1060,1100,height)
                builder.box('Distant Brighton residential block',(x,y,height/2-12),size,walls[(index+road_index)%3])
                normal=(-side,0) if vertical else (0,-side)
                front=x+normal[0]*size[0]/2 if vertical else y+normal[1]*size[1]/2
                for z in range(168,height-100,320):
                    for window in range(5):
                        tangent=along+(window-2)*172
                        position=(front,tangent,z) if vertical else (tangent,front,z)
                        place_window(builder,'Distant regular windows',position,normal,104,150,
                                     (window+index)%5==1,materials,projection)
    for x in range(-9350,-17700,-600):
        builder.box('Distant lane marking',(x,-1425,-27.5),(170,10,.8),make_material(ROOT,'LanePaint',(.65,.61,.43),.88))
    ue.log('BRIGHTON_CITY_EXTENSION_OK 42 background buildings')


def weather_surfaces(collection):
    for actor in ACTORS.get_all_level_actors():
        if actor.actor_has_tag('StreetPortal'):continue
        mesh=actor.get_component_by_class(ue.StaticMeshComponent)
        if not mesh:continue
        for slot in range(mesh.get_num_materials()):
            material=mesh.get_material(slot)
            if not material:continue
            name=material.get_name()
            if name.startswith('M_Wet_'):continue
            if name in ('M_asphalt','M_NeptuneAsphalt','M_asphalt_repair','M_concrete','M_pavement','M_WeatheredConcrete'):
                mesh.set_material(slot,weather_material(material,collection))


def capture_exterior():
    records=[]
    for actor in ACTORS.get_all_level_actors():
        folder=str(actor.get_folder_path())
        if actor.actor_has_tag('CityLifeDressing'):continue
        include=folder.startswith(('Street/','Brighton/'))
        if not include or folder.startswith(('Street/02 Apartment facade','Street/06 Sky','Street/07 Location','Street/10 Traffic','Brighton/Dima facade')):continue
        if actor.get_editor_property('hidden'):continue
        if actor.actor_has_tag('WindowProjection'):
            p=actor.get_actor_location()
            r=actor.get_actor_rotation()
            records.append(dict(label=actor.get_actor_label(),light=True,position=vector(p),rotation=(r.pitch,r.yaw,r.roll)))
            continue
        component=actor.get_component_by_class(ue.StaticMeshComponent)
        if not component or not component.static_mesh:continue
        p=actor.get_actor_location()
        r=actor.get_actor_rotation()
        s=actor.get_actor_scale3d()
        record=dict(label=actor.get_actor_label(),mesh=component.static_mesh.get_path_name(),position=vector(p),
                    rotation=(r.pitch,r.yaw,r.roll),scale=vector(s),
                    materials=[component.get_material(i).get_path_name() if component.get_material(i) else None
                               for i in range(component.get_num_materials())])
        if actor.actor_has_tag('BrightonEnlargedFactory'):
            record['enlarged_factory']=True
        if isinstance(component,ue.InstancedStaticMeshComponent):
            record['instances']=[]
            for index in range(component.get_instance_count()):
                transform=component.get_instance_transform(index,True)
                q=transform.rotation
                record['instances'].append(dict(p=vector(transform.translation),s=vector(transform.scale3d),q=(q.x,q.y,q.z,q.w)))
        records.append(record)
    return records


def apartment_city(records):
    builder=Builder('Brighton/Third floor city view')
    projection=projection_material()
    shift=V(0,-48,-640)
    # Apartment gameplay stays in its authored local frame. The exterior is shared city geometry.
    for record in records:
        p=V(*record['position'])+shift
        rotation=ue.Rotator(pitch=record['rotation'][0],yaw=record['rotation'][1],roll=record['rotation'][2])
        if record.get('light'):
            actor=builder.actor(ue.SpotLight,'Third-floor view '+record['label'],vector(p),rotation)
            actor.tags=list(actor.tags)+[ue.Name('WindowProjection')]
            light=actor.get_component_by_class(ue.SpotLightComponent)
            light.set_editor_properties(dict(mobility=ue.ComponentMobility.MOVABLE,cast_shadows=True,
                intensity=230,attenuation_radius=670,outer_cone_angle=32,inner_cone_angle=31,
                light_function_material=projection,light_function_scale=V(1,1.15,1),
                max_draw_distance=2600,max_distance_fade_range=450,source_radius=4))
            light.set_light_color(ue.LinearColor(1,.76,.44,1))
            continue
        cls=ue.StreetMeshInstances if 'instances' in record else ue.StaticMeshActor
        actor=builder.actor(cls,'Third-floor view '+record['label'],vector(p),rotation)
        if record.get('enlarged_factory'):
            actor.tags=[*actor.tags,ue.Name('BrightonEnlargedFactory')]
        actor.set_actor_scale3d(V(*record['scale']))
        mesh=actor.get_component_by_class(ue.StaticMeshComponent)
        mesh.set_static_mesh(ue.load_asset(record['mesh']))
        for index,path in enumerate(record['materials']):
            if path:mesh.set_material(index,ue.load_asset(path))
        mesh.set_collision_profile_name(ue.Name('NoCollision'))
        if 'instances' in record:
            actor.set_actor_location(V(),False,True)
            actor.set_actor_rotation(ue.Rotator(),False)
            actor.set_actor_scale3d(V(1,1,1))
            for instance in record['instances']:
                q=instance['q']
                orientation=ue.MathLibrary.quat_rotator(ue.Quat(x=q[0],y=q[1],z=q[2],w=q[3]))
                transform=ue.Transform(location=V(*instance['p'])+shift,rotation=orientation,scale=V(*instance['s']))
                mesh.add_instance(transform,True)
            if record.get('enlarged_factory'):
                mesh.set_cull_distances(29000,42000)
            else:
                mesh.set_cull_distances(19000,26000)
    facade=ue.load_asset('/Game/StreetRefinement/Materials/M_AgedRedBrick')
    builder.box('Two storeys below Dima north windows',(-190,466,-327),(1175,18,626),facade)
    builder.box('Two storeys below Dima west windows',(-782,0,-327),(18,880,626),facade)
    builder.box('Two storeys below Dima main west window',(-402,-285,-327),(18,330,626),facade)
    builder.box('Two storeys below Dima kitchen windows',(-558,20,-327),(370,18,626),facade)
    open_window_curtains(builder)
    ue.log('BRIGHTON_THIRD_FLOOR_OK elevation_cm=640 exterior_groups='+str(len(records)))


def open_window_curtains(builder):
    # Keep the user's curtain models, drawing their cloth to the sides of the openings.
    by_name={a.get_actor_label():a for a in ACTORS.get_all_level_actors()}
    def compact(actor,axis,center,width):
        p,e=actor.get_actor_bounds(False)
        extent=e.x if axis==0 else e.y
        scale=actor.get_actor_scale3d()
        scale.x*=width/(2*extent)
        actor.set_actor_scale3d(scale)
        p,_=actor.get_actor_bounds(False)
        at=actor.get_actor_location()
        if axis==0:at.x+=center-p.x
        else:at.y+=center-p.y
        actor.set_actor_location(at,False,True)
    north=by_name.get('Curtains_Double2')
    if north:
        compact(north,0,-125,70)
        mate=builder.actor(ue.StaticMeshActor,'North curtain drawn to the right')
        mate.set_actor_transform(north.get_actor_transform(),False,True)
        original=north.get_component_by_class(ue.StaticMeshComponent)
        mesh=mate.get_component_by_class(ue.StaticMeshComponent)
        mesh.set_static_mesh(original.static_mesh)
        for slot in range(original.get_num_materials()):mesh.set_material(slot,original.get_material(slot))
        mesh.set_collision_profile_name(ue.Name('NoCollision'))
        compact(mate,0,85,70)
        builder.box('Continuous north curtain rod',(-20,426,250),(257,2.5,2.5),original.get_material(0))
    for name,center in (('Curtains_Double',-351),('Curtains_Single',-221)):
        if name in by_name:compact(by_name[name],1,center,44)
    if 'Curtains_Double' in by_name:
        metal=by_name['Curtains_Double'].get_component_by_class(ue.StaticMeshComponent).get_material(0)
        builder.box('Continuous west curtain rod',(-380,-286,250),(2.5,197,2.5),metal)
