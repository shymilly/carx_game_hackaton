"""Play all Act One routes against real maps, Blueprint HUD and shared Slate documents."""
from pathlib import Path
import json
from math import hypot
import time
import traceback

import unreal as ue


levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
spec = json.loads((root/'Docs/Scenario/ActOne.json').read_text(encoding='utf-8'))
state = dict(busy=False, deadline=time.monotonic()+295)
apartment = 'L_DimaApartmentInterior'
street = 'L_NeptuneStreet'
phase = ue.ActOnePhase
action = ue.ActOneAction


def world():
    return editor.get_game_world()


def pc():
    return ue.GameplayStatics.get_player_controller(world(), 0)


def game_key(key,pressed):
    assert ue.ActOneBlueprintLibrary.send_editor_game_key(pc(),key,pressed),key


def pawn():
    return ue.GameplayStatics.get_player_pawn(world(), 0)


def hud():
    return pc().get_hud()


def subsystem(cls):
    instance = ue.GameplayStatics.get_game_instance(world())
    return next(obj for obj in ue.ObjectIterator(cls) if obj.get_outer() == instance)


def ui():
    return subsystem(ue.NarrativeSubsystem)


def act():
    return subsystem(ue.ActOneSubsystem)


def locate(name):
    return ue.GameplayStatics.get_current_level_name(world(), True) == name


def windows():
    return ue.WidgetLibrary.get_all_widgets_of_class(world(), ue.DocumentWindow, True)


def say_step(name):
    state['step'] = name
    ue.log('ACT_STEP '+name)


def wait(predicate, name, seconds=12):
    deadline = time.monotonic()+seconds
    while not predicate():
        assert time.monotonic() < deadline, name
        yield


def pause(seconds):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        yield


def page(key=None, choice=None, count=None):
    yield from wait(lambda:len(windows())==1,'Expected shared document '+str(key))
    active = windows()
    assert len(active) == 1, len(active)
    window = active[0]
    document = window.get_editor_property('document')
    if key:
        assert document.get_name() == 'D_'+key, (document.get_name(), key)
    assert pc().is_move_input_ignored() and pc().is_look_input_ignored(), key
    if count is not None:
        assert window.get_choice_count() == count, (key, window.get_choice_count(), count)
    if choice is None:
        window.request_close()
    else:
        assert window.choose_option(choice), (key, choice)
    yield


def pages(*keys):
    for key in keys:
        yield from page(key)


def place(position, facing=None, sweep=False):
    character = pawn()
    character.get_component_by_class(ue.CharacterMovementComponent).stop_movement_immediately()
    character.set_actor_location(ue.Vector(*position), sweep, True)
    if facing is not None:
        pc().set_control_rotation(ue.Rotator(yaw=facing))
    return character.get_actor_location()


def target(which):
    if isinstance(which,str):
        objects = ue.GameplayStatics.get_all_actors_with_tag(world(), which)
    else:
        objects = [item for item in ue.GameplayStatics.get_all_actors_of_class(world(), ue.ActOneInteraction)
                   if item.get_editor_property('action') == which]
    assert len(objects) == 1, (which, len(objects))
    return objects[0]


def reach(which, offset):
    point = target(which).get_actor_location()
    place((point.x+offset[0], point.y+offset[1], 100))
    return point


def use(which, offset=(-100,0)):
    reach(which,offset)
    assert ue.StreetNavigationLibrary.enter_portal(hud(), target(which)), which


def physical_use(which, offset):
    point = reach(which, offset)
    yield from look_and_use(which,point)


def look_and_use(which,point):
    yield from pause(.17)
    camera = ue.GameplayStatics.get_player_camera_manager(world(),0).get_camera_location()
    pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(camera,point))
    yield from pause(.17)
    hud().call_method('ReceiveDrawHUD',(1280,720))
    assert str(hud().get_editor_property('Focus')) == 'StreetPortal', (which,hud().get_editor_property('Focus'))
    if which==action.PISTOL:
        folder=root/'Saved/Reviews/Brighton014'
        folder.mkdir(parents=True,exist_ok=True)
        picture=folder/'PistolInGame.png'
        picture.unlink(missing_ok=True)
        ue.SystemLibrary.execute_console_command(world(),'HighResShot 1280x720 filename="'+str(picture)+'"',pc())
        yield from wait(picture.is_file,'Pistol on the desk',5)
    game_key('E',True)
    yield from pause(.09)
    game_key('E',False)
    yield


