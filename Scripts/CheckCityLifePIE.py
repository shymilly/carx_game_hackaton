"""Check the new appearance, audio and timed train using the active gameplay maps."""
from pathlib import Path
import unreal as ue

project=Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
helpers=project/"Scripts/CheckActOnePIE.py"
exec(compile(helpers.read_text(encoding="utf-8").rsplit("\nassert levels.load_level",1)[0],str(helpers),"exec"))
reviews=root/"Saved/Reviews/Brighton014"
reviews.mkdir(parents=True,exist_ok=True)
state["deadline"]=time.monotonic()+200


def look(position, target_point):
    place(position)
    yield from pause(.18)
    camera=ue.GameplayStatics.get_player_camera_manager(world(),0).get_camera_location()
    pc().set_control_rotation(ue.MathLibrary.find_look_at_rotation(camera,ue.Vector(*target_point)))
    yield from pause(.28)


def photograph(label):
    file=reviews/(label+".png")
    if file.exists():
        file.unlink()
    ue.SystemLibrary.execute_console_command(world(),'HighResShot 1280x720 filename="'+str(file)+'"',pc())
    yield from wait(file.is_file,"Capture "+label,9)


def actor_of(cls):
    return ue.GameplayStatics.get_actor_of_class(world(),cls)


def dima_mesh():
    return next((m for m in pawn().get_components_by_class(ue.SkeletalMeshComponent)
                 if m.get_name()=="DimaStreetClothes"),None)


