"""Create three standalone maps from the saved neighborhood. Original map remains an archive."""
from pathlib import Path
from datetime import datetime
import sys,shutil
import unreal as ue

root=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
assets=ue.get_editor_subsystem(ue.EditorAssetSubsystem)
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
source='/Game/Prologue/L_DimaApartmentStreet'
folder='/Game/Locations'
paths={key:folder+'/'+name for key,name in [('apartment','L_DimaApartmentInterior'),('street','L_NeptuneStreet'),('precinct','L_PolicePrecinct')]}
backup=root/'Saved/Backups'/('SplitLevels_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
for rel in ('Content/Prologue/L_DimaApartmentStreet.umap','Config/DefaultEngine.ini','Config/DefaultGame.ini','Content/Story/DimaApartment/DA_DimaApartmentScenario.uasset'):
    dest=backup/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/rel,dest)
ue.log('LEVEL_BACKUP '+str(backup))
assert levels.load_level(source)
front=next(a for a in actors.get_all_level_actors() if a.get_actor_label()=='Front door')
p=front.get_actor_location()
door_spec=((p.x,p.y,p.z),(-249.4,-449.5,p.z),front.get_actor_rotation().yaw,-90)
sys.path.insert(0,str(root/'Tools'))
from ApartmentGameplay import build_gameplay
ue.InternationalizationLibrary.set_current_culture('en',False)
hud_path=folder+'/BP_SeparateLocationsHUD'
if not assets.does_asset_exist(hud_path):
    mode=build_gameplay(folder,'BP_SeparateLocationsHUD',street_door=door_spec)
else:
    mode=ue.BlueprintEditorLibrary.generated_class(ue.load_asset(folder+'/BP_PrologueStreetGameMode'))

def inside_precinct(pos):
    return 820<pos.x<1788 and -3220<pos.y<-2180 and pos.z<290

def keep(a,key):
    f=str(a.get_folder_path())
    label=a.get_actor_label()
    if isinstance(a,ue.StreetDoorThreshold): return False
    if isinstance(a,ue.StreetPortal):
        if key=='street': return label!='Precinct lobby exit'
        return key=='precinct' and label=='Precinct lobby exit'
    if f=='Street/07 Location transitions': return False
    if f=='Street/06 Sky and time': return True
    if isinstance(a,(ue.WorldSettings,ue.DefaultPhysicsVolume)): return True
    if key=='apartment':
        return not f.startswith('Street/') or f in ('Street/07 Interior additions','Street/02 Apartment facade')
    if isinstance(a,ue.PlayerStart): return False
    if key=='street':
        if label=='Front door': return True
        if not f.startswith('Street/'): return False
        if f in ('Street/07 Interior additions','Street/11 Review cameras'): return False
        if f=='Street/06 Precinct' and (label.startswith(('Reception','Officer','Personnel'))): return False
        return True
    return f=='Street/06 Precinct'

def spawn_point(label,pos,yaw,tag):
    existing=next((a for a in actors.get_all_level_actors() if a.get_actor_label()==label),None)
    if existing: return existing
    a=actors.spawn_actor_from_class(ue.TargetPoint,ue.Vector(*pos),ue.Rotator(0,0,yaw))
    a.set_actor_label(label)
    a.set_folder_path(ue.Name('Location transitions'))
    a.tags=[ue.Name(tag)]
    return a

def portal(label,pos,extent,prompt,dest,tag,title,photo):
    a=next((a for a in actors.get_all_level_actors() if a.get_actor_label()==label),None)
    if a is None: a=actors.spawn_actor_from_class(ue.StreetPortal,ue.Vector(*pos))
    a.set_actor_label(label)
    a.set_folder_path(ue.Name('Location transitions'))
    a.set_editor_properties(dict(prompt=prompt,destination_spawn=ue.Name(tag),
        destination_title=title,destination_photo=ue.load_asset('/Game/Prologue/Street/Transitions/T_Transition_'+photo),arrival=None))
    a.get_editor_property('focus_box').set_box_extent(ue.Vector(*extent),False)
    return a

