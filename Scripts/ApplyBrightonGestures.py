"""Rebake the affected NPC upper-body clips in their current asset packages."""
from pathlib import Path
import sys

import unreal as ue

project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
sys.path.insert(0, str(project / 'Tools'))
from BrightonUpgrade import save
from CityLifeCharacters import PEOPLE, STYLES


def check_smoking(mesh, clip):
    """Check the whole raise/lower motion for the forearm-through-body regression."""
    sample = ue.CityCharacterAuthoring.pose_bone_position
    length = clip.get_play_length()
    elbow_clearance = 1.0
    wrist_path = []
    for frame in range(217):
        points = {bone: sample(mesh, clip, bone, frame*length/216) for bone in (
            'UpperArm_L', 'UpperArm_R', 'LowerArm_R', 'Palm_R')}
        left, right = points['UpperArm_L'], points['UpperArm_R']
        center = (right+left)*.5
        width = (right-left).length()
        axis = right-left
        axis.z = 0
        outward = axis*(1/axis.length())
        elbow = points['LowerArm_R']-center
        elbow_clearance = min(elbow_clearance, elbow.dot(outward)/width)
        wrist_path.append(points['Palm_R'])
    assert elbow_clearance > .44, (mesh.get_name(), elbow_clearance)
    assert (wrist_path[0]-wrist_path[-1]).length() < .25, mesh.get_name()
    assert max((b-a).length() for a,b in zip(wrist_path,wrist_path[1:])) < 16, mesh.get_name()
    ue.log(f'SMOKING_ARM_CLEAR {mesh.get_name()} at all 217 samples; minimum lateral elbow clearance {elbow_clearance:.3f} shoulder widths')


updated = set()
for role, (outfit, *_) in STYLES.items():
    if role == 'Dima':
        continue
    profile = ue.load_asset(PEOPLE + '/Profiles/DA_' + role)
    mesh = profile.get_editor_property('mesh')
    motions = profile.get_editor_property('motions')
    idle = motions[ue.Name('Idle')]
    gestures = [('Talk', idle)]
    if role in ('Bartender', 'OlderMan'):
        raw = ue.load_asset(f'{PEOPLE}/Models/{outfit}/Smooth_Male_{outfit}_Anim_HumanArmature_Man_Idle')
        gestures = [('HoldBottle', raw), ('TalkWithBottle', raw)]
    if role in ('Ivan', 'Smoker'):
        gestures.append(('Smoke', idle))
    if role in ('Krill', 'DutyOfficer'):
        gestures.append(('SeatedTalk', motions[ue.Name('Sit')]))
    for gesture, source in gestures:
        asset_path = f'{PEOPLE}/Motions/{outfit}/A_{outfit}_{gesture}'
        if asset_path in updated:
            continue
        clip = ue.load_asset(asset_path)
        assert isinstance(clip, ue.CityGestureSequence), asset_path
        assert ue.CityCharacterAuthoring.author_gesture(mesh, source, clip, gesture), asset_path
        if gesture == 'Smoke':
            check_smoking(mesh, clip)
        if gesture in ('Smoke', 'HoldBottle', 'TalkWithBottle'):
            save(mesh)
        save(clip)
        updated.add(asset_path)
        ue.log('SMOKING_GESTURE_SAVED ' + asset_path)
ue.log(f'SMOKING_GESTURES_OK {len(updated)} animation clips')
