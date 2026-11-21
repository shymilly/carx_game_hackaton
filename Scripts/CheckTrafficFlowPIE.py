"""Exercise all four traffic routes for several minutes at a low frame rate."""
import json
from pathlib import Path
import time
import traceback

import unreal as ue

levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
editor = ue.get_editor_subsystem(ue.UnrealEditorSubsystem)
assert levels.load_level("/Game/Locations/L_NeptuneStreet")
ue.EditorPythonScripting.set_keep_python_script_alive(True)
baseline = "-TrafficBaseline" in ue.SystemLibrary.get_command_line()
state = dict(deadline=time.monotonic() + 135, cars={}, ages=[], longest_wait=0, samples=0)


def finish(ok):
    ue.unregister_slate_post_tick_callback(state["callback"])
    levels.editor_request_end_play()
    ue.EditorPythonScripting.set_keep_python_script_alive(False)
    if ok:
        ue.log("QUALITY_TRAFFIC_BASELINE_OK" if baseline else "QUALITY_TRAFFIC_STRESS_OK")


def tick(delta):
    try:
        assert time.monotonic() < state["deadline"], "Traffic stress test timed out"
        world = editor.get_game_world()
        if not world:
            return
        pawn = ue.GameplayStatics.get_player_character(world, 0)
        flow = ue.GameplayStatics.get_actor_of_class(world, ue.StreetTrafficFlow)
        if not pawn or not flow:
            return
        now = ue.GameplayStatics.get_time_seconds(world)
        if "start" not in state:
            pawn.set_actor_location(ue.Vector(-2220, -515, 101), False, True)
            assert flow.validate_route_clearance()
            ue.SystemLibrary.execute_console_command(world, "t.MaxFPS 15")
            ue.GameplayStatics.set_global_time_dilation(world, 5)
            state["start"] = now
            state["wall_start"] = time.monotonic()
        for car in ue.GameplayStatics.get_all_actors_of_class(world, ue.StreetTrafficCar):
            name = car.get_name()
            if car.get_editor_property("hidden"):
                if name in state["cars"]:
                    state["ages"].append(now - state["cars"].pop(name)[0])
                continue
            position = car.get_actor_location()
            started, moved, previous = state["cars"].get(name, (now, now, position))
            if position.distance(previous) > 3:
                moved = now
                previous = position
            state["longest_wait"] = max(state["longest_wait"], now - moved)
            state["cars"][name] = started, moved, previous
        state["samples"] += 1
        if now - state["start"] < 200:
            return
        result = dict(tested_game_seconds=round(now - state["start"], 2), spawned=flow.get_total_spawned(),
                      completed=len(state["ages"]), blocked_moves=flow.get_blocked_moves(), max_vehicle_age=round(max(state["ages"], default=0), 2),
                      longest_wait=round(state["longest_wait"], 2), sampled_frames=state["samples"],
                      elapsed_seconds=round(time.monotonic() - state["wall_start"], 2))
        ue.log("QUALITY_TRAFFIC " + json.dumps(result))
        report = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_saved_dir())) / "Quality0142"
        report.mkdir(parents=True, exist_ok=True)
        (report / ("TrafficBefore.json" if baseline else "TrafficAfter.json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        if not baseline:
            assert result["blocked_moves"] == 0 and result["completed"] >= 12 and result["longest_wait"] < 13, result
        finish(True)
    except Exception:
        ue.log_error("QUALITY_TRAFFIC_FAILED " + traceback.format_exc())
        finish(False)


state["callback"] = ue.register_slate_post_tick_callback(tick)
levels.editor_request_begin_play()
