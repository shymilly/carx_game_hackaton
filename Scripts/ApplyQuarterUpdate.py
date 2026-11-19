"""Apply the 0.14 street, cinematic and animation changes to the active maps."""
from datetime import datetime
from pathlib import Path
from shutil import copy2
import json
import sys

import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(project/"Tools"))
from ActOneScenes import page_speakers
from ApartmentScene import make_material
from BrightonStreetDetails import build_street_details, expression, factory_finishes
from BrightonUpgrade import ACTORS, LEVELS, LIB, P, V, color, constant, factory_asset, media, node, output, save
from CityLifeCharacters import PEOPLE, STYLES, apply_profile, mtl_colors
from CityLifeEnvironment import save_instance_material_usage
from RefineStreetVisuals import set_lettering


def pistol_asset():
    directory=project/"Resources/Brighton/Props/pistol_obj"
    folder="/Game/Prologue/Props/pistol_obj"
    model=media(directory/"SM_pistol_obj.obj",folder)
    palette=mtl_colors(directory/"pistol.mtl")
    for index,slot in enumerate(model.get_editor_property("static_materials")):
        name=str(slot.get_editor_property("material_slot_name"))
        assert name in palette,name
        metal=name in ("slide","metal")
        mat=make_material(folder,name,palette[name],.38 if metal else .76)
        if not LIB.get_material_property_input_node(mat,P.MP_METALLIC):
            output(constant(mat,.70 if metal else .05),mat,P.MP_METALLIC)
            LIB.recompile_material(mat)
            save(mat)
        model.set_material(index,mat)
    save(model)
    return model


def smoke_material():
    mat=make_material("/Game/Prologue/Brighton","CigaretteSmoke",(.48,.51,.55))
    LIB.delete_all_material_expressions(mat)
    mat.set_editor_properties(dict(two_sided=True,blend_mode=ue.BlendMode.BLEND_TRANSLUCENT,
        shading_model=ue.MaterialShadingModel.MSM_UNLIT,used_with_instanced_static_meshes=True))
    fade=node(mat,ue.MaterialExpressionPerInstanceCustomData,data_index=0,const_default_value=0.)
    varying=node(mat,ue.MaterialExpressionVertexInterpolator)
    assert LIB.connect_material_expressions(fade,"",varying,"") or LIB.connect_material_expressions(fade,"",varying,"VS")
    alpha=expression(mat,{"UV":node(mat,ue.MaterialExpressionTextureCoordinate),"Fade":varying,
                          "Clock":node(mat,ue.MaterialExpressionTime)},"""
        float2 p=UV*2.-1.;
        p.x+=.13*sin(p.y*5.+Clock*1.5);
        float curl=.68+.32*sin(p.x*5.-p.y*3.+Clock*.9);
        return (1.-smoothstep(.05,.96,length(p)))*curl*Fade*.48;""",ue.CustomMaterialOutputType.CMOT_FLOAT1)
    output(alpha,mat,P.MP_OPACITY)
    output(color(mat,(.55,.58,.62)),mat,P.MP_EMISSIVE_COLOR)
    LIB.recompile_material(mat)
    save(mat)


def animation_profiles():
    profiles={key:ue.load_asset(PEOPLE+"/Profiles/DA_"+key) for key in STYLES}
    for role,motion,base in (("Dima","Shot","Idle"),("Krill","SeatedTalk","Sit"),
                             ("DutyOfficer","SeatedTalk","Sit")):
        profile=profiles[role]
        model=profile.get_editor_property("mesh")
        clips=dict(profile.get_editor_property("motions"))
        source=clips[ue.Name(base)]
        factory=ue.AnimSequenceFactory()
        factory.set_editor_properties(dict(target_skeleton=source.get_editor_property("skeleton"),preview_skeletal_mesh=model))
        target=factory_asset(PEOPLE+"/Motions/"+STYLES[role][0],"A_"+STYLES[role][0]+"_"+motion,ue.CityGestureSequence,factory)
        assert ue.CityCharacterAuthoring.author_gesture(model,source,target,motion)
        save(target)
        clips[ue.Name(motion)]=target
        profile.set_editor_property("motions",clips)
        save(profile)
    for role in ("Shopkeeper","PedestrianWoman"):
        profile=profiles[role]
        clips=dict(profile.get_editor_property("motions"))
        prefix=PEOPLE+"/Models/Woman/Animated_Woman_Smooth_Anim_Armature_"
        for key,source in (("Walk","Walking"),("Run","Running"),("Sit","SitIdle")):
            clip=ue.load_asset(prefix+source)
            assert clip,key
            clips[ue.Name(key)]=clip
        profile.set_editor_property("motions",clips)
        save(profile)
    return profiles


