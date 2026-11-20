"""Author the player's arms montage, cigarette prop and the two NPC smoking clips."""
from math import cos, sin, tau
from pathlib import Path
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project / "Tools"))
from ApartmentScene import make_material
from BrightonStreetDetails import expression
from BrightonUpgrade import ASSETS, LIB, P, TOOLS, color, factory_asset, node, output, save

SMOKE = "/Game/Story/ActOne/Smoking"
PEOPLE = "/Game/Prologue/CityLife/People"


def cigarette():
    parts = (
        ("Filter", -2.75, -.48, .40, (.56, .26, .105), .74),
        ("Paper", -.48, 4.56, .40, (.77, .73, .63), .84),
        ("Ash", 4.56, 5.31, .38, (.24, .22, .20), .93),
        ("Ember", 5.31, 5.46, .31, (.31, .071, .021), .58),
    )
    directory = project / "Saved/SmokingSource"
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "SM_Cigarette.obj"
    sides = 12
    vertices = []
    texcoords = []
    obj = ["mtllib Cigarette.mtl", "o Cigarette", "s 1"]
    mtl = []
    for i, (name, start, end, radius, tint, roughness) in enumerate(parts):
        offset = 1 + i * sides * 2
        mtl += [f"newmtl {name}", "Kd " + " ".join(map(str, tint))]
        obj.append("usemtl " + name)
        for x in (start, end):
            for j in range(sides):
                a = j * tau / sides
                vertices.append(f"v {x} {cos(a)*radius:.5f} {sin(a)*radius:.5f}")
                texcoords.append(f"vt {(x+2.75)/8.21:.6f} {j/(sides-1):.6f}")
        for j in range(sides):
            a = offset + j
            b = offset + (j + 1) % sides
            obj.append("f " + " ".join(f"{v}/{v}" for v in (a, b, b+sides, a+sides)))
        if i == 0:
            obj.append("f " + " ".join(f"{offset+j}/{offset+j}" for j in reversed(range(sides))))
        if i == len(parts) - 1:
            obj.append("f " + " ".join(f"{offset+sides+j}/{offset+sides+j}" for j in range(sides)))
    source.write_text("\n".join(obj[:3] + vertices + texcoords + obj[3:]) + "\n", encoding="ascii")
    (directory / "Cigarette.mtl").write_text("\n".join(mtl) + "\n", encoding="ascii")
    task = ue.AssetImportTask()
    task.set_editor_properties(dict(filename=str(source), destination_path=SMOKE, automated=True,
                                    replace_existing=True, save=False))
    TOOLS.import_asset_tasks([task])
    mesh = ue.load_asset(SMOKE + "/SM_Cigarette")
    assert mesh
    bounds = mesh.get_bounding_box()
    assert abs(bounds.min.x + 2.75) < .2 and abs(bounds.max.x - 5.46) < .2, bounds
    slots = {str(slot.material_slot_name): i for i, slot in enumerate(mesh.static_materials)}
    for name, _, _, _, tint, roughness in parts:
        material = make_material(SMOKE, name, tint, roughness)
        if name == "Ember":
            output(color(material, (.79, .115, .015)), material, P.MP_EMISSIVE_COLOR)
            LIB.recompile_material(material)
            save(material)
        mesh.set_material(slots[name], material)
    save(mesh)
    return mesh


