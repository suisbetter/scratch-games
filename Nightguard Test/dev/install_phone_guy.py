"""Install the Phone Guy voice system into nightguard_extract/project.json.

- Adds a hidden `PhoneGuy` sprite owning the generated voice clips (see
  gen_phone_audio.py) plus three scripts: a night-start greeting, the 1 AM-5 AM
  hourly tips, and a random warning handler.
- Wires Office's existing animatronic-detection handler to broadcast
  `phone warning` whenever it spotlights an animatronic outside an open door.
- Registers the new broadcast in Stage, stages the audio/costume asset files as
  <md5>.<ext> next to the source mp3s (dev/phone_audio/), and validates the
  whole block graph (both editing sites) with block_builder.check.

Run after `python gen_phone_audio.py` and before `python repack_sb3.py`.
"""
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import block_builder as bb

WORK = "nightguard_extract"
PROJECT = os.path.join(WORK, "project.json")
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phone_audio")

BROADCAST_NAME = "phone warning"
BROADCAST_ID = "ngvPhoneWarning"  # deduped if the id already exists
WARN_VAR_NAME = "warning"
WARN_VAR_ID = "ngvWarnSel"

COSTUME_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" '
    'viewBox="0 0 1 1"><rect width="1" height="1" fill="#000" opacity="0"/></svg>'
)


def md5_bytes(data):
    return hashlib.md5(data).hexdigest()


def var_reporter(bp, parent, name, vid, tag):
    sh = bb.new_block(bp, "data_variable", None, {}, fields={"VARIABLE": [name, vid]}, tag=tag)
    bp[sh]["shadow"] = True
    return sh


def add_time_equals(bp, parent, time_vid, hour_label):
    """operator_equals(time == 'N AM') -> block id (parent chained by caller)."""
    vr = var_reporter(bp, None, "time", time_vid, "timer")
    eq = bb.new_block(bp, "operator_equals", parent,
                      {"OPERAND1": [3, vr, [10, ""]], "OPERAND2": [1, [10, hour_label]]}, tag="teq")
    bp[vr]["parent"] = eq
    return eq


def add_wait_until(bp, parent, cond_bid, next_id=None):
    return bb.new_block(bp, "control_wait_until", parent, {"CONDITION": [2, cond_bid]},
                        next=next_id, tag="waituntil")


def add_sound_play_until_done(bp, parent, sound_name, next_id=None, tag=None):
    shadow = bb.new_block(bp, "sound_sounds_menu", None, {},
                          fields={"SOUND_MENU": [sound_name, None]}, tag="sndmenu")
    bp[shadow]["shadow"] = True
    pb = bb.new_block(bp, "sound_playuntildone", parent, {"SOUND_MENU": [1, shadow]},
                      next=next_id, tag=tag or "playdone")
    bp[shadow]["parent"] = pb
    return pb


def add_math_random(bp, parent, tag):
    lo = bb.new_block(bp, "math_number", None, {}, fields={"NUM": ["1"]}, tag="randlo")
    hi = bb.new_block(bp, "math_number", None, {}, fields={"NUM": ["4"]}, tag="randhi")
    bp[lo]["shadow"] = True
    bp[hi]["shadow"] = True
    r = bb.new_block(bp, "operator_random", parent,
                     {"FROM": [3, lo, [4, "1"]], "TO": [3, hi, [4, "4"]]}, tag=tag)
    bp[lo]["parent"] = r
    bp[hi]["parent"] = r
    return r


