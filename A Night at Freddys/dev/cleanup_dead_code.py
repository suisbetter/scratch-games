"""Remove dead code from the "A Night at Freddys" Scratch project.

Operates on `extract/project.json` (a fresh extraction of ../sb3/1079847401.sb3's
project.json -- the sb3 is a zip). Run in-order with `repack_sb3.py` to write the
cleaned graph back into the sb3.

What is removed (all provably unreachable, zero behavior change):

1. The `hide` broadcast (declared on Stage) and its 7 `when I receive hide`
   handlers. The message is NEVER broadcast anywhere in the project -- verified
   by scanning every block for the broadcast's id -- so all 7 handlers are dead.

2. Stray/suspended top-level blocks that are not script-starting hats (the
   "Orphaned blocks" sections in the docs):
     - Funtime_Foxy_Jumpscare: a loose `broadcast "enter funtime auditorium"`;
       `set aggression factor to 0`; `set timer to 0` fragment, plus a bare
       `when space key pressed` hat with an empty body.
     - Ending Cutscene: a loose `broadcast "surprise ending"` and a loose
       `stop all sounds` block.

The set of blocks to delete is re-derived here at runtime (walk the chains
starting from each flagged head), so it stays correct even if block ids change
after a re-save in the editor. `procedures_definition` blocks (custom-block
definitions) are explicitly kept -- they are legitimate top-level blocks.
"""

import json
import os

WORK = "extract"
PROJECT_PATH = os.path.join(WORK, "project.json")

HATS = {
    "event_whenflagclicked",
    "event_whenkeypressed",
    "event_whenbroadcastreceived",
    "event_whenthisspriteclicked",
    "event_whencloned",
    "event_whengreatthan",
    "event_whenbackdropswitchesto",
    "event_whenstageclicked",
    "event_whenreceivingkey",
    "procedures_definition",
}


def chain_ids(blocks, head):
    ids = []
    bid = head
    while isinstance(bid, str) and bid in blocks:
        ids.append(bid)
        bid = blocks[bid].get("next")
    return ids


def main():
    data = json.load(open(PROJECT_PATH, encoding="utf-8"))

    # locate the 'hide' broadcast id
    hide_id = None
    for t in data["targets"]:
        for k, v in (t.get("broadcasts") or {}).items():
            if v == "hide":
                hide_id = k
    if hide_id is None:
        raise SystemExit("ERROR: 'hide' broadcast not found on any target")

    remove = set()
    for t in data["targets"]:
        blocks = t["blocks"]
        for bid, b in blocks.items():
            if not isinstance(b, dict):
                continue
            if not b.get("topLevel"):
                continue
            if b["opcode"] == "event_whenbroadcastreceived":
                f = b.get("fields", {}).get("BROADCAST_OPTION")
                if f and f[1] == hide_id:
                    remove.update(chain_ids(blocks, bid))
                    continue
            # empty script: a hat with nothing beneath it
            if b["opcode"] in HATS and b.get("next") is None:
                remove.add(bid)
                continue
            # stray suspended block: top-level but not a script-starting hat
            if b["opcode"] not in HATS:
                remove.update(chain_ids(blocks, bid))

        # bodies of removed control blocks are referenced via [2, id] input
        # refs rather than `next`, so flood-fill through `parent` links until
        # every block belonging to a removed script is accounted for.
        changed = True
        while changed:
            changed = False
            for bid, b in blocks.items():
                if isinstance(b, dict) and bid not in remove and b.get("parent") in remove:
                    remove.add(bid)
                    changed = True

    if not remove:
        print("nothing to remove")
        return

    # sanity: no surviving block may reference a removed id
    dangling = []
    for t in data["targets"]:
        for bid, b in t["blocks"].items():
            if not isinstance(b, dict) or bid in remove:
                continue
            for ref in (b.get("next"), b.get("parent")):
                if ref in remove:
                    dangling.append((t["name"], bid, ref))
            for inp in (b.get("inputs") or {}).values():
                if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[1], str) and inp[1] in remove:
                    dangling.append((t["name"], bid, inp[1]))

    if dangling:
        # parents can legitimately stay if the parent is being removed too; only
        # surviving blocks' references are a problem.
        still_bad = [(a, by, ref) for (a, by, ref) in dangling if by not in remove]
        if still_bad:
            raise SystemExit("ERROR: surviving blocks reference removed ids: %s" % still_bad)

    total_before = sum(1 for t in data["targets"] for b in t["blocks"].values() if isinstance(b, dict))

    # remove from every target's blocks dict
    for t in data["targets"]:
        t["blocks"] = {bid: b for bid, b in t["blocks"].items() if bid not in remove}
    # drop the now-unused 'hide' broadcast declaration
    for t in data["targets"]:
        bcasts = t.get("broadcasts") or {}
        if hide_id in bcasts:
            del bcasts[hide_id]
            print("removed 'hide' broadcast declaration from", t["name"])

    total_after = sum(1 for t in data["targets"] for b in t["blocks"].items() if isinstance(b[1], dict))
    print("removed %d block(s): %d -> %d total" % (total_before - total_after, total_before, total_after))

    json.dump(data, open(PROJECT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=None, separators=(",", ":"))
    print("wrote", PROJECT_PATH)


if __name__ == "__main__":
    main()