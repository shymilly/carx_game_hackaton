"""Render the updated rooms and exterior, then refresh their actual destination photographs."""
from pathlib import Path
import time
import traceback
import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
quarter='-quarterviews' in ue.SystemLibrary.get_command_line().lower()
repair='-streetrepairviews' in ue.SystemLibrary.get_command_line().lower()
reviews=project/'Saved/Reviews'/('Brighton0141' if repair else 'Brighton014' if quarter else 'Brighton012')
reviews.mkdir(parents=True,exist_ok=True)
levels=ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors=ue.get_editor_subsystem(ue.EditorActorSubsystem)
editor=ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
shots=[
    ('L_BrightonGrocery','Grocery',(-403,28,171),(257,-40,132),82),
    ('L_BrightonGrocery','GroceryShelves',(-200,-105,150),(-80,-290,137),82),
    ('L_BrightonGrocery','CashRegister',(89,124,153),(249,130,133),67),
    ('L_BrightonGrocery','Shopkeeper',(90,49,151),(381,64,143),66),
    ('L_DimaApartmentInterior','ApartmentNorth',(32,380,166),(32,2160,-630),78),
    ('L_DimaApartmentInterior','ApartmentWest',(-365,-278,166),(-2800,-1425,-630),76),
    ('L_DimaApartmentInterior','Apartment',(30,-160,168),(-60,170,118),78),
    ('L_NeptuneStreet','Street',(-230,-645,178),(1900,-1450,330),82),
    ('L_NeptuneStreet','PaintedFacades',(-1880,-1530,178),(-1390,-2220,485),82),
    ('L_NeptuneStreet','WindowProjection',(-2780,-1904,245),(-2780,-2080,-28),76),
    ('L_NeptuneStreet','CityContinuation',(-5900,-1425,173),(-12500,-1425,350),88),
    ('L_NeptuneStreet','StreetSign',None,None,58),
    ('L_LighthouseBar','BarCast',(234,199,161),(439,238,131),72),
    ('L_PolicePrecinct','CaptainKrill',(1264,-1760,162),(1254,-1537,122),66),
]
if quarter:
    shots=[shot for shot in shots if shot[1] in ('Apartment','Street')]
    shots.extend([
        ('L_NeptuneStreet','FactorySkyline',(980,-1320,164),(5740,-1430,1675),90),
        ('L_NeptuneStreet','FactoryWorks',(3140,-1700,2770),(5790,-1420,2010),108),
        ('L_NeptuneStreet','PrecinctSign',(1995,-2719,258),(1541,-2725,269),70),
        ('L_NeptuneStreet','BusStop',(-4595,-1750,144),(-4750,-1940,98),74),
        ('L_DimaApartmentInterior','PistolDesk',(-25,310,131),(-58.3,349.3,87.7),52),
        ('L_PolicePrecinct','Precinct',(1602,-2725,170),(1110,-2860,133),80),
    ])
if repair:
    shots=[
        ('L_NeptuneStreet','Street',None,None,80),
        ('L_NeptuneStreet','BrickFacade',(986,-1850,164),(986,-2149,164),64),
        ('L_NeptuneStreet','BrickUpperFloor',(2937,1055,337),(3390,1100,330),59),
        ('L_NeptuneStreet','RailCrossing',(2400,-5320,204),(2400,-7771,532),68),
        ('L_NeptuneStreet','RailEastPortal',(16760,-7415,912),(18200,-7771,755),65),
        ('L_NeptuneStreet','RailWestPortal',(-3600,-7380,862),(-5040,-7771,733),65),
    ]
state=dict(index=0,stage='open',map=None,busy=False,deadline=time.monotonic()+240)
ue.EditorPythonScripting.set_keep_python_script_alive(True)


def finish(success):
    ue.unregister_slate_post_tick_callback(state['handle'])
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if success:ue.log('BRIGHTON_VIEWS_OK')


def daylight():
    clock=next((a for a in actors.get_all_level_actors() if isinstance(a,ue.PrologueTimeOfDay)),None)
    if not clock:return
    sun=clock.get_editor_property('sun')
    sun.set_actor_rotation(ue.Rotator(pitch=-46,yaw=316),False)
    sun.get_component_by_class(ue.DirectionalLightComponent).set_intensity(3.5)
    sun.get_component_by_class(ue.DirectionalLightComponent).set_light_color(ue.LinearColor(1,.95,.86,1))
    dome=clock.get_editor_property('sky_dome')
    if dome:
        sky=dome.get_component_by_class(ue.StaticMeshComponent).create_dynamic_material_instance(0)
        sky.set_vector_parameter_value('HorizonTint',ue.LinearColor(.60,.73,.91,1))
        sky.set_vector_parameter_value('ZenithTint',ue.LinearColor(.106,.31,.67,1))
    ambient=clock.get_editor_property('ambient_sky').get_component_by_class(ue.SkyLightComponent)
    ambient.set_intensity(1.2)
    ambient.set_light_color(ue.LinearColor(.85,.91,1,1))
    ambient.recapture_sky()