def smoke_material():
    material = ue.load_asset("/Game/Prologue/Brighton/Materials/M_CigaretteSmoke")
    assert material
    LIB.delete_all_material_expressions(material)
    material.set_editor_properties(dict(two_sided=True, blend_mode=ue.BlendMode.BLEND_TRANSLUCENT,
        shading_model=ue.MaterialShadingModel.MSM_UNLIT, used_with_instanced_static_meshes=True))
    fade = node(material, ue.MaterialExpressionPerInstanceCustomData, data_index=0, const_default_value=0.)
    stream = node(material, ue.MaterialExpressionVertexInterpolator)
    assert LIB.connect_material_expressions(fade, "", stream, "") or LIB.connect_material_expressions(fade, "", stream, "VS")
    alpha = expression(material, {"UV": node(material, ue.MaterialExpressionTextureCoordinate),
        "Fade": stream, "Time": node(material, ue.MaterialExpressionTime)}, """
        float2 p = UV * 2 - 1;
        p.x += .17 * sin(p.y * 5.1 + Time * 1.63);
        float strand = .78 + .22 * sin(p.y * 6.7 + p.x * 5.4 - Time*.9);
        return pow(saturate(1-dot(p,p)),2.4) * strand * Fade * .235;
        """, ue.CustomMaterialOutputType.CMOT_FLOAT1)
    output(alpha, material, P.MP_OPACITY)
    output(color(material, (.47, .50, .56)), material, P.MP_EMISSIVE_COLOR)
    LIB.recompile_material(material)
    save(material)


def compression(sequence):
    for kind in ("bone", "curve"):
        asset = "/ACLPlugin/ACLAnim" + kind.title() + "CompressionSettings"
        settings = ue.load_asset(asset)
        assert settings, asset
        sequence.set_editor_property(kind + "_compression_settings", settings)


def first_person(prop):
    name = SMOKE + "/SK_DimaSmokingArms"
    model = ue.load_asset(name) if ASSETS.does_asset_exist(name) else ASSETS.duplicate_asset(
        "/Game/ImportedAssets/FirstPersonArms/arms_rig/SK_arms_rig", name)
    assert model
    skeleton = factory_asset(SMOKE, "SKEL_DimaSmokingArms", ue.Skeleton, None)
    clip = factory_asset(SMOKE, "A_DimaSmoke_FirstPerson", ue.CityGestureSequence, None)
    assert ue.CityCharacterAuthoring.author_first_person_smoke(model, skeleton, clip)
    # The imported arms have no physics asset and the reference stance spreads them sideways.
    # The camera-facing reach needs its own culling bounds.
    model.set_editor_properties(dict(positive_bounds_extension=ue.Vector(12, 75, 12),
                                     negative_bounds_extension=ue.Vector(12, 16, 32)))
    compression(clip)
    save(model)
    save(clip)
    graph_factory = ue.AnimBlueprintFactory()
    graph_factory.set_editor_properties(dict(target_skeleton=skeleton, preview_skeletal_mesh=model))
    blueprint = factory_asset(SMOKE, "ABP_DimaSmokingArms", ue.AnimBlueprint, graph_factory)
    assert ue.CityCharacterAuthoring.install_smoking_slot(blueprint)
    montage_factory = ue.AnimMontageFactory()
    montage_factory.set_editor_properties(dict(target_skeleton=skeleton, source_animation=clip))
    montage = factory_asset(SMOKE, "AM_DimaSmoke", ue.AnimMontage, montage_factory)
    assert 2.5 < montage.get_play_length() < 2.7
    for asset in (skeleton, blueprint, montage):
        save(asset)
    data = ue.load_asset("/Game/Story/ActOne/DA_ActOne")
    data.set_editor_properties(dict(smoking_arms=model, smoking_anim_class=ue.BlueprintEditorLibrary.generated_class(blueprint),
                                    smoking_montage=montage, cigarette_mesh=prop))
    save(data)


def city_smokers(prop):
    for role in ("Smoker", "Ivan"):
        profile = ue.load_asset(PEOPLE + "/Profiles/DA_" + role)
        motions = profile.get_editor_property("motions")
        model = profile.get_editor_property("mesh")
        clip = motions[ue.Name("Smoke")]
        compression(clip)
        assert ue.CityCharacterAuthoring.author_gesture(model, motions[ue.Name("Idle")], clip, "Smoke"), role
        profile.set_editor_property("cigarette_mesh", prop)
        for asset in (model, clip, profile):
            save(asset)
        ue.log("QUALITY_NPC_SMOKE " + role + " " + clip.get_path_name())


prop = cigarette()
smoke_material()
first_person(prop)
city_smokers(prop)
ue.log("QUALITY_SMOKING_ASSETS_OK")