def check_journal():
    catalog = ue.load_asset('/Game/UI/Journal/DA_JournalCatalog')
    slots = {str(entry.get_editor_property('discovery_flag')): index
             for index, entry in enumerate(catalog.get_editor_property('entries'))}
    game_key('J',True)
    yield from pause(.12)
    game_key('J',False)
    assert pc().get_editor_property('show_mouse_cursor') and pc().is_move_input_ignored(),(
        hud().get_editor_property('JournalOpen'),hud().get_editor_property('JournalHeld'),
        pc().get_editor_property('show_mouse_cursor'),pc().is_move_input_ignored())
    presenter = hud().get_component_by_class(ue.JournalPresenterComponent)
    entries = presenter.visible_entries()
    assert slots['BrightonNewspaper'] in entries and slots['FedorTape'] not in entries
    presenter.select_entry(slots['BrightonNewspaper'])
    selection = ue.WidgetLibrary.get_all_widgets_of_class(world(),ue.DocumentWindow,False)
    assert any(w.get_editor_property('document') and
               w.get_editor_property('document').get_name() == 'D_BrightonNewspaper' for w in selection)
    assert ue.ActOneBlueprintLibrary.send_editor_key('J')
    assert not pc().is_move_input_ignored()


def arrival(name, tag, exact=True):
    yield from wait(lambda: locate(name) and not ui().is_location_transition_active(), 'Arrival '+name)
    if exact:
        assert ue.LocationTravelLibrary.was_last_arrival_exact(pc()), (name,tag)
        assert ue.LocationTravelLibrary.is_arrival_point_safe(pc(), tag), (name,tag)
    ue.log('ACT_ONE_ARRIVED '+name+' '+tag)


def travel(name, tag):
    expected = {'L_DimaApartmentInterior':'Apartment','L_NeptuneStreet':'Neptune','L_PolicePrecinct':'Precinct'}
    texture = 'T_Transition_'+expected[name] if name in expected else 'T_Act_'+name.removeprefix('L_')
    assert ui().is_location_transition_active() and ui().get_location_photo().get_name()==texture,(name,tag)
    assert pc().is_move_input_ignored() and pc().is_look_input_ignored()
    yield from arrival(name,tag)


def beginning(pistol):
    say_step('1 report, five inspections and nine phone pages')
    hud().call_method('ReceiveDrawHUD',(1280,720))
    assert hud().get_editor_property('State') == 9
    yield from wait(windows,'Opening report window')
    assert ue.ActOneBlueprintLibrary.send_editor_key('E'), 'E completes the opening report'
    yield from wait(lambda: hud().get_component_by_class(ue.DimaApartmentStoryComponent).get_phase() ==
                    ue.DimaApartmentPhase.EXPLORING and not pc().is_move_input_ignored(), 'Stand up from the desk')
    yield from pause(.65)
    story_try = ue.DimaApartmentStoryLibrary.try_interact
    story_try(hud(),'StreetDoor')
    assert not ui().is_location_transition_active()
    for tag in ('Wardrobe','Television','FloorLamp'):
        story_try(hud(),tag)
        yield from page()
    assert not story_try(hud(),'FridgeDoor')
    hud().call_method('ActivateFridgeDoor')
    yield from page()
    story_try(hud(),'Tap')
    assert pc().is_move_input_ignored(), 'Wash input was not locked'
    yield from page()
    story_try(hud(),'Phone')
    for _ in range(9):
        yield from page()
    assert str(ue.DimaApartmentStoryLibrary.objective(hud(),'')) == 'Выйти на улицу'
    if pistol:
        yield from physical_use(action.PISTOL,(82,-92))
        yield from page('Pistol')
        assert act().has_pistol()
    place((-194,-330,98),-90)
    yield from pause(.3)
    hud().call_method('ReceiveDrawHUD',(1280,720))
    assert str(hud().get_editor_property('Focus')) == 'StreetDoor'
    game_key('E',True)
    yield from pause(.08)
    game_key('E',False)
    yield from travel(street,'FromApartment')
    assert act().get_phase() == phase.CIGARETTES


