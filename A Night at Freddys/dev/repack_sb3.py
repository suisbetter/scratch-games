"""Write extract/project.json back into ../sb3/1079847401.sb3, replacing only
the project.json entry and copying every other zip member byte-for-byte.

The project's assets are referenced by content-md5 filenames and none are
dropped or added by the cleanup, so a targeted in-place replacement is exactly
as correct as a full rebuild and keeps the zip byte-identical everywhere except
project.json.
"""

import json
import os
import zipfile

SB3 = "../sb3/1079847401.sb3"
PROJECT_PATH = "extract/project.json"

new_pj = open(PROJECT_PATH, "rb").read()
json.loads(new_pj.decode("utf-8"))  # validate json before touching the sb3

tmp = SB3 + ".new"
with zipfile.ZipFile(SB3, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for info in zin.infolist():
        if info.filename == "project.json":
            zout.writestr(info, new_pj)
        else:
            zout.writestr(info, zin.read(info.filename))

os.replace(tmp, SB3)
print("repacked", SB3, "with edited project.json")

zin = zipfile.ZipFile(SB3)
bad = zin.testzip()
print("zip integrity:", "OK" if bad is None else "CORRUPT: " + str(bad))
print("entries:", len(zin.namelist()))