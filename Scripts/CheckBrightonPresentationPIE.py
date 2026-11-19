"""Exercise the new presentation against real PIE movement, weather, UI and map travel."""
from pathlib import Path
import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
# Reuse the established scenario helpers without launching their three-route runner.
helpers=(project/'Scripts/CheckActOnePIE.py').read_text(encoding='utf-8')
exec(compile(helpers.rsplit('\nassert levels.load_level',1)[0],str(project/'Scripts/CheckActOnePIE.py'),'exec'))
reviews=root/'Saved/Reviews/Brighton012'
reviews.mkdir(parents=True,exist_ok=True)
state['deadline']=time.monotonic()+180
assert ue.ExplorationHUDLibrary.validate_exploration_hud()


def environment():
    return ue.GameplayStatics.get_actor_of_class(world(),ue.ActOneDirector).get_editor_property('environment')


def walk(direction,seconds):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        pawn().add_movement_input(ue.Vector(*direction),1,False)
        yield
    pawn().get_component_by_class(ue.CharacterMovementComponent).stop_movement_immediately()


def capture_hud(name):
    yield from wait(lambda: ue.WidgetLibrary.get_all_widgets_of_class(world(),ue.ExplorationOverlayWidget,True),'Exploration overlay')
    overlay=ue.WidgetLibrary.get_all_widgets_of_class(world(),ue.ExplorationOverlayWidget,True)[0]
    for _ in range(3):
        assert ue.ActOneBlueprintLibrary.capture_editor_widget(overlay,str(reviews/(name+'.png')))
        yield from pause(.08)


def capture_rain():
    photo=reviews/'RainPIE.png'
    photo.unlink(missing_ok=True)
    position=ue.GameplayStatics.get_player_camera_manager(world(),0).get_camera_location()
    pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(position,position+ue.Vector(0,-700,-125)))
    yield from pause(.2)
    # Address the game viewport; AutomationLibrary screenshots address the editor viewport.
    ue.SystemLibrary.execute_console_command(world(),'HighResShot 1280x720 filename="'+str(photo)+'"',pc())
    yield from wait(photo.is_file,'Game viewport rain screenshot',12)


