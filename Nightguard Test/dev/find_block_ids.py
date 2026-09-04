"""Re-derive the block ids run_all_tests.py needs, by structural
signature (opcode + which stable variable/list/broadcast id it references)
rather than by remembered id -- TurboWarp regenerates every block id (but not
variable/list ids) whenever it re-saves the project, which invalidates any
hardcoded block id every time that happens. Variable/list ids themselves are
stable across a TurboWarp resave, which is what makes this approach work.

run_all_tests.py imports find_ids() directly, so it always uses the current
ids. Run this file standalone to print the derivations for inspection, or if
a fix_v*.py script's still-hardcoded ids have drifted (a KeyError from
interpreter.py while running run_all_tests.py, or a failing structural check,
is the symptom).
"""
import json
import os
import sys


def find_ids(data):
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

    out["LEFT_CLICK_HAT"] = next(
        bid for bid, b in door.items()
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenthisspriteclicked"
    )
    out["RIGHT_IFELSE"] = next(
        bid for bid, b in door.items()
        if isinstance(b, dict) and b["opcode"] == "control_if_else"
        and refs_var(door, b["inputs"].get("CONDITION", [None, None])[1], "rightdoorstate")
    )
    out["IS_CLONE_VAR"] = next(vid for vid, e in target("Door")["variables"].items() if e[0] == "is clone")

    out["OFFICE_RIGHT_DOOR_HAT"] = next(
        bid for bid, b in office.items()
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenbroadcastreceived"
        and b["fields"]["BROADCAST_OPTION"][0] == "right door"
    )
    out["OFFICE_LEFT_DOOR_HAT"] = next(
        bid for bid, b in office.items()
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenbroadcastreceived"
        and b["fields"]["BROADCAST_OPTION"][0] == "left door"
    )

    for bid, b in office.items():
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenflagclicked":
            nxt = b.get("next")
            if nxt and office.get(nxt, {}).get("opcode") == "control_repeat_until":
                cond = office[nxt]["inputs"]["CONDITION"][1]
                if refs_var(office, cond, "power"):
                    out["POWER_HAT"] = bid
                elif refs_var(office, cond, "time"):
                    out["TIME_HAT"] = bid

    out["JUMPSCARE_GATE_HAT"] = next(
        bid for bid, b in office.items()
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenbroadcastreceived"
        and b["fields"]["BROADCAST_OPTION"][0] == "forever"
        and refs_var(office, b.get("next"), "camlist")
    )

    out["CAMMENU_CLICK_HAT"] = next(
        bid for bid, b in cammenu.items()
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenthisspriteclicked"
        and cammenu.get(b.get("next"), {}).get("opcode") == "procedures_call"
    )
    out["CAMMENU_KEY_HAT"] = next(
        bid for bid, b in cammenu.items()
        if isinstance(b, dict) and b.get("topLevel") and b["opcode"] == "event_whenkeypressed"
        and cammenu.get(b.get("next"), {}).get("opcode") == "procedures_call"
    )

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

    def first_call_in_chain(start, proccode):
        """Walk a statement chain, descending into control_if/control_if_else
        substacks, and return the first procedures_call with the given proccode."""
        cur = start
        seen = set()
        while cur is not None and cur in an and cur not in seen:
            seen.add(cur)
            b = an[cur]
            if b.get("opcode") == "procedures_call" and b.get("mutation", {}).get("proccode") == proccode:
                return cur
            if b.get("opcode") in ("control_if", "control_if_else"):
                ins = b.get("inputs", {})
                for k in ("SUBSTACK", "SUBSTACK2"):
                    sub = ins.get(k, [None, None])[1]
                    if isinstance(sub, str):
                        found = first_call_in_chain(sub, proccode)
                        if found:
                            return found
            cur = b.get("next")
        return None

    def next_call(bid, proccode):
        """Return the next procedures_call with the given proccode on the
        statement chain following bid."""
        cur = an[bid].get("next")
        while cur is not None and cur in an:
            b = an[cur]
            if b.get("opcode") == "procedures_call" and b.get("mutation", {}).get("proccode") == proccode:
                return cur
            cur = b.get("next")
        return None

    out["LOOP_CALL_MAN"] = first_call_in_chain(
        an[out["ANIM_LOOP_BLOCK"]]["inputs"]["SUBSTACK"][1], "rng man %s")
    out["LOOP_CALL_WOMAN"] = next_call(out["LOOP_CALL_MAN"], "rng women %s")
    out["LOOP_CALL_WOMAN2"] = next_call(out["LOOP_CALL_WOMAN"], "rngwomen2 %s")
    out["TAIL_CALL_MAN"] = first_call_in_chain(an[out["ANIM_LOOP_BLOCK"]].get("next"), "rng man %s")
    out["TAIL_CALL_WOMAN"] = next_call(out["TAIL_CALL_MAN"], "rng women %s")
    out["TAIL_CALL_WOMAN2"] = next_call(out["TAIL_CALL_WOMAN"], "rngwomen2 %s")

    out["AI_ENABLED_VAR"] = next(
        (vid for vid, e in an_target["variables"].items() if e[0] == "ai enabled"),
        next((vid for vid, e in target("Stage")["variables"].items() if e[0] == "ai enabled"), None)
    )
    out["CAMLIST_ID"] = next(lid for lid, e in target("Stage")["lists"].items() if e[0] == "camlist")

    return out


if __name__ == "__main__":
    work = "nightguard_extract"
    if not os.path.exists(work + "/project.json"):
        import zipfile
        sb3_path = "../sb3/1287939979.sb3"
        if os.path.exists(sb3_path):
            os.makedirs(work, exist_ok=True)
            zipfile.ZipFile(sb3_path).extract("project.json", work)
    data = json.load(open(work + "/project.json", encoding="utf-8"))
    ids = find_ids(data)
    for k, v in ids.items():
        print(f'{k} = {v!r}')
