"""Repack nightguard_extract/project.json back into ../sb3/1287939979.sb3,
copying every other asset entry byte-for-byte unchanged."""
import zipfile
import shutil

SB3 = "../sb3/1287939979.sb3"
PROJECT_JSON = "nightguard_extract/project.json"
TMP = SB3 + ".tmp"

with open(PROJECT_JSON, "rb") as f:
    new_project_json = f.read()

with zipfile.ZipFile(SB3, "r") as zin, zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == "project.json":
            data = new_project_json
        zout.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED)

shutil.move(TMP, SB3)
print(f"Repacked {SB3} with project.json ({len(new_project_json)} bytes).")

with zipfile.ZipFile(SB3) as z:
    bad = z.testzip()
    assert bad is None, f"corrupt entry: {bad}"
    assert len(z.read("project.json")) == len(new_project_json)
    print("Repack verified OK.")
