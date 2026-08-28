"""Re-derive the hardcoded block ids run_all_tests.py needs, by structural
signature (opcode + which stable variable/list/broadcast id it references)
rather than by remembered id -- TurboWarp regenerates every block id (but not
variable/list ids) whenever it re-saves the project, which invalidates any
hardcoded block id every time that happens. Variable/list ids themselves are
stable across a TurboWarp resave, which is what makes this approach work.

Run against a fresh extraction and paste the printed constants into the top
of run_all_tests.py if the ids have drifted (a KeyError from interpreter.py
while running run_all_tests.py is the symptom).
"""
import json
import sys

WORK = "nightguard_extract"
data = json.load(open(WORK + "/project.json", encoding="utf-8"))


def target(name):
    return next(t for t in data["targets"] if t["name"] == name)


def refs_var(blocks, bid, varname, seen=None):
    if seen is None:
        seen = set()
    if bid in seen or bid not in blocks:
        return False
    seen.add(bid)
    b = blocks[bid]
    for v in b.get("fields", {}).values():
        if isinstance(v, list) and v and v[0] == varname:
            return True
    for v in b.get("inputs", {}).values():
        if not isinstance(v, list):
            continue
        for item in v[1:]:
            if isinstance(item, str) and refs_var(blocks, item, varname, seen):
                return True
            if isinstance(item, list) and len(item) > 2 and item[0] == 12 and item[1] == varname:
                return True
    return False


door = target("Door")["blocks"]
office = target("Office")["blocks"]
cammenu = target("CamMenu")["blocks"]
an_target = target("Animatronics")
an = an_target["blocks"]

out = {}

out["LEFT_CLICK_HAT"] = next(bid for bid, b in door.items()
                              if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenthisspriteclicked")
out["RIGHT_IFELSE"] = next(bid for bid, b in door.items()
                            if isinstance(b, dict) and b["opcode"] == "control_if_else"
                            and refs_var(door, b["inputs"].get("CONDITION", [None, None])[1], "rightdoorstate"))
out["IS_CLONE_VAR"] = next(vid for vid, e in target("Door")["variables"].items() if e[0] == "is clone")

out["OFFICE_RIGHT_DOOR_HAT"] = next(bid for bid, b in office.items()
                                     if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenbroadcastreceived"
                                     and b["fields"]["BROADCAST_OPTION"][0] == "right door")
out["OFFICE_LEFT_DOOR_HAT"] = next(bid for bid, b in office.items()
                                    if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenbroadcastreceived"
                                    and b["fields"]["BROADCAST_OPTION"][0] == "left door")

for bid, b in office.items():
    if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenflagclicked":
        nxt = b.get("next")
        if nxt and office.get(nxt, {}).get("opcode") == "control_repeat_until":
            cond = office[nxt]["inputs"]["CONDITION"][1]
            if refs_var(office, cond, "power"):
                out["POWER_HAT"] = bid
            elif refs_var(office, cond, "time"):
                out["TIME_HAT"] = bid

out["JUMPSCARE_GATE_HAT"] = next(bid for bid, b in office.items()
                                  if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenbroadcastreceived"
                                  and b["fields"]["BROADCAST_OPTION"][0] == "forever"
                                  and refs_var(office, b.get("next"), "camlist"))

out["CAMMENU_CLICK_HAT"] = next(bid for bid, b in cammenu.items()
                                 if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenthisspriteclicked"
                                 and cammenu.get(b.get("next"), {}).get("opcode") == "procedures_call")
out["CAMMENU_KEY_HAT"] = next(bid for bid, b in cammenu.items()
                               if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenkeypressed"
                               and cammenu.get(b.get("next"), {}).get("opcode") == "procedures_call")

for bid, b in an.items():
    if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenflagclicked":
        nxt = b.get("next")
        if nxt and an.get(nxt, {}).get("opcode") == "procedures_call":
            proc = an.get(nxt, {}).get("mutation", {}).get("proccode", "")
            if proc == "rng man %s":
                out["ANIM_CHAIN_A_HEAD"] = nxt
                cur = nxt
                while an[cur].get("opcode") == "procedures_call":
                    nxt2 = an[cur]["next"]
                    if nxt2 and an.get(nxt2, {}).get("opcode") == "control_repeat_until":
                        out["ANIM_LOOP_BLOCK"] = nxt2
                        break
                    cur = nxt2

out["AI_ENABLED_VAR"] = next((vid for vid, e in an_target["variables"].items() if e[0] == "ai enabled"),
                              next((vid for vid, e in target("Stage")["variables"].items() if e[0] == "ai enabled"), None))
out["CAMLIST_ID"] = next(lid for lid, e in target("Stage")["lists"].items() if e[0] == "camlist")

for k, v in out.items():
    print(f'{k} = {v!r}')