def replace_prop(actor,model):
    mesh=actor.get_component_by_class(ue.StaticMeshComponent)
    for child in actor.get_attached_actors(True,True):
        if child.get_actor_label()=="Grip": assert ACTORS.destroy_actor(child)
    mesh.set_static_mesh(model)
    mesh.set_editor_property("override_materials",[])
    mesh.set_collision_profile_name(ue.Name("NoCollision"))
    actor.set_actor_scale3d(V(1,1,1))
    return mesh


def lay_on_surface(actor,model,point,yaw):
    replace_prop(actor,model)
    actor.set_actor_rotation(ue.Rotator(yaw=yaw,roll=90),False)
    actor.set_actor_location(point,False,True)
    center,extent=actor.get_actor_bounds(False)
    actor.add_actor_world_offset(V(point.x-center.x,point.y-center.y,point.z-(center.z-extent.z)+.08),False,True)


def hand_prop(actor,model,performer,clip,time):
    mesh=replace_prop(actor,model)
    mesh.set_mobility(ue.ComponentMobility.MOVABLE)
    body=performer.get_editor_property("character_mesh")
    socket=ue.Name("MiddleHand_R")
    pose=ue.AnimPoseExtensions.get_anim_pose_at_time(clip,time,ue.AnimPoseEvaluationOptions())
    bone=ue.AnimPoseExtensions.get_bone_pose(pose,socket,ue.AnimPoseSpaces.WORLD)
    wrist=ue.MathLibrary.compose_transforms(bone,body.get_world_transform())
    point=wrist.translation+performer.get_actor_forward_vector()*4.-V(0,0,6.5)
    desired=ue.Transform(location=point,rotation=performer.get_actor_rotation(),scale=V(1,1,1))
    local=ue.MathLibrary.make_relative_transform(desired,wrist)
    assert actor.attach_to_component(body,socket,ue.AttachmentRule.KEEP_WORLD,ue.AttachmentRule.KEEP_WORLD,
                                     ue.AttachmentRule.KEEP_WORLD,False)
    actor.set_actor_relative_transform(local,False,True)


def on_desk(placed,model):
    table=next(a for a in placed if a.get_actor_label()=="Writing desk")
    center,extent=table.get_actor_bounds(False)
    pistol=next(a for a in placed if a.actor_has_tag("ActCue:Pistol"))
    surface=V(center.x-.36*extent.x,center.y+.13*extent.y,center.z+extent.z)
    lay_on_surface(pistol,model,surface,12)
    hit=next(a for a in placed if isinstance(a,ue.ActOneInteraction) and a.get_editor_property("action")==ue.ActOneAction.PISTOL)
    hit.set_actor_location(pistol.get_actor_bounds(False)[0],False,True)


