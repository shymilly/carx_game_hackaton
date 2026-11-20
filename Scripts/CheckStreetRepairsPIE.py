"""First exit, both ends of the railway, and physical door interactions in Play."""
from pathlib import Path
import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
helpers=project/"Scripts/CheckActOnePIE.py"
exec(compile(helpers.read_text(encoding="utf-8").rsplit("\nassert levels.load_level",1)[0],str(helpers),"exec"))
reviews=project/"Saved/Reviews/Brighton0141"
reviews.mkdir(parents=True,exist_ok=True)
state["deadline"]=time.monotonic()+105


def picture(name):
    path=reviews/(name+".png")
    path.unlink(missing_ok=True)
    ue.SystemLibrary.execute_console_command(world(),'HighResShot 1280x720 filename="'+str(path)+'"',pc())
    yield from wait(path.is_file,"Capture "+name,6)
    ue.log("FIX_CAPTURE "+name)


def face(point):
    eye=ue.GameplayStatics.get_player_camera_manager(world(),0).get_camera_location()
    pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(eye,point))


def press_door(focus):
    hud().call_method("ReceiveDrawHUD",(1280,720))
    assert str(hud().get_editor_property("Focus"))==focus,(focus,hud().get_editor_property("Focus"))
    game_key("E",True)
    yield from pause(.07)
    game_key("E",False)


def run_repair():
    session_start=time.monotonic()
    captured=False
    for _ in beginning(False):
        if locate(apartment) and ui().is_location_transition_active():
            assert ui().get_location_photo().get_name()=="T_Transition_Neptune"
            captured=True
        yield
    assert captured
    assert locate(street) and ue.LocationTravelLibrary.was_last_arrival_exact(pc())
    assert len(ue.GameplayStatics.get_all_actors_with_tag(world(),"StreetArtPass_v1"))>=15
    assert abs(pc().get_control_rotation().yaw+68)<2
    yield from picture("FirstExit")
    ue.log("FIX_FIRST_EXIT_PASSED apartment -> /Game/Locations/L_NeptuneStreet with Street Art Pass actors")

    say_step("industrial train enters and leaves under cover")
    branch=next(a for a in ue.GameplayStatics.get_all_actors_of_class(world(),ue.CityRailTraffic)
                if a.get_editor_property("covered_ends"))
    engine=next(c for c in branch.get_components_by_class(ue.StaticMeshComponent)
                if c.static_mesh and c.static_mesh.get_name()=="SM_FreightEngine")
    assert not engine.is_visible()
    place((2900,-5230,90))
    yield from pause(.19)
    face(ue.Vector(2430,branch.get_actor_location().y,740))
    # Begin a pass during this short test. The saved geometry and cadence stay untouched.
    branch.set_editor_property("first_pass_delay",time.monotonic()-session_start+2)
    branch.set_editor_property("speed",1650.)
    yield from wait(branch.is_passing,"Train started below the western portal",9)
    assert not engine.is_visible()
    yield from wait(engine.is_visible,"Locomotive appears on the modeled track",4)
    assert -6850 < engine.get_world_location().x < -4950
    yield from wait(lambda: 2250<engine.get_world_location().x<3100,"Train reached the avenue",10)
    yield from picture("TrainCrossing")
    yield from wait(lambda: not engine.is_visible(),"Locomotive leaves under the eastern portal",16)
    assert engine.get_world_location().x>18200
    ue.log("FIX_TRAIN_PASSED")

    say_step("return to apartment, then open the kitchen and bathroom doors")
    place((-194,-560,93),90)
    yield from pause(.28)
    yield from press_door("StreetPortal")
    yield from travel(apartment,"FromStreet")
    for tag,x_offset in (("KitchenDoor",140),("BathDoor",-142)):
        door=target(tag)
        p=door.get_actor_location()
        place((p.x+x_offset,p.y,99))
        yield from pause(.18)
        face(p)
        yield from pause(.17)
        yield from press_door(tag)
        yield from wait(lambda: hud().get_editor_property(tag+"Progress")>.9,"Opened "+tag,2)
        assert hud().get_editor_property(tag+"Toggled")
    ue.log("FIX_GAMEPLAY_OK")


assert levels.load_level("/Game/Locations/"+apartment)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state["run"]=run_repair()
state["handle"]=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
