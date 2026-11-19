"""Bounded 2.5D industrial set: instanced solids, tiled masonry, no lights/collision/particles."""
from random import Random
import unreal as ue

FOLDER='Street/08 Industrial horizon/Refined works'
def apply_factory():
    actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
    smoke=[a for a in actors.get_all_level_actors() if a.get_actor_label().startswith('Animated factory stack plume')]
    old=[a for a in actors.get_all_level_actors() if str(a.get_folder_path())==FOLDER]
    if old: assert actors.destroy_actors(old)
    # Replace the two old painted rectangles with instanced architecture.
    for a in actors.get_all_level_actors():
        if a.get_actor_label() in ('Aegis works painted facade','Aegis skyline behind the works'):
            a.set_actor_hidden_in_game(True)
            a.get_component_by_class(ue.StaticMeshComponent).set_visibility(False,True)
    from BrightonStreetDetails import enlarge_factory, factory_finishes
    mats=factory_finishes()
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
    enlarge_factory(actors.get_all_level_actors(), (0,0,0))
    triangles=sum(n*(12 if shape=='Cube' else 200) for (mat,shape),n in counts.items())
    report=dict(batches=len(batches),instances=sum(counts.values()),estimated_triangles=triangles,new_lights=0,new_collision_shapes=0,aligned_plumes=len(smoke))
    ue.log('FACTORY_REFINED '+str(report))
    return report
