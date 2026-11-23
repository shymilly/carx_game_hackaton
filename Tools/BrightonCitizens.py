"""Retarget the Universal Animation Library to the modular Citizens Pack cast."""
from math import atan2, degrees

import unreal as ue

from ApartmentScene import make_material
from BrightonUpgrade import ACTORS, ASSETS, LIB, P, V, factory_asset, node, output, save
from CityLifeCharacters import PEOPLE, apply_profile, move_prop


CITIZENS = '/Game/Citizens_Pack'
UNIVERSAL = '/Game/Prologue/CityLife/UniversalSource'
UNIVERSAL_SK = UNIVERSAL+'/UAL1_Standard/SkeletalMeshes/UAL1_Standard'
MOTIONS = PEOPLE+'/UniversalMotions'
REQUIRED = {
    'Idle':'Idle_Loop', 'Talk':'Idle_Talking_Loop', 'Walk':'Walk_Loop', 'FormalWalk':'Walk_Formal_Loop',
    'Run':'Sprint_Loop', 'Jog':'Jog_Fwd_Loop', 'Sit':'Sitting_Idle_Loop', 'SeatedTalk':'Sitting_Talking_Loop',
    'Fall':'Death01', 'Armed':'Pistol_Idle_Loop', 'Shot':'Pistol_Shoot',
}
LOOKS = {
    'Ivan': ('Karl_C',181), 'Krill': ('Karl_A',185), 'DutyOfficer': ('Tony_A',181),
    'Veteran': ('Tony_D',172), 'Guard': ('Tony_B',186), 'Patrol': ('Karl_B',183),
    'Agent': ('Tony_C',183), 'Bartender': ('Karl_A',177), 'OlderMan': ('Tony_D',173),
    'Shopkeeper': ('Karl_B',170), 'PedestrianWoman': ('Karl_C',166),
    'PedestrianMan': ('Tony_A',178), 'Smoker': ('Tony_C',180),
}


def require(path):
    asset = ue.load_asset(path)
    assert asset, path
    return asset


