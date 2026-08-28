"""A from-scratch (pun intended) interpreter for the subset of Scratch 3.0
opcodes this project actually uses. Built to run this project's own
project.json directly and verify real semantics -- not a mock of expected
behavior. Time-based blocks (`wait`) are simulated instantly (no real
sleeping); this models causal order and final state correctly for our
purposes (no two threads race against a real clock in this project's
door/power/time logic -- everything is single-threaded per broadcast).
"""
import json


def to_number(v):
    """Scratch's Cast.toNumber, which scratch-vm implements as JavaScript's
    Number(value) with NaN -> 0. Critically, Number() requires the *entire*
    trimmed string to be numeric -- "50%" is NaN (not 50), "12 AM" is NaN
    (not 12). There is no "parse a leading numeric run" fallback in real
    Scratch; a previous version of this function had one, which let a real
    bug (arithmetic done directly on a "N%"/"N AM"-style string instead of
    first stripping the suffix via Letter/Join) pass here while still
    breaking in the actual engine. Don't reintroduce that fallback."""
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s == "" or "_" in s:  # Python's int()/float() accept "1_000"; JS Number() does not
        return 0
    try:
        return float(s) if ("." in s or "e" in s.lower()) else int(s)
    except ValueError:
        return 0


class Interpreter:
    def __init__(self, project_json, on_broadcast=None):
        self.data = project_json
        self.targets = {t["name"]: t for t in self.data["targets"]}
        self.stage = next(t for t in self.data["targets"] if t["isStage"])
        self.varstate = {}
        for vid, entry in self.stage["variables"].items():
            self.varstate[vid] = entry[1]
        self.varname_to_id = {entry[0]: vid for vid, entry in self.stage["variables"].items()}
        self.liststate = {}
        for lid, entry in self.stage.get("lists", {}).items():
            self.liststate[lid] = list(entry[1])
        self.listname_to_id = {entry[0]: lid for lid, entry in self.stage.get("lists", {}).items()}
        self.costumes = {}  # sprite name -> current costume name
        for name in self.targets:
            self.costumes[name] = "costume1"
        self.on_broadcast = on_broadcast or (lambda msg: None)
        self.log = []
        self.mock_mousedown = False
        self.param_stack = []  # stack of dicts: param name -> value, for nested procedure calls

    def blocks_for(self, sprite):
        return self.targets[sprite]["blocks"]

    def get_var(self, vid):
        return self.varstate.get(vid, "")

    def set_var(self, vid, val):
        self.varstate[vid] = val

    def get_list(self, lid):
        return self.liststate.setdefault(lid, [])

    # ---------------- expression evaluation ----------------
    def eval_input(self, sprite, inp, blocks):
        kind = inp[0]
        if kind in (1, 3):
            val = inp[1]
            if isinstance(val, str):
                return self.eval_block(sprite, val, blocks)
            return self.literal_value(val)
        if kind == 2:
            return self.eval_block(sprite, inp[1], blocks)
        raise Exception(f"unhandled input kind {kind}")

    def literal_value(self, val):
        if isinstance(val, list):
            t = val[0]
            if t in (4, 5, 6, 7, 8, 9, 10, 11):
                return val[1]
            if t == 12:
                return self.get_var(val[2])
            if t == 13:
                return self.get_list(val[2])
        return val

    def eval_block(self, sprite, bid, blocks):
        b = blocks[bid]
        op = b["opcode"]
        ins = b.get("inputs", {})
        flds = b.get("fields", {})

        if op == "operator_equals":
            o1 = self.eval_input(sprite, ins["OPERAND1"], blocks)
            o2 = self.eval_input(sprite, ins["OPERAND2"], blocks)
            return self._scratch_equals(o1, o2)
        if op == "operator_and":
            return bool(self.eval_input(sprite, ins["OPERAND1"], blocks)) and bool(self.eval_input(sprite, ins["OPERAND2"], blocks))
        if op == "operator_or":
            return bool(self.eval_input(sprite, ins["OPERAND1"], blocks)) or bool(self.eval_input(sprite, ins["OPERAND2"], blocks))
        if op == "operator_not":
            return not bool(self.eval_input(sprite, ins["OPERAND"], blocks))
        if op == "operator_join":
            return str(self.eval_input(sprite, ins["STRING1"], blocks)) + str(self.eval_input(sprite, ins["STRING2"], blocks))
        if op == "operator_letter_of":
            idx = int(to_number(self.eval_input(sprite, ins["LETTER"], blocks)))
            s = str(self.eval_input(sprite, ins["STRING"], blocks))
            return s[idx - 1] if 1 <= idx <= len(s) else ""
        if op == "operator_length":
            return len(str(self.eval_input(sprite, ins["STRING"], blocks)))
        if op == "operator_contains":
            s1 = str(self.eval_input(sprite, ins["STRING1"], blocks)).lower()
            s2 = str(self.eval_input(sprite, ins["STRING2"], blocks)).lower()
            return s2 in s1
        if op == "operator_subtract":
            return to_number(self.eval_input(sprite, ins["NUM1"], blocks)) - to_number(self.eval_input(sprite, ins["NUM2"], blocks))
        if op == "operator_add":
            return to_number(self.eval_input(sprite, ins["NUM1"], blocks)) + to_number(self.eval_input(sprite, ins["NUM2"], blocks))
        if op == "operator_mod":
            return to_number(self.eval_input(sprite, ins["NUM1"], blocks)) % to_number(self.eval_input(sprite, ins["NUM2"], blocks))
        if op == "operator_random":
            lo = to_number(self.eval_input(sprite, ins["FROM"], blocks))
            hi = to_number(self.eval_input(sprite, ins["TO"], blocks))
            mid = (lo + hi) / 2
            if float(lo).is_integer() and float(hi).is_integer():
                return int(round(mid))  # Scratch picks a whole number when both bounds are whole
            return mid
        if op == "sensing_mousedown":
            return self.mock_mousedown
        if op == "sensing_touchingobject":
            return True  # assume "touching mouse" true when we're synthesizing a click
        if op == "sensing_of":
            prop = flds["PROPERTY"][0]
            obj_menu = ins.get("OBJECT")
            return 0  # positions unused by our logic checks
        if op == "looks_costumenumbername":
            mode = flds.get("NUMBER_NAME", ["number"])[0]
            name = self.costumes[sprite]
            if mode == "name":
                return name
            digits = "".join(ch for ch in name if ch.isdigit())
            return int(digits) if digits else 0
        if op == "data_variable":
            return self.get_var(flds["VARIABLE"][1])
        if op == "data_itemoflist":
            lid = flds["LIST"][1]
            idx = int(to_number(self.eval_input(sprite, ins["INDEX"], blocks)))
            lst = self.get_list(lid)
            return lst[idx - 1] if 1 <= idx <= len(lst) else ""
        if op == "data_lengthoflist":
            return len(self.get_list(flds["LIST"][1]))
        if op == "data_itemnumoflist":
            item = self.eval_input(sprite, ins["ITEM"], blocks)
            lst = self.get_list(flds["LIST"][1])
            try:
                return lst.index(item) + 1
            except ValueError:
                return 0
        if op == "argument_reporter_string_number":
            name = flds["VALUE"][0]
            if self.param_stack and name in self.param_stack[-1]:
                return self.param_stack[-1][name]
            return ""
        raise Exception(f"unhandled reporter opcode {op} in {sprite}")

    def _scratch_equals(self, a, b):
        try:
            return float(a) == float(b)
        except (ValueError, TypeError):
            return str(a) == str(b)

    # ---------------- statement execution ----------------
    def run_stack(self, sprite, bid, blocks, depth=0):
        """Returns True if 'stop this script' (or stop all) was hit."""
        while bid is not None:
            b = blocks[bid]
            op = b["opcode"]
            ins = b.get("inputs", {})
            flds = b.get("fields", {})
            if op == "data_setvariableto":
                vid = flds["VARIABLE"][1]
                val = self.eval_input(sprite, ins["VALUE"], blocks)
                self.set_var(vid, val)
                self.log.append(f"{sprite}: SET {flds['VARIABLE'][0]} = {val!r}")
            elif op == "data_changevariableby":
                vid = flds["VARIABLE"][1]
                delta = to_number(self.eval_input(sprite, ins["VALUE"], blocks))
                self.set_var(vid, to_number(self.get_var(vid)) + delta)
            elif op == "looks_switchcostumeto":
                shadow = ins["COSTUME"][1]
                cname = blocks[shadow]["fields"]["COSTUME"][0] if isinstance(shadow, str) else shadow
                self.costumes[sprite] = cname
                self.log.append(f"{sprite}: costume -> {cname}")
            elif op == "control_wait":
                dur = self.eval_input(sprite, ins["DURATION"], blocks)
                self.log.append(f"{sprite}: WAIT {dur}")
            elif op in ("looks_show", "looks_hide", "looks_gotofrontback", "looks_seteffectto",
                        "motion_gotoxy", "motion_goto", "motion_changexby", "sound_play",
                        "control_create_clone_of", "data_addtolist", "data_deletealloflist",
                        "data_replaceitemoflist", "data_showlist", "data_hidelist"):
                if op == "data_addtolist":
                    lid = flds["LIST"][1]
                    val = self.eval_input(sprite, ins["ITEM"], blocks)
                    self.get_list(lid).append(val)
                elif op == "data_deletealloflist":
                    lid = flds["LIST"][1]
                    self.liststate[lid] = []
                elif op == "data_replaceitemoflist":
                    lid = flds["LIST"][1]
                    idx = int(to_number(self.eval_input(sprite, ins["INDEX"], blocks)))
                    val = self.eval_input(sprite, ins["ITEM"], blocks)
                    lst = self.get_list(lid)
                    while len(lst) < idx:
                        lst.append("")
                    if idx >= 1:
                        lst[idx - 1] = val
                # wait/show/hide/motion/sound/clone: no-ops for our verification purposes
            elif op == "event_broadcast":
                msg = self.eval_input(sprite, ins["BROADCAST_INPUT"], blocks)
                self.log.append(f"{sprite}: BROADCAST {msg!r}")
                self.on_broadcast(msg)
            elif op == "control_stop":
                opt = flds.get("STOP_OPTION", [None])[0]
                self.log.append(f"{sprite}: STOP {opt}")
                return True
            elif op == "control_if":
                cond = self.eval_input(sprite, ins["CONDITION"], blocks)
                if cond:
                    if self.run_stack(sprite, ins["SUBSTACK"][1], blocks, depth + 1):
                        return True
            elif op == "control_if_else":
                cond = self.eval_input(sprite, ins["CONDITION"], blocks)
                branch = ins["SUBSTACK"][1] if cond else ins["SUBSTACK2"][1]
                if self.run_stack(sprite, branch, blocks, depth + 1):
                    return True
            elif op == "control_repeat_until":
                guard = 0
                while not self.eval_input(sprite, ins["CONDITION"], blocks):
                    if self.run_stack(sprite, ins["SUBSTACK"][1], blocks, depth + 1):
                        return True
                    guard += 1
                    if guard > 500:
                        raise Exception(f"control_repeat_until exceeded 500 iterations in {sprite} at {bid}")
            elif op == "control_repeat":
                times = int(to_number(self.eval_input(sprite, ins["TIMES"], blocks)))
                for _ in range(times):
                    if self.run_stack(sprite, ins["SUBSTACK"][1], blocks, depth + 1):
                        return True
            elif op == "control_forever":
                pass  # never iterate in this static test harness (see driver for tick-based hats)
            elif op in ("control_wait_until",):
                pass
            elif op in ("event_whenflagclicked", "event_whenbroadcastreceived",
                        "event_whenthisspriteclicked", "control_start_as_clone",
                        "event_whenkeypressed"):
                pass
            elif op == "procedures_call":
                if self._call_procedure(sprite, b, blocks, depth):
                    return True
            else:
                raise Exception(f"unhandled stmt opcode {op} in {sprite} ({bid})")
            bid = b.get("next")
        return False

    def _call_procedure(self, sprite, call_block, blocks, depth):
        mutation = call_block.get("mutation", {})
        proto = mutation.get("proccode")
        arg_ids = json.loads(mutation.get("argumentids", "[]"))
        arg_values = [self.eval_input(sprite, call_block["inputs"][aid], blocks) for aid in arg_ids if aid in call_block["inputs"]]
        for bid, b in blocks.items():
            if isinstance(b, dict) and b.get("opcode") == "procedures_definition":
                proto_block = blocks[b["inputs"]["custom_block"][1]]
                proto_mutation = proto_block.get("mutation", {})
                if proto_mutation.get("proccode") == proto:
                    param_names = json.loads(proto_mutation.get("argumentnames", "[]"))
                    self.param_stack.append(dict(zip(param_names, arg_values)))
                    try:
                        return self.run_stack(sprite, b["next"], blocks, depth + 1)
                    finally:
                        self.param_stack.pop()
        raise Exception(f"procedure not found: {proto}")

    def start_hats(self, sprite, opcode, match_fields=None):
        blocks = self.blocks_for(sprite)
        for bid, b in blocks.items():
            if isinstance(b, dict) and b.get("topLevel") and b.get("opcode") == opcode:
                if match_fields:
                    if not all(b.get("fields", {}).get(k, [None])[0] == v for k, v in match_fields.items()):
                        continue
                self.run_stack(sprite, b.get("next"), blocks)