def run_presentation():
    say_step('presentation: report, music, movement guide and paper HUD')
    scenario=ue.load_asset('/Game/Story/DimaApartment/DA_DimaApartmentScenario')
    assert scenario.get_editor_property('ambient').get_name()=='S_DimaApartmentAmbient'
    assert scenario.get_editor_property('ambient').get_editor_property('looping')
    hud().call_method('ReceiveDrawHUD',(1280,720))
    assert hud().get_editor_property('State')==9
    hud().call_method('FinishReport')
    yield from wait(lambda: not pc().is_move_input_ignored() and pc().get_view_target()==pawn(),'Standing at the desk')
    yield from pause(.7)
    guide=hud().get_component_by_class(ue.ExplorationHUDComponent)
    assert not guide.is_tutorial_complete()
    yield from capture_hud('ApartmentHUD')
    place((-230,-321,100),0)
    yield from pause(.25)
    previous=environment().get_footstep_count()
    yield from walk((1,0,0),1.8)
    assert environment().get_footstep_count()>previous,'Apartment footsteps did not play'
    assert str(environment().get_last_footstep_surface())=='Wood',environment().get_last_footstep_surface()
    previous=environment().get_footstep_count()
    yield from pause(.4)
    assert environment().get_footstep_count()==previous,'Footsteps while stationary'
    game_key('J',True)
    yield from pause(.1)
    game_key('J',False)
    assert pc().is_move_input_ignored() and pc().get_editor_property('show_mouse_cursor')
    for key in ('W','A','S','D','SpaceBar','LeftShift'):
        game_key(key,True)
        yield from pause(.04)
        game_key(key,False)
    assert not guide.is_tutorial_complete(),'Journal input counted towards movement training'
    assert ue.ActOneBlueprintLibrary.send_editor_key('J')
    yield from pause(.12)
    assert not pc().is_move_input_ignored(),'Journal did not release movement'
    for key in ('W','A','S','D','SpaceBar','RightShift'):
        game_key(key,True)
        yield from pause(.08)
        game_key(key,False)
        yield from pause(.04)
    yield from capture_hud('ApartmentHUDAfterTraining')
    assert guide.is_tutorial_complete(),'The six movement actions did not complete training'
    del guide
    story_try=ue.DimaApartmentStoryLibrary.try_interact
    for tag in ('Wardrobe','Television','FloorLamp'):
        story_try(hud(),tag)
        yield from wait(windows,'Inspection '+tag)
        previous=environment().get_footstep_count()
        yield from pause(.15)
        assert environment().get_footstep_count()==previous,'Footsteps during dialogue'
        yield from page()
    assert not story_try(hud(),'FridgeDoor')
    hud().call_method('ActivateFridgeDoor')
    yield from page()
    story_try(hud(),'Tap')
    yield from page()
    story_try(hud(),'Phone')
    for _ in range(9):yield from page()
    place((-194,-330,98),-90)
    yield from pause(.3)
    hud().call_method('ReceiveDrawHUD',(1280,720))
    game_key('E',True)
    yield from pause(.08)
    game_key('E',False)
    yield from travel(street,'FromApartment')
    say_step('presentation: street footsteps, side quests and background boundary')
    assert len(act().optional_objectives())==3
    place((-2000,-1425,90),0)
    yield from pause(.25)
    previous=environment().get_footstep_count()
    yield from walk((1,0,0),1.7)
    assert environment().get_footstep_count()>previous,'Dry street footsteps did not play'
    assert str(environment().get_last_footstep_surface())=='Asphalt'
    yield from capture_hud('StreetHUD')
    place((-6570,-1425,90),180)
    yield from pause(.2)
    yield from walk((-1,0,0),1.5)
    assert pawn().get_actor_location().x>-6735,'The city continuation opened the playable boundary'
    say_step('presentation: detailed rain, wetness and wet footsteps')
    place((-2780,-1770,90),-90)
    director=ue.GameplayStatics.get_actor_of_class(world(),ue.ActOneDirector)
    director.set_rain(True)
    yield from wait(lambda: environment().get_wetness()>.9,'Wet pavement',10)
    assert director.get_editor_property('rain').get_instance_count()==480
    assert director.get_editor_property('rain_splashes').get_instance_count()==72
    previous=environment().get_footstep_count()
    yield from walk((1,0,0),1.7)
    assert environment().get_footstep_count()>previous
    assert str(environment().get_last_footstep_surface())=='Wet'
    yield from capture_rain()
    director.set_rain(False)
    assert director.get_editor_property('rain').get_instance_count()==0
    assert director.get_editor_property('rain_splashes').get_instance_count()==0
    del director
    say_step('presentation: stocked grocery, real cash register and tiled footsteps')
    use(action.GROCERY,(0,133))
    yield from travel('L_BrightonGrocery','ActEntry')
    groups=[a for a in ue.GameplayStatics.get_all_actors_of_class(world(),ue.StreetMeshInstances)
            if a.actor_has_tag('BrightonUpgrade_v1')]
    assert sum(a.get_editor_property('instances').get_instance_count() for a in groups)==155
    for name in ('green_can_obj','soda_bottle_obj','chocolate_bar_obj'):
        assert any(name in a.get_editor_property('instances').static_mesh.get_name() for a in groups),name
    register=next(a for a in ue.GameplayStatics.get_all_actors_of_class(world(),ue.StaticMeshActor)
                  if a.get_component_by_class(ue.StaticMeshComponent).static_mesh and
                  a.get_component_by_class(ue.StaticMeshComponent).static_mesh.get_name()=='SM_cash_register_obj')
    mesh=register.get_component_by_class(ue.StaticMeshComponent)
    assert mesh.get_num_materials()==13
    assert all(mesh.get_material(i) and 'WorldGrid' not in mesh.get_material(i).get_name() for i in range(13))
    del register,mesh,groups
    place((-410,-80,100),0)
    yield from pause(.25)
    previous=environment().get_footstep_count()
    yield from walk((1,0,0),1.5)
    assert environment().get_footstep_count()>previous
    assert str(environment().get_last_footstep_surface())=='Tile'
    yield from physical_use(action.CIGARETTES,(-132,0))
    yield from travel(street,'FromGrocery')
    yield from pages('DispatchBar','Disposition')
    assert act().get_phase()==phase.BAR_CALL
    ue.log('BRIGHTON_PRESENTATION_PIE_OK: music, four footstep surfaces, tutorial and journal, paper HUD, rain, boundary, stocked grocery and travel')


assert levels.load_level('/Game/Locations/'+apartment)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state['run']=run_presentation()
state['handle']=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