def restore_mouth():
    path = CITIZENS+'/Materials/MI_Citizens_Pack_Mouth_Inst'
    if ASSETS.does_asset_exist(path):
        return require(path)
    material = make_material(CITIZENS, 'CitizenMouth', (.21,.16,.14), .65)
    library = CITIZENS+'/Textures/Citizens_Pack_Body/T_Citizens_Pack_Mouth_'
    color = node(material, ue.MaterialExpressionTextureSample, texture=require(library+'BaseColor'))
    normal = node(material, ue.MaterialExpressionTextureSample, texture=require(library+'Normal'),
                  sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    orm = node(material, ue.MaterialExpressionTextureSample, texture=require(library+'ORM'),
               sampler_type=ue.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    for expression, channel, prop in ((color,'RGB',P.MP_BASE_COLOR),(normal,'RGB',P.MP_NORMAL),
                                     (orm,'R',P.MP_AMBIENT_OCCLUSION),(orm,'G',P.MP_ROUGHNESS),
                                     (orm,'B',P.MP_METALLIC)):
        output(expression,material,prop,channel)
    LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    LIB.recompile_material(material)
    save(material)
    instance = factory_asset(CITIZENS+'/Materials','MI_Citizens_Pack_Mouth_Inst',ue.MaterialInstanceConstant,
                             ue.MaterialInstanceConstantFactoryNew())
    LIB.set_material_instance_parent(instance,material)
    save(instance)
    return instance


def chains():
    yield 'Spine','spine_01','spine_03'
    yield 'Head','neck_01','head'
    for side in ('l','r'):
        yield f'Clavicle_{side}',f'clavicle_{side}',f'clavicle_{side}'
        yield f'Arm_{side}',f'upperarm_{side}',f'hand_{side}'
        yield f'Leg_{side}',f'thigh_{side}',f'foot_{side}'
        yield f'Toes_{side}',f'ball_{side}',f'ball_{side}'
        for finger in ('index','middle','ring','pinky','thumb'):
            yield f'{finger}_{side}',f'{finger}_01_{side}',f'{finger}_03_{side}'


def rig(mesh, folder, name):
    asset = factory_asset(folder,name,ue.IKRigDefinition,ue.IKRigDefinitionFactory())
    controller = ue.IKRigController.get_controller(asset)
    controller.set_skeletal_mesh(mesh)
    existing = {str(chain.chain_name) for chain in controller.get_retarget_chains()}
    if not existing:
        assert controller.set_retarget_root('pelvis')
        for chain, first, last in chains():
            assert str(controller.add_retarget_chain(chain,first,last,'None')) == chain
    save(asset)
    return asset


def retarget(target):
    results = {key: MOTIONS+'/A_Citizen_'+clip for key,clip in REQUIRED.items()}
    if not all(ASSETS.does_asset_exist(path) for path in results.values()):
        source = require(UNIVERSAL_SK)
        source_rig = rig(source,UNIVERSAL,'IK_Universal')
        target_rig = rig(target,UNIVERSAL,'IK_Citizens')
        asset = factory_asset(UNIVERSAL,'RTG_Universal_Citizens',ue.IKRetargeter,ue.IKRetargetFactory())
        controller = ue.IKRetargeterController.get_controller(asset)
        for role,model,definition in ((ue.RetargetSourceOrTarget.SOURCE,source,source_rig),
                                      (ue.RetargetSourceOrTarget.TARGET,target,target_rig)):
            controller.set_ik_rig(role,definition)
            controller.set_preview_mesh(role,model)
        controller.add_default_ops()
        controller.auto_map_chains(ue.AutoMapChainType.EXACT,True)
        assert all(str(controller.get_source_chain(name)) == name for name,_,_ in chains())
        controller.auto_align_all_bones(ue.RetargetSourceOrTarget.SOURCE)
        save(asset)
        clips = [ASSETS.find_asset_data(UNIVERSAL_SK+clip) for clip in REQUIRED.values()]
        params = ue.IKRetargetBatchOperationInputs(assets_to_retarget=clips,source_mesh=source,
            target_mesh=target,ik_retarget_asset=asset,search='UAL1_Standard',replace='A_Citizen_',
            target_path=MOTIONS,include_referenced_assets=False,overwrite_existing_files=True)
        retargeted = ue.IKRetargetBatchOperation.run_batch_retarget(params)
        assert len(retargeted) == len(REQUIRED),(len(retargeted),len(REQUIRED))
    clips = {key:require(path) for key,path in results.items()}
    skeleton = target.get_editor_property('skeleton')
    for key,clip in clips.items():
        assert clip.get_editor_property('skeleton') == skeleton and clip.get_play_length() > .2, key
        clip.set_editor_properties(dict(enable_root_motion=False,force_root_lock=True))
        save(clip)
    ue.log(f'CITIZEN_RETARGET_OK {len(clips)} clips to {skeleton.get_name()}')
    return clips


def gesture(mesh, base, name, variant):
    factory = ue.AnimSequenceFactory()
    factory.set_editor_properties(dict(target_skeleton=mesh.get_editor_property('skeleton'),preview_skeletal_mesh=mesh))
    clip = factory_asset(MOTIONS,'A_Citizen_'+variant+'_'+name,ue.CityGestureSequence,factory)
    assert ue.CityCharacterAuthoring.author_gesture(mesh,base,clip,name),(variant,name)
    save(clip)
    return clip


def profiles():
    mouth = restore_mouth()
    variants = sorted({name for name,_ in LOOKS.values()})
    meshes = {name:require(CITIZENS+'/Meshes/SK_Citizens_Pack_'+name) for name in variants}
    for mesh in meshes.values():
        slots = list(mesh.get_editor_property('materials'))
        for index,slot in enumerate(slots):
            if 'mouth' in str(slot.get_editor_property('material_slot_name')).lower():
                slot.set_editor_property('material_interface',mouth)
                slots[index] = slot
        mesh.set_editor_property('materials',slots)
        save(mesh)
    universal = retarget(meshes['Karl_A'])
    sample = ue.CityCharacterAuthoring.pose_bone_position
    unique = {}
    for role,(variant,height) in LOOKS.items():
        mesh = meshes[variant]
        clips = {key:universal[key] for key in ('Idle','Talk','Walk','Run','Sit','Fall','Armed','Shot','SeatedTalk')}
        clips['SeatedIdle'] = clips['Sit']
        if role in ('Patrol','Krill','DutyOfficer'):
            clips['Walk'] = universal['FormalWalk']
        if role == 'Veteran':
            clips['Run'] = universal['Jog']
        if role in ('Ivan','Smoker','Agent'):
            clips['Smoke'] = unique.get((variant,'Smoke')) or gesture(mesh,clips['Idle'],'Smoke',variant)
            unique[variant,'Smoke'] = clips['Smoke']
            save(mesh)
        if role in ('OlderMan','Bartender'):
            clips['Idle'] = gesture(mesh,universal['Idle'],'HoldBottle',variant)
            clips['Talk'] = gesture(mesh,universal['Talk'],'TalkWithBottle',variant)
            save(mesh)
        clips['Nod'] = unique.get((variant,'Nod')) or gesture(mesh,universal['Idle'],'Nod',variant)
        unique[variant,'Nod'] = clips['Nod']
        if role in ('Krill','DutyOfficer'):
            clips['SeatedNod'] = gesture(mesh,clips['Sit'],'SeatedNod',variant)
        right = sample(mesh,universal['Idle'],'upperarm_r',0)-sample(mesh,universal['Idle'],'upperarm_l',0)
        assert right.length() > 25,(variant,right)
        yaw = -degrees(atan2(-right.x,right.y))
        bounds = mesh.get_bounds()
        scale = height/(2*bounds.box_extent.z)
        palette = [mouth if 'mouth' in str(slot.get_editor_property('material_slot_name')).lower()
                   else slot.get_editor_property('material_interface') for slot in mesh.get_editor_property('materials')]
        assert all(palette),(variant,palette)
        profile = require(PEOPLE+'/Profiles/DA_'+role)
        profile.set_editor_properties(dict(mesh=mesh,materials=palette,model_scale=scale,facing_yaw=yaw,
            feet_offset=scale*(bounds.box_extent.z-bounds.origin.z),
            motions={ue.Name(key):clip for key,clip in clips.items()}))
        save(profile)
        ue.log(f'CITIZEN_PROFILE {role} {variant} scale={scale:.3f} yaw={yaw:.1f}')
    return {role:require(PEOPLE+'/Profiles/DA_'+role) for role in LOOKS}


def attach_props(actor, component):
    idle = actor.get_editor_property('character_profile').get_editor_property('motions')[ue.Name('Idle')]
    for prop in actor.get_attached_actors(True,False):
        label = prop.get_actor_label()
        if prop.actor_has_tag('ActCue:GuardWeapon'):
            move_prop(prop,actor,component,'hand_r',(7,1,0))
        elif label == 'Gauze over broken nose':
            move_prop(prop,actor,component,'head',(9,0,3))
        elif 'Bottle' in label or 'bottle' in label:
            assert component.does_socket_exist('BottleGrip'),(label,idle.get_name())
            move_prop(prop,actor,component,'BottleGrip',(0,0,0))


def dress_cast(palettes):
    count = 0
    for actor in ACTORS.get_all_level_actors():
        if not isinstance(actor,ue.ActOneCast):
            continue
        current = actor.get_editor_property('character_profile')
        role = current.get_name().removeprefix('DA_') if current else ''
        if role == 'Dima':
            continue
        assert role in palettes,(actor.get_actor_label(),role)
        component = actor.get_editor_property('character_mesh')
        for index in range(component.get_num_materials()):
            component.set_material(index,None)
        mesh = apply_profile(actor,palettes[role])
        attach_props(actor,mesh)
        count += 1
    return count


def limit_texture_sizes():
    limit = 2048
    resized = 0
    for path in ASSETS.list_assets(CITIZENS+'/Textures',True):
        texture = require(path)
        if not isinstance(texture,ue.Texture2D):
            continue
        if max(texture.blueprint_get_size_x(),texture.blueprint_get_size_y()) > limit:
            result = ue.TextureAssetActionsBlueprintFns.resize_texture_source(texture,limit)
            assert result != ue.TextureAssetActionsBlueprintReturn.ERROR, path
            texture.set_editor_property('max_texture_size',limit)
            save(texture)
            resized += 1
    ue.log(f'CITIZEN_TEXTURES_OK resized={resized} maximum={limit}')
