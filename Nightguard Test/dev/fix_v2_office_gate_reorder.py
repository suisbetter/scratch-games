import json

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]
ob = office

OUTER_IF = "uofl_I,QI[?_fz}%vW%;"
INNER_IF = "Yd$*_P?@Clp1{NzLn:J3"
COND_COUNTER1 = "PLFW`Vr=x$W|o1Q+iKhg"
COND_RIGHTCLOSED = "(+`wfa:ra]JV`bd7[0vk"
STOP_BLOCK = "ld96+=#D(gL0sn8hfV=R"
CLOSE_CHAIN_HEAD = "Y2_1JX}/dl*FWuBsy+MI"
REOPEN_CHAIN_HEAD = "5mldgnL-qzZED]jL38x8"

assert ob[OUTER_IF]["opcode"] == "control_if_else"
assert ob[INNER_IF]["opcode"] == "control_if_else"
assert ob[OUTER_IF]["inputs"]["CONDITION"] == [2, COND_COUNTER1]
assert ob[INNER_IF]["inputs"]["CONDITION"] == [2, COND_RIGHTCLOSED]

# The original wiring gated on `counter==1` BEFORE checking door state at all, so
# once counter latched to 1 after the first close, every later "right door"
# broadcast -- including the reopen one, which is what resets counter -- got
# stopped immediately and counter could never reset. Swap the gate order: check
# door state first (outer), use counter only to debounce the close animation
# (inner).
ob[OUTER_IF]["inputs"] = {
    "CONDITION": [2, COND_RIGHTCLOSED],
    "SUBSTACK": [2, INNER_IF],
    "SUBSTACK2": [2, REOPEN_CHAIN_HEAD],
}
ob[INNER_IF]["inputs"] = {
    "CONDITION": [2, COND_COUNTER1],
    "SUBSTACK": [2, STOP_BLOCK],
    "SUBSTACK2": [2, CLOSE_CHAIN_HEAD],
}

ob[COND_RIGHTCLOSED]["parent"] = OUTER_IF
ob[COND_COUNTER1]["parent"] = INNER_IF
ob[STOP_BLOCK]["parent"] = INNER_IF
ob[REOPEN_CHAIN_HEAD]["parent"] = OUTER_IF
# CLOSE_CHAIN_HEAD's parent stays INNER_IF (unchanged)


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


check(ob, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v2) written.")
