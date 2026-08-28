import json, zipfile, shutil, os

SRC_SB3 = "../sb3/1287939979.sb3"
WORK = "nightguard_extract"
OUT_SB3 = "1287939979_fixed.sb3"

proj_path = os.path.join(WORK, "project.json")
data = json.load(open(proj_path, encoding="utf-8"))

door = next(t for t in data["targets"] if t["name"] == "Door")
db = door["blocks"]
office = next(t for t in data["targets"] if t["name"] == "Office")
ob = office["blocks"]

# ---------------------------------------------------------------
# FIX 1 (Door.txt): right-door clone click handler never sets
# rightdoorstate back to "open" and always falls through to the
# "close" logic regardless of which branch ran. Convert the plain
# control_if into control_if_else, moving the existing fall-through
# ("close") chain into the else branch, and appending a
# "set rightdoorstate to open" to the end of the if-true ("open")
# branch so the two paths are mutually exclusive.
# ---------------------------------------------------------------

IF_BLOCK = "DS-(O!4uIDa^*g|alQ4*"
COND = "YBIer#Y=TtiWjAP_Mgeo"
TRUE_SUBSTACK_HEAD = "^/@35oTvn`JrA*9wd$15"          # switch costume2 (open anim)
TRUE_CLONE = "A8Jbi.Kukr6@Q84UY6_U"                   # create clone (to remove)
TRUE_CLONE_MENU = "Kurs$qC0V(Md|4jHB5`1"
TRUE_BROADCAST = "b[^aJ|fPOb@0XN%Uj}M3"               # broadcast "right door"

ELSE_SUBSTACK_HEAD = "3c`[[`@Y!?+u.I8b/GmT"           # set rightdoorstate=closed
ELSE_COSTUME1 = "6:0t1e^mX40x-[F%_)A6"                # switch costume1 (closed anim)
ELSE_CLONE = "mD`Ym(PJ[gfov7:s#Y2^"                   # create clone (to remove)
ELSE_CLONE_MENU = ";m-T8RDi~F@f;4zzik7Y"
ELSE_BROADCAST = "9l2TAc?sw1=`Bx3?6O0X"               # broadcast "right door"

assert db[IF_BLOCK]["opcode"] == "control_if"
assert db[IF_BLOCK]["next"] == ELSE_SUBSTACK_HEAD

# remove the runaway "create clone of myself" calls from both branches
db[TRUE_SUBSTACK_HEAD]["next"] = TRUE_BROADCAST
db[TRUE_BROADCAST]["parent"] = TRUE_SUBSTACK_HEAD
del db[TRUE_CLONE]
del db[TRUE_CLONE_MENU]

db[ELSE_COSTUME1]["next"] = ELSE_BROADCAST
db[ELSE_BROADCAST]["parent"] = ELSE_COSTUME1
del db[ELSE_CLONE]
del db[ELSE_CLONE_MENU]

# append "set rightdoorstate to open" at the end of the if-true (open) branch
NEW_OPEN_STATE = "zNGdoorOpenState001"
db[NEW_OPEN_STATE] = {
    "opcode": "data_setvariableto",
    "next": None,
    "parent": TRUE_BROADCAST,
    "inputs": {"VALUE": [1, [10, "open"]]},
    "fields": {"VARIABLE": ["rightdoorstate", "kWwpbLAXTnqMRh?mebX0"]},
    "shadow": False,
    "topLevel": False,
}
db[TRUE_BROADCAST]["next"] = NEW_OPEN_STATE

# convert the control_if into control_if_else: true branch keeps opening the
# door, else branch (previously unconditional fall-through) closes it.
db[IF_BLOCK]["opcode"] = "control_if_else"
db[IF_BLOCK]["inputs"] = {
    "CONDITION": [2, COND],
    "SUBSTACK": [2, TRUE_SUBSTACK_HEAD],
    "SUBSTACK2": [2, ELSE_SUBSTACK_HEAD],
}
db[IF_BLOCK]["next"] = None

print("Door.txt fix applied.")

