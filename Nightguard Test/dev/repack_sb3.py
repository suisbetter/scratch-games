"""Repack nightguard_extract/project.json back into ../sb3/1287939979.sb3,
copying every other zip entry byte-for-byte unchanged, and adding any new
asset files staged by install_phone_guy.py (dev/phone_audio/<md5>.mp3 and
<md5>.svg costume ignored by git, generated on the fly) into the zip."""
import glob
import os
import shutil
import zipfile

SB3 = "../sb3/1287939979.sb3"
PROJECT_JSON = "nightguard_extract/project.json"
TMP = SB3 + ".tmp"
NEW_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phone_audio")


def staged_assets():
    """Files in dev/phone_audio/ that are md5-named (i.e. generated layout
    assets: <32 hex chars>.<ext>). Their zip entry name is their file name."""
    return [
        os.path.basename(p)
        for p in glob.glob(os.path.join(NEW_ASSET_DIR, "[0-9a-f]" * 32 + ".*"))
    ]


with open(PROJECT_JSON, "rb") as f:
    new_project_json = f.read()

with zipfile.ZipFile(SB3, "r") as zin, zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "project.json":
            data = new_project_json
        else:
            data = zin.read(item.filename)
        zout.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED)
    for name in staged_assets():
        zout.write(os.path.join(NEW_ASSET_DIR, name), arcname=name)

shutil.move(TMP, SB3)
print(f"Repacked {SB3} with project.json ({len(new_project_json)} bytes) "
      f"plus {len(staged_assets())} new asset file(s).")

with zipfile.ZipFile(SB3) as z:
    bad = z.testzip()
    assert bad is None, f"corrupt entry: {bad}"
    assert len(z.read("project.json")) == len(new_project_json)
    print("Repack verified OK.")