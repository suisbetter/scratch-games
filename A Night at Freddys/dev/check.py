"""Verify the (optionally edited) sb3 / project.json: zip integrity, graph
integrity (broken refs, orphans), asset coverage, and broadcast usage.

Usage: python check.py            # checks the sb3's current project.json
"""

import json
import sys
import zipfile

SB3 = "../sb3/1079847401.sb3"


def main():
    z = zipfile.ZipFile(SB3)
    data = json.loads(z.read("project.json").decode("utf-8"))
    bad = z.testzip()
    print("zip integrity:", "OK" if bad is None else "CORRUPT: " + str(bad))
    print("zip entries:  %d" % len(z.namelist()))

    all_ops = {}
    all_ids = {}
    broken = []
    stray_heads = []
    empty_hats = []
    total = 0
    for t in data["targets"]:
        name = t["name"]
        blocks = t["blocks"]
        for bid, b in blocks.items():
            if not isinstance(b, dict):
                continue
            total += 1
            all_ops.setdefault(b["opcode"], []).append(name)
            all_ids[bid] = name
            if b.get("topLevel") and b["opcode"] not in {"procedures_definition"}:
                if not b.get("next") and b.get("opcode") == "event_whenkeypressed":
                    empty_hats.append((name, bid, b["opcode"]))
                if b["opcode"] not in {
                    "event_whenflagclicked", "event_whenkeypressed", "event_whenbroadcastreceived",
                    "event_whenthisspriteclicked", "event_whencloned", "event_whengreatthan",
                    "event_whenbackdropswitchesto", "event_whenstageclicked", "event_whenreceivingkey",
                }:
                    stray_heads.append((name, bid, b["opcode"]))
            for ref in (b.get("next"), b.get("parent")):
                if isinstance(ref, str) and ref not in blocks:
                    broken.append((name, bid, "->", ref))
            for k, v in (b.get("inputs") or {}).items():
                if isinstance(v, list) and len(v) >= 2 and isinstance(v[1], str) and v[1] not in blocks:
                    broken.append((name, bid, "input " + k, v[1]))

    print("total blocks: %d" % total)
    print("broken refs:  %d %s" % (len(broken), broken[:5]))
    print("stray non-hat topLevel heads: %d %s" % (len(stray_heads), stray_heads[:5]))
    print("empty key-pressed hats: %d %s" % (len(empty_hats), empty_hats[:5]))

    # asset coverage
    refs = set()
    for t in data["targets"]:
        for m in (t.get("costumes") or []) + (t.get("sounds") or []) + (t.get("backdrops") or []):
            refs.add(m["md5ext"])
    members = set(z.namelist())
    missing = refs - members
    unused = [m for m in members if m != "project.json" and m not in refs]
    print("assets in json refs: %d" % len(refs))
    print("unreferenced zip members: %d" % len(unused))
    print("referenced-but-missing: %d" % len(missing))

    # dead broadcasts
    sent = set()
    received = set()
    for t in data["targets"]:
        for b in t["blocks"].values():
            if not isinstance(b, dict):
                continue
            if b["opcode"] in {"event_broadcast", "event_broadcastandwait"}:
                f = b.get("inputs", {}).get("BROADCAST_INPUT")
                if f and isinstance(f[1], list) and len(f[1]) == 3:
                    sent.add(f[1][2])
            if b["opcode"] == "event_whenbroadcastreceived":
                received.add(b["fields"]["BROADCAST_OPTION"][1])
    declared = {}
    for t in data["targets"]:
        for k, v in (t.get("broadcasts") or {}).items():
            declared[k] = v
    print("broadcasts declared: %d" % len(declared))
    print("never sent but declared/handled: %s" % (received - sent))
    print("sent but never declared: %s" % (sent - set(declared)))

    return 0 if not broken and not missing else 1


if __name__ == "__main__":
    sys.exit(main())