def brighton(alt,tear_seal):
    say_step('2 street, newspaper, payphone, veteran and grocery')
    assert str(ue.DimaApartmentStoryLibrary.objective(hud(),'')) == 'Купить сигареты'
    use('ActPrecinctEntry')
    assert not ui().is_location_transition_active()
    assert not target(action.NEWSPAPER).get_actor_enable_collision()
    use(action.PRESS,(0,105))
    yield from page('Vendor')
    use(action.NEWSPAPER,(0,91))
    yield from wait(windows, 'Newspaper widget')
    news = windows()[0].get_editor_property('document')
    assert news.get_editor_property('layout') == ue.DocumentLayout.NEWSPAPER
    articles = news.get_editor_property('articles')
    expected = spec['documents']['BrightonNewspaper']['articles']
    assert [str(article.get_editor_property('text')) for article in articles] == [entry['text'] for entry in expected]
    if not alt and not tear_seal:
        path=root/'Saved/ActOne/Newspaper.png'
        assert ue.ActOneBlueprintLibrary.capture_editor_document(windows()[0],str(path))
    yield from page('BrightonNewspaper')
    assert act().has_evidence('BrightonNewspaper')
    yield from check_journal()
    use(action.PAY_PHONE,(0,-100))
    yield from page('PayPhone',1 if alt else 0,2)
    assert pc().is_move_input_ignored()
    yield from page('NoConnection')
    assert act().has_evidence('MotherCall' if alt else 'LizaCall')
    use(action.VETERAN)
    yield from page('VeteranAsk',2 if alt else 1 if tear_seal else 0,3)
    if not alt:
        yield from page('VeteranCurse' if tear_seal else 'VeteranThanks')
    assert act().get_statistics().get_editor_property('heritage') == (0 if alt or tear_seal else 1)
    use(action.BAR)
    assert not ui().is_location_transition_active()
    yield from physical_use(action.GROCERY,(0,133))
    yield from travel('L_BrightonGrocery','ActEntry')
    yield from physical_use(action.CIGARETTES,(-132,0))
    yield from travel(street,'FromGrocery')
    director=ue.GameplayStatics.get_actor_of_class(world(),ue.ActOneDirector)
    yield from wait(lambda: director.get_component_by_class(ue.CigaretteSmokeComponent) and
                    director.get_component_by_class(ue.CigaretteSmokeComponent).is_visible(),'Dima cigarette smoke',2)
    yield from pages('DispatchBar','Disposition')
    assert act().get_statistics().get_editor_property('calm') == 1
    use(action.BAR)
    yield from travel('L_LighthouseBar','ActEntry')


