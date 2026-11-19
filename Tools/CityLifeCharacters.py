"""Import the rigged models and assign appearances without changing story actors."""
from math import atan2, degrees

import unreal as ue

from BrightonUpgrade import (
    ACTORS, ASSETS, LIB, P, PROJECT, TOOLS, V, constant, factory_asset, media, node, output, save,
)
from ApartmentScene import make_material

ROOT = "/Game/Prologue/CityLife"
PEOPLE = ROOT + "/People"
SOURCE = PROJECT / "SourceAssets/CityLife"

# Profile name, source outfit, final height, garment, trousers, skin and hair.
STYLES = {
    "Dima": ("LongSleeve", 183, "37495b", "343a42", "c59076", "352f2a"),
    "Ivan": ("Suit", 181, "243849", "27262d", "bd8c69", "4a352b"),
    "Krill": ("Suit", 186, "344b65", "242e42", "cea58b", "857a74"),
    "DutyOfficer": ("Shirt", 180, "526276", "303843", "b57d61", "423b36"),
    "Veteran": ("LongSleeve", 175, "665b44", "524c43", "b48670", "87817a"),
    "Guard": ("Shirt", 186, "303e53", "393e48", "c99c78", "3b2c27"),
    "Patrol": ("Suit", 184, "415366", "3d414a", "966b56", "3b2a25"),
    "Agent": ("Suit", 181, "30333f", "24252d", "c18968", "5d4739"),
    "Bartender": ("Shirt", 179, "b6a48a", "3d3934", "a9775e", "362d29"),
    "OlderMan": ("LongSleeve", 173, "73655b", "383b3e", "caa283", "938780"),
    "Shopkeeper": ("Woman", 167, None, None, None, "LightSkin2"),
    "PedestrianWoman": ("Woman", 169, None, None, None, "DarkSkin1"),
    "PedestrianMan": ("Casual", 177, "6c5141", "4d5356", "b47d60", "3d332b"),
    "Smoker": ("LongSleeve", 181, "696447", "3b4954", "af795e", "3a302c"),
}

STORY_ROLES = {
    "IvanStreet": "Ivan", "IvanFedor": "Ivan", "Krill": "Krill", "DutyOfficer": "DutyOfficer",
    "Veteran": "Veteran", "BarGuard": "Guard", "OldMan": "OlderMan", "Bartender": "Bartender",
    "GroceryClerk": "Shopkeeper", "Patrol": "Patrol", "Agent": "Agent",
}

COMMON_CLIPS = {"idle": "Idle", "walk": "Walk", "walking": "Walk", "run": "Run", "running": "Run", "jump": "Jump", "jump2": "Jump",
                "sitting": "Sit", "death": "Fall"}


def mtl_colors(file):
    colors = {}
    name = None
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "newmtl":
            name = fields[1]
        elif fields[0] == "Kd" and name:
            colors[name] = tuple(map(float, fields[1:4]))
    return colors


def import_task(file, folder, options=None, replace=False, save_imported=False):
    task = ue.AssetImportTask()
    task.set_editor_properties(dict(filename=str(file), destination_path=folder, options=options,
                                    automated=True, replace_existing=replace, save=save_imported))
    TOOLS.import_asset_tasks([task])
    return task.get_objects()


def skeletal_source(outfit):
    name = "Animated_Woman_Smooth" if outfit == "Woman" else "Smooth_Male_" + outfit
    folder = PEOPLE + "/Models/" + outfit
    model = ue.load_asset(folder + "/" + name) if ASSETS.does_asset_exist(folder + "/" + name) else None
    is_import = model is None
    if is_import:
        options = ue.FbxImportUI()
        options.set_editor_properties(dict(automated_import_should_detect_type=False,
            mesh_type_to_import=ue.FBXImportType.FBXIT_SKELETAL_MESH, import_as_skeletal=True, import_mesh=True,
            import_animations=True, import_materials=False, import_textures=False, create_physics_asset=False))
        options.get_editor_property("skeletal_mesh_import_data").set_editor_property("force_front_x_axis", True)
        options.get_editor_property("anim_sequence_import_data").set_editor_properties(dict(
            force_front_x_axis=True, custom_sample_rate=30 if outfit == "Woman" else 24,
            use_default_sample_rate=False, snap_to_closest_frame_boundary=True))
        imported = import_task(SOURCE/"People"/(name+".fbx"),folder,options,save_imported=True)
        model = next((item for item in imported if isinstance(item,ue.SkeletalMesh)),None)
        assert model, name
        for item in imported:
            save(item)
        # Legacy FBX returns the mesh in AssetImportTask even when it creates many packages.
        skeleton = model.get_editor_property("skeleton")
        assert skeleton,name
        save(skeleton)
    motion = {}
    for path in ASSETS.list_assets(folder,True):
        if "_Anim_" not in path:
            continue
        asset = ue.load_asset(path)
        key = asset.get_name().split("_")[-1].lower()
        if is_import and isinstance(asset,ue.AnimSequence):
            save(asset)
        if key in COMMON_CLIPS and isinstance(asset,ue.AnimSequence):
            motion[COMMON_CLIPS[key]] = asset
    assert "Idle" in motion, (outfit, list(motion))
    if outfit != "Woman":
        assert set(COMMON_CLIPS.values()) <= motion.keys(), (outfit, list(motion))
    else:
        assert len(motion)>=3, (outfit,list(motion))
    for gesture in ("Talk","Smoke","Nod","Armed"):
        if outfit == "Woman" and gesture != "Talk":
            continue
        factory = ue.AnimSequenceFactory()
        factory.set_editor_properties(dict(target_skeleton=motion["Idle"].get_editor_property("skeleton"),
                                           preview_skeletal_mesh=model))
        clip = factory_asset(PEOPLE+"/Motions/"+outfit,"A_"+outfit+"_"+gesture,ue.CityGestureSequence,factory)
        assert ue.CityCharacterAuthoring.author_gesture(model,motion["Idle"],clip,gesture), (name,gesture)
        save(clip)
        motion[gesture] = clip
    ue.log("CITY_LIFE_RIG "+outfit+" "+str(sorted(motion)))
    return name,model,motion


