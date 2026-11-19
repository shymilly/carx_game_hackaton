"""Prepare the selected desktop assets and the recorded footstep sources."""
import argparse
from io import BytesIO
from pathlib import Path
from shutil import copy2
import sys
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
DESKTOP = Path.home() / "Desktop" / "assets"
OUT = PROJECT / "SourceAssets" / "CityLife"
sys.path.insert(0, str(PROJECT / "Saved/CityLife/Python"))

PEOPLE = ("Smooth_Male_Suit", "Smooth_Male_LongSleeve", "Smooth_Male_Shirt", "Smooth_Male_Casual")
# OBJ files in these packs have Y up. Keep their proportions and use a ground pivot.
MESHES = {
    "OakAmber": ("nature", "CommonTree_Autumn_2", 650, 1),
    "OakGreen": ("nature", "CommonTree_3", 570, 1),
    "BirchGold": ("nature", "BirchTree_Autumn_3", 575, 1),
    "Bush": ("nature", "Bush_2", 75, 1),
    "WalkupBrick": ("city2", "Building3_Big", 1250, 1),
    "WalkupPale": ("city2", "Building1_Large", 1440, 1),
    "WalkupBay": ("city2", "Building2_Large", 1125, 1),
    "MarketHouse": ("city2", "House2", 660, 1),
    "TrashCan": ("Furniture", "Trashcan_Cylindric", 82, 1),
    "Dumpster": ("Furniture", "Trashcan_Green", 112, 1),
    "RailStraight": ("train", "RailwayTrack_Straight", 780, 0),
    "FreightEngine": ("train", "CargoTrain_Front", 1510, 0),
    "FreightBoxcar": ("train", "CargoTrain_Wagon", 1420, 0),
    "FreightGondola": ("train", "CargoTrain_WagonOpenContainer", 1240, 0),
}


def normalize_obj(source, target, size, length_axis):
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    points = [tuple(map(float, line.split()[1:4])) for line in lines if line.startswith("v ")]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    factor = size / (high[length_axis] - low[length_axis])
    cx, cz = (low[0] + high[0]) / 2, (low[2] + high[2]) / 2
    has_uvs = any(line.startswith("vt ") for line in lines)
    out = ["mtllib " + target.with_suffix(".mtl").name, "o " + target.stem]
    if not has_uvs:
        # The OBJ translator expects a UV index even for a flat-color model.
        out.append("vt 0.5 0.5")
    for line in lines:
        if line.startswith(("mtllib ", "o ", "g ", "s ")):
            continue
        if line.startswith("v "):
            x, y, z = map(float, line.split()[1:4])
            line = "v %.6f %.6f %.6f" % ((x - cx) * factor, (z - cz) * factor, (y - low[1]) * factor)
        elif line.startswith("vn "):
            x, y, z = map(float, line.split()[1:4])
            line = "vn %.7f %.7f %.7f" % (x, z, y)
        elif line.startswith("f "):
            corners = list(reversed(line.split()[1:]))
            if not has_uvs:
                corners = [v.replace("//", "/1/") if "//" in v else v + "/1" for v in corners]
            line = "f " + " ".join(corners)
        out.append(line)
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    copy2(source.with_suffix(".mtl"), target.with_suffix(".mtl"))
    print(target.stem, "size cm", tuple(round((high[i] - low[i]) * factor, 1) for i in (0, 2, 1)))


def stage_models():
    meshes = OUT / "Meshes"
    people = OUT / "People"
    meshes.mkdir(parents=True, exist_ok=True)
    people.mkdir(parents=True, exist_ok=True)
    for name, (pack, stem, size, axis) in MESHES.items():
        source = DESKTOP / pack / "OBJ" / (stem + ".obj")
        normalize_obj(source, meshes / ("SM_" + name + ".obj"), size, axis)
    men = DESKTOP / "human_assets/man"
    for name in PEOPLE:
        copy2(men / "FBX" / (name + ".fbx"), people)
        copy2(men / "OBJ" / (name + ".mtl"), people)
    copy2(men / "Blends/Tie.png", people)
    women = DESKTOP / "human_assets/all_background"
    copy2(women / "FBX/Animated Woman_smooth.fbx", people / "Animated_Woman_Smooth.fbx")
    for name in ("LightSkin", "LightSkin2", "DarkSkin1"):
        copy2(women / "Blends" / (name + ".png"), people)
    copy2(men / "License.txt", OUT / "Quaternius-LICENSE.txt")


def staged_audio(archive_path):
    import numpy as np
    import soundfile

    destination = PROJECT / "Resources/Brighton/Audio"
    notes = [
        "Footsteps on different surfaces, assembled by congusbongus (CC BY 3.0).",
        "https://opengameart.org/content/footsteps-on-different-surfaces",
        "Project edits: converted to mono PCM, trimmed quiet tails, softened the attack and matched levels.",
        "Wet variants blend a recorded splash with a recorded shoe on concrete.",
    ]
    with ZipFile(archive_path) as archive:
        def load(surface, index):
            with BytesIO(archive.read(f"footsteps/{surface}/{index}.ogg")) as stream:
                data, rate = soundfile.read(stream, dtype="float32", always_2d=True)
            mono = data.mean(axis=1)
            output_rate = 44100
            if rate != output_rate:
                pos = np.arange(round(len(mono) * output_rate / rate)) * rate / output_rate
                mono = np.interp(pos, np.arange(len(mono)), mono)
            peak = max(np.max(np.abs(mono)), .00001)
            valid = np.flatnonzero(np.abs(mono) > peak * .026)
            mono = mono[max(0, valid[0] - 80):valid[-1] + 800][:int(output_rate * .42)].copy()
            mono -= mono.mean()
            mono[:132] *= np.linspace(0, 1, 132)
            fade = min(len(mono), 660)
            mono[-fade:] *= np.linspace(1, 0, fade)
            return mono / max(np.max(np.abs(mono)), .00001)

        for dest, source, samples in (("Wood", "wood", (0, 2, 5, 7)),
                                      ("Tile", "tile", (0, 1, 2, 3)),
                                      ("Asphalt", "boots", (1, 3, 5, 8)),
                                      ("Wet", "water", (0, 1, 2, 3))):
            notes.extend(("\n" + dest, archive.read(f"footsteps/{source}/license.txt").decode("utf-8-sig").strip()))
            for output, index in enumerate(samples):
                step = load(source, index)
                if dest == "Wet":
                    shoe = load("boots", (1, 3, 5, 8)[output])
                    mixed = np.zeros(max(len(shoe), len(step) + 170))
                    mixed[:len(shoe)] += shoe * .80
                    mixed[170:len(step) + 170] += step * .37
                    step = mixed
                target = destination / f"{dest}{output}.wav"
                step *= min(.11 / max(np.sqrt(np.mean(step ** 2)), .00001), .58 / np.max(np.abs(step)))
                soundfile.write(target, step, 44100, subtype="PCM_16")
                print(target.name, round(len(step) / 44100, 3), "seconds")
    (destination / "RECORDED-FOOTSTEPS-LICENSE.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--footsteps", type=Path, required=True)
    args = parser.parse_args()
    stage_models()
    staged_audio(args.footsteps)
