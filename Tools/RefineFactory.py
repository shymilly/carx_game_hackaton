"""Bounded 2.5D industrial set: instanced solids, tiled masonry, no lights/collision/particles."""
import math,hashlib
from random import Random
from pathlib import Path
import unreal as ue

FOLDER='Street/08 Industrial horizon/Refined works'
ROOT='/Game/Prologue/Street/RefinedFactory'
def apply_factory():
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
    lib=ue.MaterialEditingLibrary
    from ApartmentScene import make_material
    from StreetMaterials import custom_input
    smoke=[a for a in actors.get_all_level_actors() if a.get_actor_label().startswith('Animated factory stack plume')]
    def signature():
        result=[]
        for a in smoke:
            p,r,s=a.get_actor_location(),a.get_actor_rotation(),a.get_actor_scale3d()
            result.append((a.get_actor_label(),tuple(round(v,6) for v in (p.x,p.y,p.z,r.pitch,r.yaw,r.roll,s.x,s.y,s.z)),a.get_component_by_class(ue.StaticMeshComponent).get_material(0).get_path_name()))
        return result
    before=signature()
    old=[a for a in actors.get_all_level_actors() if str(a.get_folder_path())==FOLDER]
    if old: assert actors.destroy_actors(old)
    # Replace both painted factory rectangles with actual depth. Smoke is independent and untouched.
    for a in actors.get_all_level_actors():
        if a.get_actor_label() in ('Aegis works painted facade','Aegis skyline behind the works'):
            a.set_actor_hidden_in_game(True)
            a.get_component_by_class(ue.StaticMeshComponent).set_visibility(False,True)
    collection=ue.load_asset('/Game/Prologue/Street/Materials/MPC_StreetLighting')
    palette={
        'brick':((1.18,.97,.84),'T_brick_Color',200),
        'ochre':((1.08,1.04,.94),'T_ochre_brick_Color',200),
        'soot':((.48,.49,.50),'T_brick_Color',200),
        'concrete':((.86,.89,.88),'T_concrete_Color',400),
        'steel':((.16,.19,.20),None,200),
        'rust':((.31,.17,.105),None,200),
        'glass':((.115,.21,.265),None,200),
        'glass_warm':((.46,.38,.22),None,200),
        'black':((.027,.033,.036),None,200),
    }
    mats={}
    for name,(tint,tex,span) in palette.items():
        m=make_material(ROOT,'Factory_'+name,tint,.9)
        if not lib.get_material_property_input_node(m,ue.MaterialProperty.MP_EMISSIVE_COLOR):
            m.set_editor_property('shading_model',ue.MaterialShadingModel.MSM_UNLIT)
            def n(cls,x,y,**kw):
                obj=lib.create_material_expression(m,cls,x,y)
                obj.set_editor_properties(kw)
                return obj
            p=n(ue.MaterialExpressionWorldPosition,-850,0)
            normal=n(ue.MaterialExpressionPixelNormalWS,-850,200)
            uv=n(ue.MaterialExpressionCustom,-600,0,inputs=[custom_input('P'),custom_input('N')],
                output_type=ue.CustomMaterialOutputType.CMOT_FLOAT2,code=f'return float2(abs(N.x)>abs(N.y)?P.y:P.x,-P.z)/{float(span)};')
            lib.connect_material_expressions(p,'',uv,'P');lib.connect_material_expressions(normal,'',uv,'N')
            if tex:
                color=n(ue.MaterialExpressionTextureSample,-380,0,texture=ue.load_asset('/Game/Prologue/Street/Textures/'+tex))
                lib.connect_material_expressions(uv,'',color,'Coordinates')
            else: color=n(ue.MaterialExpressionConstant3Vector,-380,0,constant=ue.LinearColor(1,1,1,1))
            tintnode=n(ue.MaterialExpressionConstant3Vector,-380,300,constant=ue.LinearColor(*tint,1))
            exposure=n(ue.MaterialExpressionCollectionParameter,-380,450,collection=collection,parameter_name=ue.Name('FactoryExposure'))
            shade=n(ue.MaterialExpressionCustom,0,0,inputs=[custom_input(s) for s in ('C','Tint','N','Light')],
                output_type=ue.CustomMaterialOutputType.CMOT_FLOAT3,
                code='float shade=.38+.62*saturate(dot(normalize(N),normalize(float3(-.8,-.5,.8)))); return C*Tint*shade*Light;')
            for node,pin in ((color,'C'),(tintnode,'Tint'),(normal,'N'),(exposure,'Light')):lib.connect_material_expressions(node,'',shade,pin)
            lib.connect_material_property(shade,'',ue.MaterialProperty.MP_EMISSIVE_COLOR)
            lib.recompile_material(m)
            assert assets.save_loaded_asset(m,False)
        mats[name]=m
        # Guard normals on the cheap unlit path and explicitly feed RGB (not RGBA).
        for expr in ue.ObjectIterator(ue.MaterialExpressionCustom):
            if expr.get_outer()!=m or 'float shade=' not in expr.get_editor_property('code'):continue
            expr.set_editor_property('code','float3 normal=N+float3(.0001,.0001,.0001); float shade=.68+.32*saturate(dot(normalize(normal),normalize(float3(-.8,-.5,.8)))); return C.rgb*Tint.rgb*shade*1.8*max(Light,.4);')
            for sample in ue.ObjectIterator(ue.MaterialExpressionTextureSample):
                if sample.get_outer()==m:lib.connect_material_expressions(sample,'RGB',expr,'C')
            m.set_editor_property('used_with_instanced_static_meshes',True)
            lib.recompile_material(m);assert assets.save_loaded_asset(m,False)
    batches={};counts={}
    def item(material,pos,size,shape='Cube',roll=0):
        key=(material,shape)
        if key not in batches:
            a=actors.spawn_actor_from_class(ue.StreetMeshInstances,ue.Vector())
            a.set_actor_label('Factory depth '+material+' '+shape)
            a.set_folder_path(ue.Name(FOLDER))
            c=a.get_editor_property('instances')
            c.set_static_mesh(ue.load_asset('/Engine/BasicShapes/'+shape))
            c.set_material(0,mats[material]);c.set_collision_profile_name(ue.Name('NoCollision'))
            c.set_editor_properties(dict(cast_shadow=False,affect_distance_field_lighting=False))
            c.set_cull_distances(18000,24000)
            batches[key]=c;counts[key]=0
        batches[key].add_instance(ue.Transform(location=ue.Vector(*pos),rotation=ue.Rotator(roll=roll),scale=ue.Vector(*(s/100 for s in size))),True)
        counts[key]+=1
    rng=Random(1994)
    # South/north sidewalls, real roof planes, concrete bays and recessed multi-pane windows.
    for index,(lo,hi,top,brick,depth) in enumerate(((-4870,-3140,1500,'ochre',760),(-3110,180,1740,'brick',1080),(330,1940,1520,'soot',820))):
        middle=(lo+hi)/2;width=hi-lo
        item(brick,(5750,middle,top/2),(depth,width,top))
        front=5750-depth/2-3
        item('concrete',(5750,middle,top+8),(depth+32,width+55,28))
        item('soot',(front-3,middle,55),(18,width,110))
        for y in range(round(lo+80),round(hi),340):
            item('concrete',(front-15,y,top/2),(36,35,top))
        for row,z in enumerate((270,570,900,1230)):
            if z+100>top: continue
            for j,y in enumerate(range(round(lo+200),round(hi-60),340)):
                item('black',(front-12,y,z),(18,246,184))
                item('glass_warm' if (j+row+index)%7==0 else 'glass',(front-24,y,z+4),(8,221,155))
                for dy in (-112,0,112):item('steel',(front-31,y+dy,z+5),(9,8,166))
                for dz in (-78,0,78):item('steel',(front-31,y,z+dz),(9,229,8))
                item('concrete',(front-31,y,z-91),(58,264,14))
                # Water stains below selected sills form readable broad streaks, not tiny noise.
                if j%3==1:item('soot',(front-8,y-58,z-150),(8,49,91))
        item('rust',(front-21,middle,135),(38,245,270))
        for dy in (-140,140):item('concrete',(front-34,middle+dy,150),(55,30,300))
        item('steel',(front-38,middle,290),(58,315,25))
        # Raised saw-tooth northlights provide a broken industrial roof silhouette and depth.
        for y in range(round(lo+280),round(hi-180),680):
            item('steel',(5750,y,top+64),(depth*.84,610,20),roll=12)
            item('glass',(front+80,y-270,top+76),(12,18,135))
            item('concrete',(front+58,y-271,top+148),(24,42,14))
    # Keep the exact original stack-top UV/world positions, so the unchanged plumes still join them.
    for u,v,radius in ((300,69,227.5),(458,112,170.6),(717,93,199.1)):
        y=-1425+(u/1024-.5)*7280
        top=-55+(1-v/512)*2940
        base=380;span=top-base
        for section in range(4):
            h=span/4;r=radius*(1+.35*(3-section)/3)
            item('brick',(5595,y,base+h*(section+.5)),(2*r,2*r,h+2),'Cylinder')
        for z in range(600,round(top),260):item('steel',(5595,y,z),(radius*2.5,radius*2.5,13),'Cylinder')
        item('concrete',(5595,y,top-14),(radius*2.13,radius*2.13,25),'Cylinder')
        item('black',(5595,y,top+.8),(radius*1.76,radius*1.76,3),'Cylinder')
        for z in range(600,round(top-30),120):
            item('rust',(5595-radius-16,y,z),(12,80,7))
        for dy in (-42,42):item('steel',(5595-radius-16,y+dy,(600+top)/2),(10,10,top-600))
    # A separate rear utility block / duct network adds parallax at grazing street viewpoints.
    item('concrete',(6250,1440,670),(620,980,1340))
    for z in (320,880):
        item('rust',(5340,-1800,z),(70,2120,70),'Cube')
        for y in range(-2740,-700,480):item('steel',(5380,y,z-44),(110,18,45))
    assert before==signature(),'Smoke actor configuration changed'
    triangles=sum(n*(12 if shape=='Cube' else 200) for (mat,shape),n in counts.items())
    report=dict(batches=len(batches),instances=sum(counts.values()),estimated_triangles=triangles,new_lights=0,new_collision_shapes=0,smoke_unchanged=True)
    ue.log('FACTORY_REFINED '+str(report))
    return report