def srgb(hex_color):
    return tuple((int(hex_color[i:i+2],16)/255.0)**2.2 for i in (0,2,4))


def character_material(style, slot, color, texture=None):
    material = make_material(PEOPLE+"/Materials",style+"_"+slot,color,.76 if slot!="Eyes" else .35)
    if texture and not isinstance(LIB.get_material_property_input_node(material,P.MP_BASE_COLOR),ue.MaterialExpressionTextureSample):
        sample = node(material,ue.MaterialExpressionTextureSample,texture=texture)
        output(sample,material,P.MP_BASE_COLOR,"RGB")
    LIB.set_material_usage(material,ue.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    LIB.recompile_material(material)
    save(material)
    return material


def create_profiles():
    editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
    ue.SystemLibrary.execute_console_command(editor.get_editor_world(),"Interchange.FeatureFlags.Import.FBX 0")
    models = {outfit:skeletal_source(outfit) for outfit in dict.fromkeys(entry[0] for entry in STYLES.values())}
    profiles = {}
    for style,(outfit,height,top,legs,skin,hair) in STYLES.items():
        name,model,motions = models[outfit]
        get_position = ue.CityCharacterAuthoring.pose_bone_position
        hand = "RightArm" if outfit=="Woman" else "UpperArm.R"
        left = "LeftArm" if outfit=="Woman" else "UpperArm.L"
        width = get_position(model,motions["Idle"],hand,0)-get_position(model,motions["Idle"],left,0)
        assert width.length()>1,(style,width)
        # The source packs use different forward axes. Resolve from the rig after FBX conversion.
        yaw = -degrees(atan2(-width.x,width.y))
        if outfit=="Woman":
            toe = get_position(model,motions["Idle"],"LeftToeBase",0)
            foot = get_position(model,motions["Idle"],"LeftFoot",0)
            if toe.length()>1 and foot.length()>1:
                direction=toe-foot
                if direction.x*direction.x+direction.y*direction.y>10:
                    yaw=-degrees(atan2(direction.y,direction.x))
        bounds = model.get_bounds()
        scale = height/(bounds.box_extent.z*2)
        feet = -(bounds.origin.z-bounds.box_extent.z)*scale
        slots = [str(slot.get_editor_property("material_slot_name")) for slot in model.get_editor_property("materials")]
        if outfit=="Woman":
            texture = media(SOURCE/"People"/(hair+".png"),PEOPLE+"/Textures")
            texture.set_editor_properties(dict(filter=ue.TextureFilter.TF_NEAREST,
                mip_gen_settings=ue.TextureMipGenSettings.TMGS_NO_MIPMAPS))
            save(texture)
            palette = [character_material(style,slot,(.5,.4,.3),texture) for slot in slots]
        else:
            raw = mtl_colors(SOURCE/"People"/(name+".mtl"))
            colors = {"Shirt":top, "Shirt2":"9c8f83" if style=="Bartender" else top, "Pants":legs, "Skin":skin,
                      "Hair":hair, "Hair2":hair, "Eyes":"231d18", "Details":"b5a286", "Shoes":"2b2826"}
            palette = []
            for slot in slots:
                tint = srgb(colors[slot]) if slot in colors else raw.get(slot,(.12,.10,.08))
                texture = media(SOURCE/"People/Tie.png",PEOPLE+"/Textures") if slot=="TieTexture" else None
                palette.append(character_material(style,slot,tint,texture))
        f = ue.DataAssetFactory()
        f.set_editor_property("data_asset_class",ue.CityCharacterProfile)
        profile = factory_asset(PEOPLE+"/Profiles","DA_"+style,ue.CityCharacterProfile,f)
        profile.set_editor_properties(dict(mesh=model,model_scale=scale,facing_yaw=yaw,feet_offset=feet,
            materials=palette,motions={ue.Name(key):value for key,value in motions.items()}))
        save(profile)
        profiles[style] = profile
        ue.log(f"CITY_LIFE_PROFILE {style}: {scale:.3f}, yaw {yaw:.0f}, feet {feet:.1f}")
    return profiles


def apply_profile(actor, profile):
    actor.set_editor_property("character_profile",profile)
    component = actor.get_editor_property("character_mesh")
    component.set_skeletal_mesh_asset(profile.get_editor_property("mesh"))
    component.set_relative_scale3d(V(*([profile.get_editor_property("model_scale")]*3)))
    component.set_relative_location(V(0,0,profile.get_editor_property("feet_offset")),False,True)
    component.set_relative_rotation(ue.Rotator(yaw=profile.get_editor_property("facing_yaw")),False,True)
    for index,material in enumerate(profile.get_editor_property("materials")):
        component.set_material(index,material)
    motions=profile.get_editor_property("motions")
    pose=actor.get_editor_property("default_pose")
    key={ue.ActOnePose.SEATED:"Sit",ue.ActOnePose.SMOKING:"Smoke",ue.ActOnePose.CONVERSING:"Talk",
         ue.ActOnePose.WALKING:"Walk",ue.ActOnePose.RUNNING:"Run"}.get(pose,"Idle")
    pose_time=actor.get_editor_property("animation_phase")
    if pose_time<=0:
        pose_time={"Sit":.7,"Smoke":2.9}.get(key,.2)
    component.override_animation_data(motions.get(ue.Name(key),motions[ue.Name("Idle")]),True,True,pose_time,1.0)
    component.set_update_animation_in_editor(True)
    component.set_collision_profile_name(ue.Name("NoCollision"))
    return component


def move_prop(prop, owner, mesh, socket, offset, rotate=0):
    position = mesh.get_socket_location(ue.Name(socket))
    world_offset = ue.MathLibrary.transform_direction(owner.get_actor_transform(),V(*offset))
    prop.set_actor_location(position+world_offset,False,True)
    prop.set_actor_rotation(ue.Rotator(yaw=owner.get_actor_rotation().yaw+rotate),False)
    prop.get_component_by_class(ue.SceneComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    assert prop.attach_to_component(mesh,ue.Name(socket),ue.AttachmentRule.KEEP_WORLD,
        ue.AttachmentRule.KEEP_WORLD,ue.AttachmentRule.KEEP_WORLD,False),prop.get_actor_label()


def update_story_cast(profiles):
    count = 0
    for actor in ACTORS.get_all_level_actors():
        if not isinstance(actor,ue.ActOneCast) or not actor.actor_has_tag("ActOneGenerated"):
            continue
        key = next((str(tag).removeprefix("ActCue:") for tag in actor.tags if str(tag).startswith("ActCue:")),"")
        assert key in STORY_ROLES,(actor,key)
        mesh = apply_profile(actor,profiles[STORY_ROLES[key]])
        original = actor.get_attached_actors(True,True)
        hand_socket = next((bone for bone in ("MiddleHand_R","MiddleHand.R") if mesh.get_bone_index(ue.Name(bone))>=0),"")
        keep = set()
        for prop in original:
            label=prop.get_actor_label()
            if prop.actor_has_tag("ActCue:GuardWeapon"):
                assert hand_socket
                move_prop(prop,actor,mesh,hand_socket,(6,0,0))
            elif label in ("Green glass bottle","Bottle neck","Cigarette","Cigarette ember"):
                assert hand_socket
                offset = {"Green glass bottle":(2,0,5),"Bottle neck":(2,0,17),
                          "Cigarette":(4,0,1),"Cigarette ember":(8,0,1)}[label]
                move_prop(prop,actor,mesh,hand_socket,offset)
            elif label=="Gauze over broken nose":
                move_prop(prop,actor,mesh,"Head",(10,0,4))
            else:
                continue
            keep.add(prop)
            keep.update(prop.get_attached_actors(True,True))
        # The story actors and interactive props keep their original identities and cues.
        obsolete = [part for part in original if part not in keep and part.actor_has_tag("ActOneGenerated")]
        actor.set_editor_property("parts",{})
        if obsolete:
            assert ACTORS.destroy_actors(obsolete)
        count += 1
    return count


def update_footsteps(profile):
    folder="/Game/Prologue/Brighton/Audio"
    for surface in ("Wood","Tile","Asphalt","Wet"):
        for i in range(4):
            name=f"{surface}{i}"
            file=PROJECT/"Resources/Brighton/Audio"/(name+".wav")
            imported=import_task(file,folder,replace=True)
            assert imported and isinstance(imported[0],ue.SoundWave),name
            save(imported[0])
    data=ue.load_asset("/Game/Prologue/Brighton/DA_Environment")
    data.set_editor_property("player_appearance",profile)
    save(data)