def bar_cinematic(placed,model,profiles):
    def cue(tag,cls,at,yaw=0):
        actor=next((a for a in placed if a.actor_has_tag("ActCue:"+tag)),None)
        if not actor:
            actor=ACTORS.spawn_actor_from_class(cls,V(*at),ue.Rotator(yaw=yaw))
            actor.tags=[*actor.tags,ue.Name("ActCue:"+tag)]
        actor.set_actor_label("Bar shot "+tag)
        actor.set_folder_path(ue.Name("Act One/Bar/Cinematic"))
        return actor

    guard=next(a for a in placed if a.actor_has_tag("ActCue:BarGuard"))
    held=next(a for a in placed if a.actor_has_tag("ActCue:GuardWeapon"))
    hand_prop(held,model,guard,profiles["Guard"].get_editor_property("motions")[ue.Name("Armed")],.65)
    dropped=next(a for a in placed if a.actor_has_tag("ActCue:DroppedWeapon"))
    dropped.get_component_by_class(ue.StaticMeshComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    lay_on_surface(dropped,model,V(382,175,0),49)
    dima=cue("BarDima",ue.ActOneCast,(172,91,0),14)
    body=apply_profile(dima,profiles["Dima"])
    shot=profiles["Dima"].get_editor_property("motions")[ue.Name("Shot")]
    body.override_animation_data(shot,False,False,.48,1.)
    weapon=cue("BarShotProp",ue.StaticMeshActor,(172,91,0))
    hand_prop(weapon,model,dima,shot,.47)
    for actor in (dima,weapon,held,dropped):
        actor.set_actor_hidden_in_game(True)
        actor.set_actor_enable_collision(False)
    camera=cue("BarShotCamera",ue.CameraActor,(202,-146,136))
    camera.set_actor_rotation(ue.MathLibrary.find_look_at_rotation(camera.get_actor_location(),V(309,142,99)),False)
    lens=camera.get_component_by_class(ue.CameraComponent)
    lens.set_field_of_view(66.)
    exposure=lens.get_editor_property("post_process_settings")
    exposure.set_editor_properties(dict(override_auto_exposure_bias=True,auto_exposure_bias=-.65))
    lens.set_editor_properties(dict(post_process_settings=exposure,post_process_blend_weight=1.))
    flash=cue("BarFlash",ue.PointLight,(225,102,139))
    light=flash.get_component_by_class(ue.PointLightComponent)
    light.set_mobility(ue.ComponentMobility.MOVABLE)
    light.set_editor_properties(dict(intensity_units=ue.LightUnits.LUMENS,intensity=150.,attenuation_radius=200.,
                                     source_radius=3.,cast_shadows=False))
    light.set_light_color(ue.LinearColor(1.,.60,.29,1))
    light.set_visibility(False)


maps=("L_DimaApartmentInterior","L_NeptuneStreet","L_PolicePrecinct","L_LighthouseBar")
backup=project/"Saved/Backups"/("Quarter014_"+datetime.now().strftime("%Y%m%d_%H%M%S"))
backup.mkdir(parents=True)
for name in maps: copy2(project/"Content/Locations"/(name+".umap"),backup/(name+".umap"))
profiles=animation_profiles()
model=pistol_asset()
smoke_material()
factory_finishes()
spec=json.loads((project/"Docs/Scenario/ActOne.json").read_text(encoding="utf-8"))
data=ue.load_asset("/Game/Story/ActOne/DA_ActOne")
data.set_editor_property("page_speakers",page_speakers(spec))
save(data)
letters=ue.load_asset("/Game/StreetRefinement/Materials/M_Neptune94Ivory")
for name in maps:
    assert LEVELS.load_level("/Game/Locations/"+name)
    placed=ACTORS.get_all_level_actors()
    if name!="L_LighthouseBar":
        fascia=next(a for a in placed if a.get_actor_label().endswith("60 Precinct fascia"))
        set_lettering(fascia,"SM_NeighborhoodPrecinct",letters,name==maps[0])
    if name in maps[:2]:
        if name==maps[0]: on_desk(placed,model)
        for actor in placed:
            if not isinstance(actor,ue.ActOneCast): continue
            if actor.get_editor_property("default_pose")==ue.ActOnePose.SMOKING:
                for prop in actor.get_attached_actors(True,True):
                    if prop.get_actor_label() in ("Cigarette ember","Smoker's cigarette") and not prop.actor_has_tag("CigaretteSource"):
                        prop.tags=[*prop.tags,ue.Name("CigaretteSource")]
        build_street_details(name==maps[0])
        save_instance_material_usage()
    if name=="L_LighthouseBar":
        bar_cinematic(placed,model,profiles)
    assert LEVELS.save_current_level(),name
    ue.log("Q14_MAP_OK "+name)
ue.log("Q14_APPLY_OK")