def run_life():
    say_step("City life: opening, updated player body and arrival on the street")
    yield from beginning(False)
    yield from wait(dima_mesh,"New player presentation")
    assert dima_mesh().get_editor_property("skeletal_mesh_asset").get_name()=="Smooth_Male_LongSleeve"
    old=[m for m in pawn().get_components_by_class(ue.SkeletalMeshComponent) if m!=dima_mesh()]
    assert all(not m.is_visible() for m in old)
    del old
    yield from look((-725,-695,93),(-728,-695,0))
    yield from photograph("DimaBody")
    yield from look((-720,-700,93),(-1510,-550,72))
    yield from photograph("DimaAndSidewalk")
    env=actor_of(ue.ActOneDirector).get_editor_property("environment")
    guide=hud().get_component_by_class(ue.ExplorationHUDComponent)
    assert not guide.should_show_tasks() and not guide.should_show_stamina()
    game_key("Q",True)
    yield from pause(.18)
    assert guide.should_show_tasks()
    game_key("Q",False)
    overlay,=ue.WidgetLibrary.get_all_widgets_of_class(world(),ue.ExplorationOverlayWidget,True)
    assert ue.ActOneBlueprintLibrary.capture_editor_widget(overlay,str(reviews/"StreetTasks.png"))
    game_key("Q",True)
    yield from pause(.09)
    game_key("Q",False)
    assert not guide.should_show_tasks()
    game_key("RightShift",True)
    yield from pause(.1)
    assert guide.should_show_stamina()
    game_key("RightShift",False)
    yield from pause(.1)
    assert not guide.should_show_stamina()
    camera=pawn().get_component_by_class(ue.CameraComponent)
    assert camera.get_attach_parent()==pawn().get_component_by_class(ue.CapsuleComponent)
    pc().set_control_rotation(ue.Rotator(yaw=180))
    before=env.get_footstep_count()
    game_key("LeftShift",True)
    sprint_samples=0
    start=time.monotonic()
    while time.monotonic()<start+1.35:
        pawn().add_movement_input(ue.Vector(-1,0,0),1,False)
        if pawn().get_velocity().length()>450:
            head=dima_mesh().get_socket_location("Head")
            depth=ue.Vector.dot(head-camera.get_world_location(),pawn().get_actor_forward_vector())
            assert depth<0,("Head crosses the camera during a stride",depth)
            sprint_samples+=1
        yield
    assert sprint_samples>=3 and guide.should_show_stamina(),sprint_samples
    assert env.get_footstep_count()>before, "Dry footsteps were silent"
    assert str(env.get_last_footstep_surface())=="Asphalt"
    hud_overlay=ue.WidgetLibrary.get_all_widgets_of_class(world(),ue.ExplorationOverlayWidget,True)
    assert len(hud_overlay)==1
    for _ in range(3):
        assert ue.ActOneBlueprintLibrary.capture_editor_widget(hud_overlay[0],str(reviews/"StaminaHUD.png"))
        yield from pause(.04)
    game_key("LeftShift",False)
    yield from pause(.10)
    assert not guide.should_show_stamina()

    say_step("City life: two talking neighbors and a smoker")
    crowd=[a for a in ue.GameplayStatics.get_all_actors_of_class(world(),ue.ActOneCast)
           if a.actor_has_tag("CityLifeDressing")]
    assert len(crowd)==3
    yield from look((770,-885,86),(770,-620,127))
    walkers=[a.get_editor_property("character_mesh") for a in crowd
             if a.get_editor_property("default_pose")==ue.ActOnePose.CONVERSING]
    assert len(walkers)==2
    first=[mesh.get_position() for mesh in walkers]
    yield from pause(.48)
    assert all(abs(mesh.get_position()-at)>.05 for mesh,at in zip(walkers,first))
    yield from photograph("Neighbors")
    yield from look((-1400,-718,88),(-1203,-480,144))
    smoker=next(a for a in crowd if a.get_editor_property("default_pose")==ue.ActOnePose.SMOKING)
    smoker_mesh=smoker.get_editor_property("character_mesh")
    assert smoker_mesh.get_editor_property("skeletal_mesh_asset")
    yield from wait(lambda: 2.3<smoker_mesh.get_position()<2.95,"Smoker raised his hand",8)
    trail=smoker.get_component_by_class(ue.CigaretteSmokeComponent)
    assert trail and trail.is_visible() and trail.get_instance_count()==24
    yield from photograph("NewsstandSmoker")
    del walkers,smoker,crowd

    say_step("City life: cloud motion, haze and the five-minute freight service")
    yield from look((-5960,-1877,89),(-9680,-1465,870))
    yield from photograph("Horizon")
    rail,branch=sorted(ue.GameplayStatics.get_all_actors_of_class(world(),ue.CityRailTraffic),key=lambda a:a.get_actor_location().x)
    assert rail.get_editor_property("interval")==300
    assert rail.get_actor_location().x<-6735
    def locomotive():
        components=rail.get_components_by_class(ue.StaticMeshComponent)
        return next((part for part in components if part.static_mesh and part.static_mesh.get_name()=="SM_FreightEngine"),None)
    yield from wait(rail.is_passing,"First train appeared",75)
    yield from wait(lambda: locomotive() and -1660<locomotive().get_world_location().y<-1070,
                    "Train reached the visible section",27)
    y=locomotive().get_world_location().y
    yield from pause(.21)
    assert locomotive().get_world_location().y>y+100, "Train did not move at runtime"
    assert locomotive().get_collision_enabled()==ue.CollisionEnabled.NO_COLLISION
    yield from photograph("Freight")
    yield from wait(lambda: not rail.is_passing(),"Train clears the city",28)
    assert not locomotive().is_visible()
    yield from look((2540,-4960,90),(2550,branch.get_actor_location().y,650))
    yield from wait(branch.is_passing,"Industrial train departed",55)
    engine=next(c for c in branch.get_components_by_class(ue.StaticMeshComponent)
                if c.static_mesh and c.static_mesh.get_name()=="SM_FreightEngine")
    yield from wait(lambda: 2140<engine.get_world_location().x<3220,"Industrial train reached the crossing",30)
    x=engine.get_world_location().x
    yield from pause(.25)
    assert engine.get_world_location().x>x+100 and engine.get_collision_enabled()==ue.CollisionEnabled.NO_COLLISION
    yield from photograph("IndustrialTrain")
    del rail,branch,engine
    say_step("City life: wet footsteps keep the new recorded splash in the mix")
    yield from look((-2260,-1230,90),(-3600,-1230,135))
    director=actor_of(ue.ActOneDirector)
    director.set_rain(True)
    yield from wait(lambda: env.get_wetness()>.28,"Rain wets the road",5)
    before=env.get_footstep_count()
    start=time.monotonic()
    while time.monotonic()<start+1.45:
        pawn().add_movement_input(ue.Vector(-1,0,0),1,False)
        yield
    assert env.get_footstep_count()>before
    assert str(env.get_last_footstep_surface())=="Wet"
    ue.log("CITY_LIFE_PIE_OK")


assert levels.load_level("/Game/Locations/"+apartment)
ue.EditorPythonScripting.set_keep_python_script_alive(True)
state["run"]=run_life()
state["handle"]=ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