def conflict(alt):
    say_step('3 bar, '+('force and pistol' if alt else 'dialogue, QTE failure and success'))
    use(action.GUARD)
    yield from page('BarChoice',1 if alt else 0,2)
    if alt:
        yield from page('BarGun',1,2)
        camera=target('ActCue:BarShotCamera')
        yield from wait(lambda: pc().get_view_target()==camera,'Cut to the shot')
        shooter=target('ActCue:BarDima')
        prop=target('ActCue:BarShotProp')
        assert prop.get_attach_parent_actor()==shooter and str(prop.get_attach_parent_socket_name())=='BarPistolGrip'
        assert not shooter.get_editor_property('hidden') and pawn().get_editor_property('hidden')
        shot=shooter.get_editor_property('character_mesh').get_anim_instance()
        authored=shooter.get_editor_property('character_profile').get_editor_property('motions')
        assert isinstance(shot,ue.CityClipInstance) and abs(shot.get_length()-authored[ue.Name('Shot')].get_play_length())<.001
        chamber=root/'Saved/Reviews/Brighton014'
        chamber.mkdir(parents=True,exist_ok=True)
        yield from wait(lambda: shooter.get_editor_property('character_mesh').get_position()>.32,'Dima raises his arm')
        aim=chamber/'BarAim.png'
        aim.unlink(missing_ok=True)
        ue.SystemLibrary.execute_console_command(world(),'HighResShot 1280x720 filename="'+str(aim)+'"',pc())
        yield from wait(aim.is_file,'Capture the gesture',5)
        yield from wait(lambda: act().was_guard_killed(),'Shot reaches the guard')
        loose=target('ActCue:DroppedWeapon')
        assert loose.get_actor_location().z>40, 'Weapon should fall from the hand'
        guard=target('ActCue:BarGuard')
        fall=guard.get_editor_property('character_profile').get_editor_property('motions')[ue.Name('Fall')]
        fallen=guard.get_editor_property('character_mesh').get_anim_instance()
        assert 'Death' in fall.get_name() and abs(fallen.get_length()-fall.get_play_length())<.001
        for delay,name in ((0,'BarShot'),(.78,'BarFall')):
            yield from pause(delay)
            image=chamber/(name+'.png')
            image.unlink(missing_ok=True)
            ue.SystemLibrary.execute_console_command(world(),'HighResShot 1280x720 filename="'+str(image)+'"',pc())
            yield from wait(image.is_file,'Capture '+name,5)
        assert loose.get_actor_location().z<12, 'Dropped prop should have landed'
    else:
        yield from pages('GuardTaunt','DimaBarReply','GuardEnglish')
        yield from page('BarGun',0,1)
        assert ue.ActOneBlueprintLibrary.send_editor_key('F')
        yield from page('DisarmRetry')
        yield from page('BarGun',0,1)
        for expected, key in enumerate(('Q','E','F'),1):
            assert ue.ActOneBlueprintLibrary.send_editor_key(key), key
            assert act().get_challenge_step() == expected
        yield from page('OldManThanks')
    yield from page('DispatchPrecinct')
    assert act().get_phase() == phase.PRECINCT
    assert act().was_guard_killed() == alt
    assert not pawn().get_editor_property('hidden')
    stats = act().get_statistics()
    assert stats.get_editor_property('anger') == (35 if alt else 0)
    assert stats.get_editor_property('neighborhood') == (-1 if alt else 0)
    use(action.LEAVE_BAR,(95,0))
    yield from travel(street,'FromBar')
    use('ActPrecinctEntry')
    yield from travel('L_PolicePrecinct','FromStreet')


def precinct(alt,tear_seal):
    say_step('4 precinct, three conversations with Krill and Ivan at the door')
    use(action.MISSING,(100,0))
    yield from page('FedorMissing')
    assert act().has_evidence('FedorMissing')
    resource = target(action.OFFICE).get_actor_location()
    yield from physical_use(action.OFFICE,(0,-124))
    yield from pause(.58)
    assert place((resource.x,resource.y+120,99),sweep=True).y > resource.y+80, 'Captain office opening blocks the player'
    use(action.CAPTAIN,(0,-111))
    yield from page('CaptainNews',2 if alt else 1 if tear_seal else 0,3)
    if not alt:
        yield from page('CaptainReply02' if tear_seal else 'CaptainReply01')
    yield from page('CaptainKGB',2 if alt else 1 if tear_seal else 0,3)
    if alt:
        yield from pages('CaptainSearch','CaptainSearchReply')
    elif tear_seal:
        yield from pages('CaptainInfo','CaptainInfoReply')
    else:
        yield from page('CaptainAnger')
    yield from page('CaptainOffer',2 if alt else 1 if tear_seal else 0,3)
    if alt:
        yield from page('CaptainFather')
    yield from page('CaptainWarning')
    assert act().has_archive_access() == (not alt and not tear_seal)
    if not alt and not tear_seal:
        use(action.ARCHIVES,(0,-101))
        yield from page('AegisArchive')
        use(action.TRAINING)
        yield from page('LockTraining')
        assert act().has_lockpick_training()
    use('ActPrecinctExit')
    yield from travel(street,'FromPrecinct')
    use(action.IVAN_STREET,(133,0))
    yield from pages('IvanStreet01','IvanStreet02','IvanStreet03')
    yield from page('IvanKeyOffer',0 if alt else 1,2)
    assert act().has_act_key() == alt
    use(action.RIDE,(104,0))
    yield from travel('L_FedorEntry','ActEntry')