def import_views():
    from shutil import copy2
    changed=(('Grocery','Resources/ActOne/Transitions/T_Act_BrightonGrocery.png','/Game/Story/ActOne/Art'),
             ('Apartment','Resources/Presentation/T_Transition_Apartment.png','/Game/Prologue/Street/Transitions'),
             ('Street','Resources/Presentation/T_Transition_Neptune.png','/Game/Prologue/Street/Transitions'))
    if quarter:
        changed=(*changed[1:],('Precinct','Resources/Presentation/T_Transition_Precinct.png','/Game/Prologue/Street/Transitions'))
    if repair:
        changed=(('Street','Resources/Presentation/T_Transition_Neptune.png','/Game/Prologue/Street/Transitions'),)
    for name,destination,folder in changed:
        file=project/destination
        copy2(reviews/(name+'.png'),file)
        task=ue.AssetImportTask()
        task.set_editor_properties(dict(filename=str(file),destination_path=folder,destination_name=file.stem,
                                        automated=True,save=False,replace_existing=True))
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        image=ue.load_asset(folder+'/'+file.stem)
        image.set_editor_properties(dict(lod_group=ue.TextureGroup.TEXTUREGROUP_UI,
            mip_gen_settings=ue.TextureMipGenSettings.TMGS_NO_MIPMAPS,never_stream=True))
        assert ue.get_editor_subsystem(ue.EditorAssetSubsystem).save_loaded_asset(image,False)


def tick(delta):
    if state['busy']:return
    state['busy']=True
    try:
        assert time.monotonic()<state['deadline'],state
        if state['index']==len(shots):
            import_views()
            finish(True)
            return
        name,title,position,target,field=shots[state['index']]
        if state['stage']=='open':
            changed=state['map']!=name
            if changed:
                assert levels.load_level('/Game/Locations/'+name),name
                state['map']=name
                if name!='L_BrightonGrocery':daylight()
                for character in actors.get_all_level_actors():
                    if isinstance(character,ue.ActOneCast):
                        mesh=character.get_editor_property('character_mesh')
                        if mesh.get_editor_property('skeletal_mesh_asset'):
                            mesh.set_update_animation_in_editor(True)
            if repair and title=='Street':
                entrance, = [a for a in actors.get_all_level_actors() if a.actor_has_tag('FromApartment')]
                normal=entrance.get_actor_forward_vector()
                at=entrance.get_actor_location()+normal*8+ue.Vector(0,0,59)
                position=at.to_tuple()
                target=(at+normal*1800).to_tuple()
            elif position is None:
                sign=next(a for a in actors.get_all_level_actors()
                          if a.actor_has_tag('SignText:4-я БРАЙТОН-БИЧ / 4th Brighton beach'))
                center,extent=sign.get_actor_bounds(False)
                normal=ue.MathLibrary.get_right_vector(sign.get_actor_rotation())
                at=center+normal*max(180,max(extent.x,extent.y)*3.3)
                position=(at.x,at.y,at.z)
                target=(center.x,center.y,center.z)
            angle=ue.MathLibrary.find_look_at_rotation(ue.Vector(*position),ue.Vector(*target))
            camera=actors.spawn_actor_from_class(ue.SceneCapture2D,ue.Vector(*position),angle)
            capture=camera.get_component_by_class(ue.SceneCaptureComponent2D)
            image_format=ue.TextureRenderTargetFormat.RTF_RGBA8_SRGB if quarter or repair else ue.TextureRenderTargetFormat.RTF_RGBA8
            render=ue.RenderingLibrary.create_render_target2d(editor.get_editor_world(),1280,720,image_format)
            capture.set_editor_properties(dict(texture_target=render,fov_angle=field,
                capture_source=ue.SceneCaptureSource.SCS_FINAL_COLOR_LDR,capture_every_frame=False,capture_on_movement=False))
            # Match the editor photo pass exposure; no gameplay light or map is saved here.
            post=capture.get_editor_property('post_process_settings')
            post.set_editor_properties(dict(override_auto_exposure_bias=True,auto_exposure_bias=2.0))
            capture.set_editor_property('post_process_settings',post)
            state.update(camera=camera,render=render,stage='capture',at=time.monotonic()+(4 if changed else .8))
        elif state['stage']=='capture' and time.monotonic()>=state['at']:
            state['camera'].get_component_by_class(ue.SceneCaptureComponent2D).capture_scene()
            state.update(stage='export',at=time.monotonic()+.35)
        elif state['stage']=='export' and time.monotonic()>=state['at']:
            ue.RenderingLibrary.export_render_target(editor.get_editor_world(),state['render'],str(reviews),title+'.png')
            assert (reviews/(title+'.png')).is_file(),title
            actors.destroy_actor(state.pop('camera'))
            del state['render']
            ue.log('BRIGHTON_VIEW '+title)
            state.update(index=state['index']+1,stage='open')
    except Exception:
        ue.log_error('BRIGHTON_VIEWS_FAILED '+traceback.format_exc())
        finish(False)
    finally:state['busy']=False


state['handle']=ue.register_slate_post_tick_callback(tick)