def main():
    data = json.load(open(PROJECT, encoding="utf-8"))
    targets = data["targets"]
    stage = next(t for t in targets if t["isStage"])
    if any(t["name"] == "PhoneGuy" for t in targets):
        print("PhoneGuy sprite already present; aborting (expected, script is not idempotent).")
        sys.exit(0)

    manifest = json.load(open(os.path.join(AUDIO_DIR, "manifest.json"), encoding="utf-8"))
    clips = manifest["clips"]

    # ---------------- Stage the asset files (md5-named for the zip) ----------------
    sounds = []
    staged = {}
    for key, meta in clips.items():
        src = os.path.join(AUDIO_DIR, meta["file"])
        raw = open(src, "rb").read()
        digest = md5_bytes(raw)
        dest = os.path.join(AUDIO_DIR, f"{digest}.mp3")
        shutil.copy2(src, dest)
        staged[dest] = True
        sounds.append({
            "name": meta["name"],
            "assetId": digest,
            "dataFormat": "mp3",
            "rate": int(manifest["sample_rate"]),
            "sampleCount": int(meta["sample_count"]),
            "md5ext": f"{digest}.mp3",
        })
    svg_bytes = COSTUME_SVG.encode("utf-8")
    svg_md5 = md5_bytes(svg_bytes)
    svg_path = os.path.join(AUDIO_DIR, f"{svg_md5}.svg")
    if not os.path.exists(svg_path):
        with open(svg_path, "wb") as f:
            f.write(svg_bytes)
    staged[svg_path] = True

    # ---------------- Dedupe broadcast/variable ids ----------------
    bid = BROADCAST_ID
    existing = set(stage.get("broadcasts", {}).keys())
    if bid in existing:
        import secrets as _secrets

        bid = "ngv" + _secrets.token_hex(8)
    stage.setdefault("broadcasts", {})[bid] = BROADCAST_NAME

    warn_id = WARN_VAR_ID
    existing_vars = set()
    for t in targets:
        existing_vars.update(t.get("variables", {}).keys())
    if warn_id in existing_vars:
        import secrets as _secrets

        warn_id = "ngv" + _secrets.token_hex(8)

    # ---------------- Build the PhoneGuy sprite ----------------
    bp = {}
    pp = {}  # helpers for immutable structure below
    del pp

    # Script A: green flag -> wait 2s -> play greeting until done
    a_play = add_sound_play_until_done(bp, None, clips["greeting"]["name"], tag="playgreet")
    a_wait = bb.new_block(bp, "control_wait", a_play, {"DURATION": [1, [5, "2"]]}, next=a_play, tag="waitgreet")
    bp[a_play]["parent"] = a_wait
    a_hat = bb.new_block(bp, "event_whenflagclicked", None, {}, next=a_wait, tag="hatgreet")
    a_hat_id = a_hat
    bp[a_wait]["parent"] = a_hat
    bp[a_hat_id]["topLevel"] = True

    # Script B: hourly tips — wait until each hour, then play that hour's clip.
    time_vid = next(vid for vid, e in stage["variables"].items() if e[0] == "time")
    b_head = None
    prev_play = None
    for hour in ["1 AM", "2 AM", "3 AM", "4 AM", "5 AM"]:
        key = hour.replace(" ", "").lower()  # 1am..5am
        play = add_sound_play_until_done(bp, None, clips[key]["name"], tag="play" + key)
        eq = add_time_equals(bp, play, time_vid, hour)
        wait = bb.new_block(bp, "control_wait_until", None, {"CONDITION": [2, eq]},
                            next=play, tag="wait" + key)
        bp[eq]["parent"] = wait
        bp[play]["parent"] = wait
        if prev_play is not None:
            bp[prev_play]["next"] = wait
            bp[wait]["parent"] = prev_play
        else:
            b_head = wait
        prev_play = play
    b_hat = bb.new_block(bp, "event_whenflagclicked", None, {}, next=b_head, tag="hathourly")
    bp[b_head]["parent"] = b_hat
    bp[b_hat]["topLevel"] = True

    # Script C: on `phone warning`, play a random warning clip until done.
    first_if = None
    prev_if = None
    for num in (4, 3, 2, 1):
        key_w = f"w{num}"
        play_note = add_sound_play_until_done(bp, None, clips[key_w]["name"], tag="play" + key_w)
        eq_n = bb.new_block(bp, "operator_equals", prev_if,
                            {"OPERAND1": [3, var_reporter(bp, None, WARN_VAR_NAME, warn_id, "warnrep%d" % num), [10, ""]],
                             "OPERAND2": [1, [10, str(num)]]}, tag="eq" + key_w)
        if_block = bb.new_block(bp, "control_if", prev_if,
                                {"CONDITION": [2, eq_n], "SUBSTACK": [2, play_note]},
                                next=None, tag="if" + key_w)
        bp[play_note]["parent"] = if_block
        bp[eq_n]["parent"] = if_block
        if prev_if is not None:
            bp[prev_if]["next"] = if_block
        else:
            first_if = if_block
        prev_if = if_block

    rand_bid = add_math_random(bp, None, "randwarn")
    set_var = bb.new_block(bp, "data_setvariableto", None,
                           {"VALUE": [3, rand_bid, [10, ""]]},
                           fields={"VARIABLE": [WARN_VAR_NAME, warn_id]}, next=first_if, tag="setwarn")
    bp[rand_bid]["parent"] = set_var
    bp[first_if]["parent"] = set_var
    c_hat = bb.new_block(bp, "event_whenbroadcastreceived", None, {},
                         fields={"BROADCAST_OPTION": [BROADCAST_NAME, bid]},
                         next=set_var, tag="hatwarn")
    bp[set_var]["parent"] = c_hat
    bp[c_hat]["topLevel"] = True

    phone_guy = {
        "isStage": False,
        "name": "PhoneGuy",
        "variables": {warn_id: [WARN_VAR_NAME, "", False]},
        "lists": {},
        "broadcasts": {bid: BROADCAST_NAME},
        "blocks": bp,
        "comments": {},
        "currentCostume": 0,
        "costumes": [{
            "name": "invisible",
            "assetId": svg_md5,
            "dataFormat": "svg",
            "md5ext": f"{svg_md5}.svg",
            "rotationCenterX": 0.5,
            "rotationCenterY": 0.5,
        }],
        "sounds": sounds,
        "volume": 100,
        "layerOrder": max(t.get("layerOrder", 0) for t in targets if not t["isStage"]) + 1,
        "visible": False,
        "x": 0,
        "y": 0,
        "size": 100,
        "direction": 90,
        "draggable": False,
        "rotationStyle": "all around",
    }
    targets.append(phone_guy)

    # ---------------- Wire Office's detection handler to broadcast warnings ----------------
    office = next(t for t in targets if t["name"] == "Office")
    ob = office["blocks"]
    ambiences = [
        pbid for pbid, b in ob.items()
        if isinstance(b, dict) and b.get("opcode") == "sound_play"
        and isinstance(b.get("inputs", {}).get("SOUND_MENU"), list)
        and len(b["inputs"]["SOUND_MENU"]) == 2
        and isinstance(b["inputs"]["SOUND_MENU"][1], str)
        and b["inputs"]["SOUND_MENU"][1] in ob
        and ob[b["inputs"]["SOUND_MENU"][1]].get("opcode") == "sound_sounds_menu"
        and ob[b["inputs"]["SOUND_MENU"][1]].get("fields", {}).get("SOUND_MENU", [None])[0]
        == "fnaf-2-ambience-sound-effect"
    ]
    if len(ambiences) != 2:
        raise AssertionError(f"expected exactly 2 ambience sound_play blocks, found {len(ambiences)}")
    for pbid in ambiences:
        play_b = ob[pbid]
        old_next = play_b.get("next")
        bc = bb.new_block(ob, "event_broadcast", pbid,
                          {"BROADCAST_INPUT": [1, [11, BROADCAST_NAME, bid]]},
                          next=old_next, tag="pbcast")
        play_b["next"] = bc
        if old_next:
            bb.reparent(ob, old_next, bc)

    # ---------------- Validate + save ----------------
    bb.check(bp, "PhoneGuy")
    bb.check(ob, "Office")
    json.dump(data, open(PROJECT, "w", encoding="utf-8"), indent=2)
    staged_files = sorted(staged.keys())
    print(f"installed PhoneGuy sprite with {len(sounds)} sounds, broadcast '{BROADCAST_NAME}' ({bid})")
    print(f"wired {len(ambiences)} Office broadcast(s); staged {len(staged_files)} asset file(s) for the zip:")
    for f in staged_files:
        print("  " + os.path.basename(f))


if __name__ == "__main__":
    main()