def fedor(alt,tear_seal):
    entry = 'remove seal' if tear_seal else 'Ivan’s key' if alt else 'lock timing'
    say_step('5 '+entry+', four clues, pursuit and automatic credits')
    assert not ue.GameplayStatics.get_all_actors_with_tag(world(),'ActCue:Patrol')
    yield from physical_use(action.BUILDING_ENTRY,(-115,0))
    yield from pause(.73)
    travel_limit=time.monotonic()+26
    for floor in range(3):
        for x,y in ((604,0),(604,-91),(955,-91),(955,64),(600,64)):
            yield from walk_to(x,y,travel_limit,17)
        assert pawn().get_actor_location().z>(floor+1)*270+62,(floor,pawn().get_actor_location())
    yield from walk_to(602,40,travel_limit,14)
    pawn().get_component_by_class(ue.CharacterMovementComponent).stop_movement_immediately()
    assert abs(target(action.SEAL).get_actor_location().z-919)<.5
    ue.log('FEDOR_STAIRS_PLAY_OK entry door opened with E and all six flights climbed on foot')
    yield from look_and_use(action.SEAL,target(action.SEAL).get_actor_location())
    if tear_seal:
        yield from page('SealDoor',0,1)
    else:
        yield from page('SealDoor',1,2)
    if not alt and not tear_seal:
        assert ue.ActOneBlueprintLibrary.send_editor_key('SpaceBar')
        yield from page('LockRetry')
        yield from page('SealDoor',1,2)
        for step in range(3):
            yield from wait(lambda: abs(act().get_challenge_position()-act().get_challenge_target()) < .05,'Lock pulse',5)
            assert ue.ActOneBlueprintLibrary.send_editor_key('SpaceBar')
            assert act().get_challenge_step() == step+1
    yield from wait(lambda: ui().is_location_transition_active(), 'Opening the sealed door')
    yield from travel('L_FedorApartment','ActEntry')
    assert not act().is_alarmed()
    assert not target(action.IVAN_FEDOR).get_actor_enable_collision()
    ivan=target('ActCue:IvanFedor')
    listener=target('ActCue:FedorListener')
    outside=listener.get_actor_location()
    assert ivan.get_editor_property('character_profile').get_name()=='DA_Ivan'
    assert listener.get_editor_property('character_profile').get_name()=='DA_Agent'
    assert ivan.get_editor_property('hidden') and outside.x<-529 and listener.get_editor_property('hidden')
    assert not listener.get_actor_enable_collision()
    use(action.FLOORBOARD)
    use(action.FOLDER)
    yield from page('FedorFolder')
    use(action.TAPE,(0,100))
    yield from page('FedorTape')
    use(action.PHOTOGRAPH,(0,100))
    yield from page('FedorPhoto')
    use(action.DRAWER)
    use(action.DESK_BADGE)
    yield from page('FedorBadge')
    yield from wait(lambda:target(action.IVAN_FEDOR).get_actor_enable_collision(),'Ivan walks in',6)
    assert ivan.get_actor_location().x>-500
    assert (listener.get_actor_location()-outside).length()<2
    use(action.IVAN_FEDOR,(104,0))
    yield from page('IvanFedor')
    assert listener.get_editor_property('hidden')
    yield from page('FedorWho')
    assert act().has_evidence('BankKey')
    yield from wait(lambda:listener.get_editor_property('hidden'),'The listener runs away',5)
    assert (listener.get_actor_location()-outside).length()>180 and not ivan.get_editor_property('hidden')
    assert ivan.get_actor_location().x>-500
    ue.log('FEDOR_ROLES_PLAY_OK Ivan enters and remains inside while the listener runs down the hallway')
    use(action.LEAVE_FEDOR,(100,0))
    yield from travel('L_BrightonAlley','ActEntry')
    assert not target(action.CHASE_BADGE).get_actor_enable_collision()
    agent = target('ActCue:Agent')
    if tear_seal:
        # Let the agent leave while Dima stands still, then verify the stumble and badge below.
        yield from wait(lambda:act().is_pursuit_finished(),'Agent runs out of sight on his own',24)
        ue.log('CHASE_AGENT_ESCAPED_WHILE_PLAYER_WAITED')
    else:
        starting_point = agent.get_actor_location()
        yield from pause(2.3)
        assert agent.get_actor_location().distance(starting_point)>675, 'The agent stopped to wait for Dima'
    game_key('LeftShift',True)
    route_end=time.monotonic()+32
    director=ue.GameplayStatics.get_actor_of_class(world(),ue.ActOneDirector)
    saw_fall=False
    for x,y in ((1017,0),(1017,822),(2190,822),(2190,1620),(3330,1620)):
        while True:
            current=pawn().get_actor_location()
            dx,dy=x-current.x,y-current.y
            distance=hypot(dx,dy)
            if distance<28:break
            assert time.monotonic()<route_end,('Physical pursuit route blocked',current,x,y)
            if director.is_pursuit_trip_playing() and not saw_fall:
                saw_fall=True
                assert x==2190 and y==1620 and current.y<1550,current
                yield from pause(.61)
                view=pc().get_view_target()
                arms=next(c for c in view.get_components_by_class(ue.SkeletalMeshComponent) if c.get_name()=='FirstPersonTripArms')
                assert arms.get_position()>.43 and arms.is_playing()
                assert pc().is_move_input_ignored()
                assert ue.GameplayStatics.get_player_camera_manager(world(),0).get_camera_location().z<106
                yield from wait(lambda:not director.is_pursuit_trip_playing(),'Dima stands back up',5)
                assert not pc().is_move_input_ignored()
                continue
            pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(current,ue.Vector(x,y,current.z)))
            pawn().add_movement_input(ue.Vector(dx/distance,dy/distance,0),1,False)
            yield
    game_key('LeftShift',False)
    pawn().get_component_by_class(ue.CharacterMovementComponent).stop_movement_immediately()
    yield from wait(lambda: act().is_pursuit_finished(), 'Agent ran to the end of the route')
    assert saw_fall and agent.get_editor_property('hidden')
    escaped_at = agent.get_actor_location()
    assert escaped_at.x>4585 and escaped_at.y<1040,escaped_at
    ue.log('CHASE_TRIP_PLAY_OK Dima falls before the turn, recovers controls, then the badge is available')
    use(action.CHASE_BADGE,(84,0))
    yield from arrival(apartment,'FromFinale')
    yield from wait(windows,'Tape playback')
    assert windows()[0].get_editor_property('document').get_name() == 'D_FedorRecording'
    yield from wait(lambda: act().get_phase() == phase.COMPLETE, 'Automatic credits',20)
    assert windows()[0].get_editor_property('document').get_editor_property('layout') == ue.DocumentLayout.CREDITS
    assert act().has_evidence('BrightonNewspaper') and act().has_evidence('PursuitBadge')
    assert act().can_use_disposition(1,0,1,100)
    assert not act().can_use_disposition(2,0,100,100)