for key,path in paths.items():
    if assets.does_asset_exist(path):
        assert levels.load_level(path),'Could not open '+path
    else:
        assert levels.new_level_from_template(path,source),'Could not create '+path
    placed=actors.get_all_level_actors()
    # Instance batches can contain both interior and exterior decoration. Split the instances too.
    for a in placed:
        if not keep(a,key): continue
        if isinstance(a,ue.StreetMeshInstances) and str(a.get_folder_path())=='Street/06 Precinct':
            c=a.get_editor_property('instances')
            if key in ('street','precinct'):
                for i in reversed(range(c.get_instance_count())):
                    t=c.get_instance_transform(i,True)
                    pos=t.translation
                    if inside_precinct(pos)==(key=='street'): c.remove_instance(i)
    deleted=[a for a in placed if not keep(a,key)]
    assert actors.destroy_actors(deleted),'Could not remove actors from '+path
    remaining=actors.get_all_level_actors()
    time=next(a for a in remaining if isinstance(a,ue.PrologueTimeOfDay))
    time.set_editor_property('street_lights',[a for a in time.get_editor_property('street_lights') if a and a in remaining])
    if key!='apartment':
        time.set_editor_properties(dict(hour_hand=None,minute_hand=None,pillow_view=None))
    for a in remaining:
        if a.get_actor_label()=='Front door':
            a.tags=[ue.Name('StreetDoor')] if key=='apartment' else []
            mesh=a.get_component_by_class(ue.StaticMeshComponent)
            mesh.set_simulate_physics(False)
            mesh.set_collision_profile_name(ue.Name('BlockAll'))
    if key=='apartment':
        spawn_point('Return from Neptune Street',(-194,-330,98),90,'FromStreet')
    elif key=='street':
        for a in remaining:
            if isinstance(a,ue.StreetPortal) and a.get_actor_label()=='Precinct street door':
                a.set_editor_properties(dict(arrival=None,destination_spawn=ue.Name('FromStreet')))
        spawn_point('Arrival from Dima apartment',(-194,-552,101),-90,'FromApartment')
        spawn_point('Arrival from police precinct',(1914,-2725,101),0,'FromPrecinct')
        portal('Dima apartment entrance',(-194,-465,106),(70,12,108),'Войти в квартиру Димы',paths['apartment'],'FromStreet','Квартира Димы','Apartment')
        # The apartment interior is absent from the street map. Its shell stays physically closed.
        for i,(x1,x2,y1,y2) in enumerate(((-390,390,-448,455),(390,808,-448,115),(-777,-390,32,455))):
            a=actors.spawn_actor_from_class(ue.DimaStoryFocusProxy,ue.Vector((x1+x2)/2,(y1+y2)/2,160))
            a.set_actor_label('Apartment facade collision '+str(i))
            a.set_folder_path(ue.Name('Location boundaries'))
            c=a.get_editor_property('focus_box')
            c.set_box_extent(ue.Vector((x2-x1)/2,(y2-y1)/2,160),False)
            c.set_collision_profile_name(ue.Name('BlockAll'))
    else:
        for a in remaining:
            if isinstance(a,ue.StreetPortal):
                a.set_editor_properties(dict(arrival=None,destination_spawn=ue.Name('FromPrecinct')))
        spawn_point('Arrival from Neptune Street',(1602,-2725,101),180,'FromStreet')
    if key!='apartment':
        pos,yaw=((-194,-552,101),-90) if key=='street' else ((1602,-2725,101),180)
        start=actors.spawn_actor_from_class(ue.PlayerStart,ue.Vector(*pos),ue.Rotator(0,0,yaw))
        start.set_actor_label('Default '+key+' entry')
    world=ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    settings=ue.GameplayStatics.get_actor_of_class(world,ue.WorldSettings)
    settings.set_editor_property('default_game_mode',mode)
    assert levels.save_current_level(),'Could not save '+path
    ue.log('LEVEL_CREATED '+path+' actors='+str(len(actors.get_all_level_actors())))

for key in ('street','precinct'):
    assert levels.load_level(paths[key])
    for a in actors.get_all_level_actors():
        if not isinstance(a,ue.StreetPortal): continue
        label=a.get_actor_label()
        dest=None
        if label=='Precinct street door': dest=paths['precinct']
        if label=='Precinct lobby exit': dest=paths['street']
        if label=='Dima apartment entrance': dest=paths['apartment']
        if dest: a.set_editor_property('destination_map',ue.load_asset(dest))
    assert levels.save_current_level()
scenario=ue.load_asset('/Game/Story/DimaApartment/DA_DimaApartmentScenario')
scenario.set_editor_properties(dict(apartment_map=ue.Name('L_DimaApartmentInterior'),street_map=ue.load_asset(paths['street'])))
assert assets.save_loaded_asset(scenario,False)
# Configure startup/cooking only after every map has been created successfully.
p=root/'Config/DefaultEngine.ini'
s=p.read_text(encoding='utf-8-sig')
import re
s=re.sub(r'(?m)^(EditorStartupMap|GameDefaultMap)=.*$',lambda m:m[1]+'='+paths['apartment']+'.L_DimaApartmentInterior',s)
s=re.sub(r'(?m)^GlobalDefaultGameMode=.*$','GlobalDefaultGameMode='+folder+'/BP_PrologueStreetGameMode.BP_PrologueStreetGameMode_C',s)
p.write_text(s,encoding='utf-8')
p=root/'Config/DefaultGame.ini'
s=p.read_text(encoding='utf-8-sig')
s=re.sub(r'(?m)^\+MapsToCook=.*\n?','',s)
s=s.replace('[/Script/UnrealEd.ProjectPackagingSettings]','[/Script/UnrealEd.ProjectPackagingSettings]\n'+'\n'.join('+MapsToCook=(FilePath="'+p+'")' for p in paths.values()))
p.write_text(s,encoding='utf-8')
ue.log('LEVEL_SPLIT_APPLIED')