# ---------------------------------------------------------------
# FIX 2 (Office.txt): the "right door" broadcast handler only reacts
# to rightdoorstate=="closed" (plays the close animation, sets
# counter=1) and has no matching branch for the reopen case, so
# `counter` is never reset to 0 and every later "right door"
# broadcast is swallowed by the `If (counter == 1) Stop` guard.
# The correct reopen animation already exists but is an orphaned,
# disconnected script that never runs. Wire it in as the missing
# "Else" branch, mirroring the working "left door" handler's
# if/else pattern in this same file.
# ---------------------------------------------------------------

INNER_IF = "Yd$*_P?@Clp1{NzLn:J3"     # If (rightdoorstate == "closed")
CLOSE_CHAIN_HEAD = "Y2_1JX}/dl*FWuBsy+MI"  # unchanged: close animation + counter=1

REOPEN_COSTUME6 = "5mldgnL-qzZED]jL38x8"   # switch costume6
REOPEN_WAIT = "Pbd-rz=3Rzse6P691E0F"
REOPEN_COSTUME1 = "^p,UcfHP=`aUk$moP6`3"  # switch costume1
REOPEN_COUNTER0 = "yW[mizMa~V]5pzA!!Q#r"  # counter = 0
REOPEN_STATE_OPEN = "sOCH7tg9XGb|hCuL5U+v"  # rightdoorstate = open (now redundant, drop)
REOPEN_STOP = "N~LBIqr#z``,nna]P+b?"        # stop this script (drop, unneeded in if/else branch)

ORPHAN_WAITUNTIL = "Om=o@jwu5X;IN1cV.A=4"
ORPHAN_WAITUNTIL_COND = "}%Js%U8?8hauFNm0CnWf"
ORPHAN_OUTER_IF = "NfN]4qa-s6I%/R%(Mzqw"
ORPHAN_OUTER_COND = "Nqd7]_q`0(E-K3[nsik{"

assert ob[INNER_IF]["opcode"] == "control_if"

# detach the reopen-animation chain from the orphaned script and reuse it,
# dropping the redundant state-set/stop (Door.txt now owns rightdoorstate)
ob[REOPEN_COUNTER0]["next"] = None
del ob[REOPEN_STATE_OPEN]
del ob[REOPEN_STOP]

ob[REOPEN_COSTUME6]["parent"] = INNER_IF

# delete the now-fully-unused orphaned top-level script
del ob[ORPHAN_WAITUNTIL]
del ob[ORPHAN_WAITUNTIL_COND]
del ob[ORPHAN_OUTER_IF]
del ob[ORPHAN_OUTER_COND]

# convert the inner If into If/Else: closed -> close anim (unchanged),
# else (open) -> reopen anim + reset counter so the toggle can repeat
ob[INNER_IF]["opcode"] = "control_if_else"
ob[INNER_IF]["inputs"]["SUBSTACK2"] = [2, REOPEN_COSTUME6]

print("Office.txt fix applied.")

# ---------------------------------------------------------------
# sanity check: every block reference actually resolves
# ---------------------------------------------------------------
def check(blocks, label):
    ids = set(blocks.keys())
    for bid, b in blocks.items():
        if not isinstance(b, dict):
            continue
        if b.get("next") and b["next"] not in ids:
            raise AssertionError(f"{label}: {bid} next -> missing {b['next']}")
        if b.get("parent") and b["parent"] not in ids:
            raise AssertionError(f"{label}: {bid} parent -> missing {b['parent']}")
        for k, v in (b.get("inputs") or {}).items():
            if isinstance(v, list) and len(v) >= 2 and isinstance(v[1], str):
                if v[1] not in ids:
                    raise AssertionError(f"{label}: {bid} input {k} -> missing {v[1]}")

check(db, "Door")
check(ob, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json written.")

# ---------------------------------------------------------------
# repackage into a new sb3 (zip), copying every other asset unchanged
# ---------------------------------------------------------------
if os.path.exists(OUT_SB3):
    os.remove(OUT_SB3)

with zipfile.ZipFile(SRC_SB3) as zin, zipfile.ZipFile(OUT_SB3, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        if item.filename == "project.json":
            zout.write(proj_path, "project.json")
        else:
            zout.writestr(item, zin.read(item.filename))

print("Wrote fixed sb3 to", OUT_SB3)