def walk_to(x,y,deadline,tolerance):
    while True:
        current=pawn().get_actor_location()
        dx,dy=x-current.x,y-current.y
        distance=hypot(dx,dy)
        if distance<tolerance:
            return
        assert time.monotonic()<deadline,('Stairwell movement blocked',current,x,y)
        pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(current,ue.Vector(x,y,current.z)))
        pawn().add_movement_input(ue.Vector(dx/distance,dy/distance,0),min(1,distance/44),False)
        yield


def run():
    for alternative,tear_seal in ((False,False),(True,False),(False,True)):
        yield from beginning(alternative)
        yield from brighton(alternative,tear_seal)
        yield from conflict(alternative)
        yield from precinct(alternative,tear_seal)
        yield from fedor(alternative,tear_seal)
        ue.log('ACT_ONE_ROUTE_OK '+('seal' if tear_seal else 'pistol/key' if alternative else 'QTE/lock'))
        windows()[0].request_close()
        yield from wait(lambda: act().get_phase() == phase.APARTMENT and hud().get_editor_property('State') == 9,
                        'Clean restart at report')
        assert not act().has_evidence('PursuitBadge')


def finish(success):
    ue.unregister_slate_post_tick_callback(state['handle'])
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if success:
        ue.log('ACT_ONE_PIE_OK')


def tick(_delta):
    if state['busy']:
        return
    state['busy'] = True
    try:
        assert time.monotonic() < state['deadline'], state.get('step')
        if not world() or not pc() or not hud() or not pawn():
            return
        if hud().get_editor_property('State') == -1:
            hud().call_method('ReceiveDrawHUD',(1280,720))
        next(state['run'])
    except StopIteration:
        finish(True)
    except Exception:
        ue.log_error('ACT_ONE_PIE_FAILED '+str(state.get('step'))+'\n'+traceback.format_exc())
        finish(False)
    finally:
        state['busy'] = False


assert levels.load_level('/Game/Locations/'+apartment)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state['run'] = run()
state['handle'] = ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
