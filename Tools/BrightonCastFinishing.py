"""Fit the bar cinematic prop and add rig-mounted details to the precinct uniforms."""
from math import cos, pi, sin, sqrt

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, LEVELS, LIB, P, PROJECT, V, connect, constant, media, node, output, save
from CityLifeCharacters import apply_profile
from RepairBrightonStoryScenes import Detail, require, tagged


DRIFTER = '/Game/Prologue/Characters/HollowNightDrifter/DA_DimaDrifter'
UNIFORMS = '/Game/Prologue/Characters/Precinct'
UNIFORM_TAG = ue.Name('PrecinctUniformDetail')
KEEP = ue.AttachmentRule.KEEP_WORLD
MATH = ue.MathLibrary


def scene_map(name):
    assert ue.EditorLoadingAndSavingUtils.load_map('/Game/Locations/'+name),name
    return ACTORS.get_all_level_actors()


def rig_pose(clip, time):
    pose = ue.AnimPoseExtensions.get_anim_pose_at_time(clip,time,ue.AnimPoseEvaluationOptions())
    def sample(bone):
        return ue.AnimPoseExtensions.get_bone_pose(pose,bone,ue.AnimPoseSpaces.WORLD)
    return sample


def mount(prop,body,socket,relative):
    prop.get_component_by_class(ue.SceneComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    assert body.does_socket_exist(socket),socket
    assert prop.attach_to_component(body,socket,KEEP,KEEP,KEEP,False),prop
    prop.set_actor_relative_transform(relative,False,True)


def bar():
    profile = require(DRIFTER)
    mesh = profile.get_editor_property('mesh')
    motions = profile.get_editor_property('motions')
    idle, shot = (motions[ue.Name(name)] for name in ('Idle','Shot'))
    assert ue.CityCharacterAuthoring.author_bar_pistol_pose(mesh,idle,shot)
    save(mesh)
    save(shot)

    actors = scene_map('L_LighthouseBar')
    dima = tagged(actors,'BarDima')
    prop = tagged(actors,'BarShotProp')
    body = dima.get_editor_property('character_mesh')
    socket = ue.Name('BarPistolGrip')
    hand = rig_pose(shot,.47)('Hand_R')
    socket_local = body.get_socket_transform(socket,ue.RelativeTransformSpace.RTS_PARENT_BONE_SPACE)
    grip = MATH.compose_transforms(socket_local,MATH.compose_transforms(hand,body.get_world_transform()))
    center = V(-5.7,0,7*.78)
    scale = grip.scale3d
    prop.get_component_by_class(ue.StaticMeshComponent).set_absolute(False,False,False)
    mount(prop,body,socket,ue.Transform(location=V(-center.x/scale.x,-center.y/scale.y,-center.z/scale.z),
                                        scale=V(1/scale.x,1/scale.y,.78/scale.z)))
    axis = grip.rotation.rotate_vector(V(1,0,0))
    assert V.dot(axis,dima.get_actor_forward_vector())>.95 and abs(axis.z)<.08,axis
    assert prop.get_attach_parent_socket_name()==socket
    body.override_animation_data(shot,False,False,.47,1.)
    assert LEVELS.save_current_level()
    ue.log(f'REPAIR_BAR_GRIP_OK prop local offset and dedicated palm socket; aim direction={axis}')


def shield_mesh():
    # Symmetric outline with a tapered point and a recessed enamel face.
    name = 'SM_Precinct_Shield'
    work = PROJECT/'Saved/StoryDetail'
    work.mkdir(parents=True,exist_ok=True)
    file = work/(name+'.obj')
    rim = [(-2.5,2.8),(0,3.5),(2.5,2.8),(2.2,-.6),(1.1,-2.1),(0,-3),(-1.1,-2.1),(-2.2,-.6)]
    lines = ['o '+name]
    for x,scale in ((-.35,1),(.16,1),(.68,.85)):
        for y,z in rim:
            lines.extend((f'v {x} {y*scale:.4f} {z*scale:.4f}',f'vt {.5+y*scale/6:.4f} {.5+z*scale/8:.4f}'))
    def face(*indices):
        lines.append('f '+' '.join(f'{i}/{i}' for i in indices))
    for layer in range(2):
        for i in range(8):
            a,b = 1+8*layer+i,1+8*layer+(i+1)%8
            face(b,a,a+8,b+8)
    face(*range(1,9))
    face(*range(24,16,-1))
    file.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return media(file,UNIFORMS+'/Meshes',replace_existing=True)


def select_station_uniform_base(actor,variant,height):
    profile = actor.get_editor_property('character_profile')
    current = profile.get_editor_property('mesh')
    mesh = require('/Game/Citizens_Pack/Meshes/SK_Citizens_Pack_'+variant)
    old_slots = current.get_editor_property('materials')
    palette = dict(zip((str(slot.get_editor_property('material_slot_name')) for slot in old_slots),
                       profile.get_editor_property('materials')))
    materials = [palette.get(str(slot.get_editor_property('material_slot_name')),
                             slot.get_editor_property('material_interface')) for slot in mesh.get_editor_property('materials')]
    bounds = mesh.get_bounds()
    scale = height/(2*bounds.box_extent.z)
    profile.set_editor_properties(dict(mesh=mesh,materials=materials,model_scale=scale,
        feet_offset=scale*(bounds.box_extent.z-bounds.origin.z)))
    body = actor.get_editor_property('character_mesh')
    for index in range(body.get_num_materials()):
        body.set_material(index,None)
    apply_profile(actor,profile)
    save(profile)


def mask_civilian_headwear(profile,role):
    mesh = profile.get_editor_property('mesh')
    idle = profile.get_editor_property('motions')[ue.Name('Idle')]
    head = ue.CityCharacterAuthoring.pose_bone_position(mesh,idle,'head',0)
    for surface in profile.get_editor_property('materials'):
        if not surface.get_name().startswith(('M_'+role+'_Cloth','M_'+role+'_Set')):
            continue
        if not LIB.get_material_property_input_node(surface,P.MP_OPACITY_MASK):
            surface.set_editor_property('blend_mode',ue.BlendMode.BLEND_MASKED)
            position = node(surface,ue.MaterialExpressionPreSkinnedPosition)
            height = node(surface,ue.MaterialExpressionComponentMask,b=True)
            height_pixel = node(surface,ue.MaterialExpressionVertexInterpolator)
            trim = node(surface,ue.MaterialExpressionIf)
            connect(position,height)
            connect(height,height_pixel)
            connect(height_pixel,trim,'A')
            connect(constant(surface,head.z-3),trim,'B')
            connect(constant(surface,1),trim,'A < B')
            connect(constant(surface,0),trim,'A > B')
            output(trim,surface,P.MP_OPACITY_MASK)
            LIB.recompile_material(surface)
            save(surface)
    ue.log(f'REPAIR_PRECINCT_HEADWEAR {role} local head height {head.z:.1f} cm')


def service_cap_mesh():
    name = 'SM_Precinct_ServiceCap'
    file = PROJECT/'Saved/StoryDetail'/(name+'.obj')
    lines = ['o '+name]
    count = 24
    for z,x,y in ((0,9.4,8.7),(2.0,9.7,9.1),(4.0,11.7,10.9),(7.9,12.1,11.75),(9.0,10.7,10.3)):
        for i in range(count):
            angle=2*pi*i/count
            cx,cy=cos(angle),sin(angle)
            lines.extend((f'v {cx*x:.5f} {cy*y:.5f} {z+max(0,cx)*1.15:.5f}',
                          f'vt {(cx+1)*.5:.5f} {(cy+1)*.5:.5f}'))
    def face(indices):
        lines.append('f '+' '.join(f'{index}/{index}' for index in indices))
    for layer in range(4):
        lines.append('usemtl Band' if layer==0 else 'usemtl Crown')
        for i in range(count):
            a,b = 1+layer*count+i,1+layer*count+(i+1)%count
            face((a,b,b+count,a+count))
    face(tuple(range(4*count+1,5*count+1)))
    face(tuple(range(count,0,-1)))
    lines.append('usemtl Peak')
    for layer in (0,1):
        for rim in (0,1):
            for i in range(11):
                theta = (i-5)*pi/20
                x = cos(theta)*(15.9 if rim else 9.2)
                y = sin(theta)*(13.4 if rim else 9.2)
                z = (-1.65 if rim else .55)-layer*.36
                lines.extend((f'v {x:.5f} {y:.5f} {z:.5f}',f'vt {i/10:.3f} {rim}'))
    root=5*count+1
    for i in range(10):
        a=root+i
        face((a,a+11,a+12,a+1))
        face((a+22,a+23,a+34,a+33))
        face((a+11,a+33,a+34,a+12))
    file.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return media(file,UNIFORMS+'/Meshes',replace_existing=True)


def cloth_detail(name,patches,curvature=0):
    file = PROJECT/'Saved/StoryDetail'/(name+'.obj')
    lines = ['o '+name]
    index = 1
    for material,polygon in patches:
        lines.append('usemtl '+material)
        for x,y,z in polygon:
            lines.extend((f'v {x:.5f} {y:.5f} {z:.5f}',f'vt {.5+y/12:.5f} {.5+z/60:.5f}'))
            normal_y = curvature*y
            normal_z = .023
            length = sqrt(1+normal_y**2+normal_z**2)
            lines.append(f'vn {1/length:.6f} {normal_y/length:.6f} {normal_z/length:.6f}')
        lines.append('f '+' '.join(f'{i}/{i}/{i}' for i in range(index,index+len(polygon))))
        index += len(polygon)
    file.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return media(file,UNIFORMS+'/Meshes',replace_existing=True)


def krill_tailoring():
    patches = []

    def cloth_point(y,z,offset=.0):
        return (.66-.022*y*y-.023*z+offset,y,z)

    def pocket_panel(outline,offset):
        edge = [cloth_point(y,z,offset-.11) for y,z in outline]
        inset = [cloth_point(y*.94,z*.94,offset) for y,z in outline]
        midpoint = cloth_point(0,sum(z for _,z in outline)/len(outline),offset+.06)
        for i in range(len(edge)):
            j = (i+1)%len(edge)
            patches.append(('seam',(edge[i],edge[j],inset[j],inset[i])))
            patches.append(('fabric',(inset[i],inset[j],midpoint)))

    pocket_panel(((-4.95,-3.72),(-4.19,-4.64),(0,-5.02),(4.21,-4.64),
                  (4.96,-3.61),(4.93,4.52),(-4.90,4.56)),0)
    pocket_panel(((-4.8,2.45),(-3.9,1.95),(0,1.04),(4.24,2.05),(5.1,2.55),(5.0,4.88),(-4.99,4.95)),.16)
    pocket = cloth_detail('SM_Krill_ShapedPocket',patches,.044)

    # The knot widens under the collar. The folded blade tapers to a pointed tip.
    rows = ((2.10,1.97,.38),(.75,1.69,.71),(-2.3,1.11,.65),(-5.0,1.25,.32),
            (-12.5,1.75,.19),(-20.7,2.38,.08),(-23,2.41,-.09),(-25.6,.035,-.33))
    crease = [((x,y-width,z),(x+.21,y,z),(x,y+width,z)) for (z,width,x),y in
              zip(rows,(0,0,0,.02,.09,.19,.27,.26))]
    patches = []
    for upper,lower in zip(crease,crease[1:]):
        patches.extend((('silk',(lower[0],lower[1],upper[1],upper[0])),
                        ('fold',(lower[1],lower[2],upper[2],upper[1]))))
    tie = cloth_detail('SM_Krill_FoldedTie',patches)
    return pocket,tie


def uniform(scene,actor,role,shield,cap,surfaces):
    captain = role=='Krill'
    body = actor.get_editor_property('character_mesh')
    profile = actor.get_editor_property('character_profile')
    clips = profile.get_editor_property('motions')
    clip = clips[ue.Name('SeatedIdle' if captain else 'Idle')]
    pose_time = max(.2,actor.get_editor_property('animation_phase'))
    sample = rig_pose(clip,pose_time)

    def pose(bone):
        return MATH.compose_transforms(sample(bone),body.get_world_transform())

    left,right = (pose(bone).translation for bone in ('upperarm_l','upperarm_r'))
    span = V(right.x-left.x,right.y-left.y,0)
    side = span/span.length()
    front = V.cross(side,V(0,0,1))
    assert V.dot(front,actor.get_actor_forward_vector())>.75,(role,front)
    yaw = MATH.make_rot_from_x(front).yaw
    torso = pose('spine_03').translation
    chest = torso+front*(17.8 if captain else 15.6)+V(0,0,6.3)

    def fit(prop,bone='spine_03'):
        prop.tags = [tag for tag in prop.tags if str(tag)!='BrightonStoryDetail']+[UNIFORM_TAG]
        relative = MATH.make_relative_transform(prop.get_actor_transform(),pose(bone))
        mount(prop,body,ue.Name(bone),relative)
        return prop

    def piece(name,point,dimensions,material,bone='spine_03',pitch=0,roll=0):
        return fit(scene.mesh(role+' '+name,point.to_tuple(),dimensions,surfaces[material],
                              yaw=yaw,pitch=pitch,roll=roll),bone)

    def inscription(text,point,size,color):
        return fit(scene.label(text,point.to_tuple(),yaw,size,color))

    def cloth(name,model,point,slots,angle=0):
        garment = scene.spawn(ue.StaticMeshActor,role+' '+name,point.to_tuple(),yaw+angle)
        component = garment.get_component_by_class(ue.StaticMeshComponent)
        component.set_static_mesh(model)
        component.set_collision_profile_name('NoCollision')
        component.set_cast_shadow(False)
        for index,slot in enumerate(model.get_editor_property('static_materials')):
            label = str(slot.get_editor_property('imported_material_slot_name')).casefold()
            component.set_material(index,next(surfaces[key] for suffix,key in slots if label.endswith(suffix)))
        return fit(garment)

    cap_line = pose('head').translation + front*.3 + V(0,0,12)
    headwear = scene.spawn(ue.StaticMeshActor,role+' police service cap',cap_line.to_tuple(),yaw)
    cap_mesh = headwear.get_component_by_class(ue.StaticMeshComponent)
    cap_mesh.set_static_mesh(cap)
    cap_mesh.set_collision_profile_name('NoCollision')
    cap_mesh.set_cast_shadow(False)
    for index,slot in enumerate(cap.get_editor_property('static_materials')):
        material = str(slot.get_editor_property('imported_material_slot_name')).casefold()
        cap_mesh.set_material(index,surfaces['radio' if material.endswith(('peak','band')) else 'flap'])
    fit(headwear,'head')
    cap_mark = scene.spawn(ue.StaticMeshActor,role+' cap badge',(cap_line+front*11.9+V(0,0,6)).to_tuple(),yaw)
    cap_mark.set_actor_scale3d(V(.86,.78,.72))
    cap_badge = cap_mark.get_component_by_class(ue.StaticMeshComponent)
    cap_badge.set_static_mesh(shield)
    cap_badge.set_material(0,surfaces['hardware'])
    cap_badge.set_collision_profile_name('NoCollision')
    cap_badge.set_cast_shadow(False)
    fit(cap_mark,'head')

    if captain:
        pocket_mesh,tie_mesh = krill_tailoring()
    for side_sign in (-1,1):
        pocket = chest+side*(side_sign*10.5)-front*1.7-V(0,0,7.5)
        if captain:
            cloth('stitched breast pocket',pocket_mesh,pocket,(('fabric','pocket'),('seam','seam')),side_sign*7)
            piece('covered pocket button',pocket+front*.89+V(0,0,2.8),(.26,.68,.68),'seam')
        else:
            piece('tailored breast pocket',pocket,(1.8,11.0,10.8),'cloth')
            piece('pointed pocket flap',pocket+front*1.2+V(0,0,4.4),(1.6,11.8,3.7),'flap')
            piece('pocket button',pocket+front*2.1+V(0,0,3.5),(.6,1.0,1.0),'hardware')
    badge_center = chest-side*10.5+V(0,0,1.5)
    badge = scene.spawn(ue.StaticMeshActor,role+' shield badge',badge_center.to_tuple(),yaw)
    badge_component = badge.get_component_by_class(ue.StaticMeshComponent)
    badge_component.set_static_mesh(shield)
    badge_component.set_material(0,surfaces['hardware'])
    badge_component.set_collision_profile_name('NoCollision')
    badge_component.set_cast_shadow(False)
    fit(badge)
    inscription('POLICE',badge_center+front*.75+V(0,0,.7),1.02,(43,53,65))
    nameplate = chest+side*10.5-V(0,0,.3)
    piece('service nameplate',nameplate,(.8,8.7,2.2),'hardware')
    inscription('CAPT. KRILL' if captain else 'POLICE',nameplate+front*.44+V(0,0,.7),1.12,(24,34,49))

    for sign,shoulder,bone in ((-1,left,'clavicle_l'),(1,right,'clavicle_r')):
        top = shoulder-side*(sign*4.7)+V(0,0,5.8)
        piece('uniform shoulder strap',top,(7.5,11.5,1.7),'flap',bone,roll=sign*-10)
        if captain:
            for offset in (-1.2,1.2):
                piece('captain rank bar',top+side*offset+V(0,0,.93),(3.1,1.3,.51),'hardware',bone)
    if captain:
        for sign in (-1,1):
            at = chest+side*(sign*4.4)+V(0,0,10)
            piece('captain collar point',at,(.9,3.8,5.5),'collar',roll=sign*24)
        cloth('folded service tie',tie_mesh,chest+front*.52+V(0,0,8.2),(('silk','tie'),('fold','tie_fold')))
    else:
        radio = chest+side*17-V(0,0,10)-front*3
        piece('portable dispatch radio',radio,(4.7,5.3,11),'radio',roll=-8)
        piece('dispatch radio antenna',radio+V(0,1.4,8.5),(1.0,.95,6),'radio')
        waist = pose('pelvis').translation+front*11.8+V(0,0,9.3)
        piece('duty belt front',waist,(2.0,28,5.6),'radio','pelvis')
        piece('duty belt buckle',waist+front*1.25,(1.2,6.8,4.5),'hardware','pelvis')
    body.override_animation_data(clip,False,False,pose_time,1.)
    body.set_update_animation_in_editor(True)
    ue.log(f'REPAIR_PRECINCT_UNIFORM_OK {role} shield, pocket flaps and service distinctions')


def precinct(roles=('Krill','DutyOfficer')):
    actors = scene_map('L_PolicePrecinct')
    officers = {role:tagged(actors,role) for role in roles}
    previous = [actor for actor in actors if actor.actor_has_tag(UNIFORM_TAG) and
                actor.get_attach_parent_actor() in officers.values()]
    if previous:
        assert ACTORS.destroy_actors(previous)
    scene = Detail('Precinct uniforms')
    shield = ue.load_asset(UNIFORMS+'/Meshes/SM_Precinct_Shield') or shield_mesh()
    cap = ue.load_asset(UNIFORMS+'/Meshes/SM_Precinct_ServiceCap') or service_cap_mesh()
    for role,variant,height,metal in (('Krill','Karl_A',185,(.57,.42,.18)),
                                     ('DutyOfficer','Tony_A',181,(.47,.51,.54))):
        if role not in officers:
            continue
        materials = {'cloth':(.021,.029,.046),'flap':(.018,.026,.044),'collar':(.52,.53,.49),
                     'hardware':metal,'radio':(.016,.022,.024)}
        if role=='Krill':
            materials.update(pocket=(.0185,.021,.028),seam=(.0145,.0165,.022),
                             tie=(.012,.016,.023),tie_fold=(.010,.014,.021),collar=(.38,.40,.38))
        surfaces = {}
        for key,tint in materials.items():
            surface = make_material(UNIFORMS+'/Materials',f'M_{role}_Uniform_{key}',tint,
                                    {'hardware':.36,'tie':.57,'tie_fold':.60}.get(key,.82))
            node = LIB.get_material_property_input_node(surface,P.MP_BASE_COLOR)
            node.set_editor_property('constant',ue.LinearColor(*tint,1))
            LIB.recompile_material(surface)
            save(surface)
            surfaces[key] = surface
        officer = officers[role]
        select_station_uniform_base(officer,variant,height)
        mask_civilian_headwear(officer.get_editor_property('character_profile'),role)
        uniform(scene,officer,role,shield,cap,surfaces)
    assert LEVELS.save_current_level()
