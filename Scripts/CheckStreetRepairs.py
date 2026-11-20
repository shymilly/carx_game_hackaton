"""Check whole-train clearance, track continuity and the saved door cues."""
from itertools import product
from pathlib import Path
import sys
import unreal as ue

root = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0,str(root/"Tools"))
from CityLifeEnvironment import STREET_SHIFT
from IndustrialRail import START, END, Y, RAIL_Z, TRACK_SECTION, label

levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)


def bounds(mesh, transform):
    box=mesh.get_bounding_box()
    corners=[ue.MathLibrary.transform_location(transform,ue.Vector(x,y,z)).to_tuple()
             for x,y,z in product((box.min.x,box.max.x),(box.min.y,box.max.y),(box.min.z,box.max.z))]
    return tuple((min(p[i] for p in corners),max(p[i] for p in corners)) for i in range(3))


def intersects(box, corridor):
    return all(a1>b0+.1 and a0<b1-.1 for (a0,a1),(b0,b1) in zip(box,corridor))


for name in ("L_NeptuneStreet","L_DimaApartmentInterior"):
    assert levels.load_level("/Game/Locations/"+name)
    placed=actors.get_all_level_actors()
    shift=STREET_SHIFT if name.endswith("Interior") else (0,0,0)
    main,branch=sorted((a for a in placed if isinstance(a,ue.CityRailTraffic)),key=lambda a:a.get_actor_location().x)
    assert branch.get_editor_property("covered_ends")
    assert abs(branch.get_actor_location().y-Y-shift[1])<.05
    assert abs(branch.get_actor_location().z-RAIL_Z-shift[2])<.05
    sections=[]
    portals=[]
    for a in placed:
        if label(a) not in ("Industrial line rails","Industrial line tunnel roof"):continue
        instances=a.get_component_by_class(ue.InstancedStaticMeshComponent)
        for i in range(instances.get_instance_count()):
            box=bounds(instances.static_mesh,instances.get_instance_transform(i,True))
            (sections if label(a)=="Industrial line rails" else portals).append(box[0])
    sections.sort()
    assert len(sections)==(END-START)//TRACK_SECTION
    assert abs(sections[0][0]-START)<2 and abs(sections[-1][1]-END)<2,sections
    assert max(begin-previous_end for (_,previous_end),(begin,_) in zip(sections,sections[1:]))<2,sections
    assert any(abs(begin-START)<1 for begin,end in portals)
    assert any(abs(end-END)<1 for begin,end in portals)

    corridors=[]
    for service in (main,branch):
        position=service.get_actor_location().to_tuple()
        train=[car.get_editor_property("mesh").get_bounding_box() for car in service.get_editor_property("consist")]
        extent=max(max(abs(mesh.min.y),abs(mesh.max.y)) for mesh in train)+6
        tallest=max(mesh.max.z for mesh in train)+3
        reach=service.get_editor_property("half_route")
        sides=(reach,extent) if service==branch else (extent,reach)
        corridors.append(tuple((p-h,p+h) for p,h in zip(position,sides)) + ((position[2]+3,position[2]+tallest),))
    obstructions=[]
    for a in placed:
        if a.get_editor_property("hidden") or "sky dome" in label(a).lower():continue
        for comp in a.get_components_by_class(ue.StaticMeshComponent):
            if not comp.static_mesh or not comp.is_visible():continue
            transforms=([comp.get_instance_transform(i,True) for i in range(comp.get_instance_count())]
                        if isinstance(comp,ue.InstancedStaticMeshComponent) else [comp.get_world_transform()])
            for index,transform in enumerate(transforms):
                box=bounds(comp.static_mesh,transform)
                if any(intersects(box,corridor) for corridor in corridors):
                    obstructions.append((label(a),index,box))
    assert not obstructions,(name,obstructions[:15])
    ue.log("FIX_MAP_CLEAR "+name+" two continuous train paths without geometry inside the swept bounds")

for cue in ("S_WoodenDoorOpen","S_EntryDoorOpen","S_FridgeDoorOpen"):
    wave=ue.load_asset("/Game/Prologue/Brighton/Audio/Doors/"+cue)
    assert isinstance(wave,ue.SoundWave) and .22 < wave.duration < .65
    assert not wave.get_editor_property("looping")
ue.log("FIX_ASSETS_OK")
