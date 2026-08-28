"""Generic Scratch block pretty-printer, used both for inspecting block
structure precisely (with real ids) during development and for regenerating
human-readable decompiled scripts to keep this repo's docs in sync."""
import json


def desc_input(v, blocks, show_ids):
    if not isinstance(v, list):
        return repr(v)
    if v[0] in (1, 2, 3):
        inner = v[1]
        if isinstance(inner, str) and inner in blocks:
            return desc_block(inner, blocks, show_ids)
        return desc_input(inner, blocks, show_ids)
    if v[0] in (4, 5, 6, 7, 8, 9, 10, 11):
        return repr(v[1])
    if v[0] == 12:
        return f"{v[1]}"
    if v[0] == 13:
        return f"{v[1]}"
    return repr(v)


def tag(bid, show_ids):
    return f"[{bid}]" if show_ids else ""


def desc_block(bid, blocks, show_ids, depth=0):
    if depth > 12:
        return f"<{bid}>"
    b = blocks[bid]
    op = b["opcode"]
    ins = b.get("inputs", {})
    flds = b.get("fields", {})
    t = tag(bid, show_ids)
    if op == "operator_join":
        return f"{t}Join({desc_input(ins.get('STRING1'), blocks, show_ids)}, {desc_input(ins.get('STRING2'), blocks, show_ids)})"
    if op == "operator_letter_of":
        return f"{t}Letter({desc_input(ins.get('LETTER'), blocks, show_ids)}, {desc_input(ins.get('STRING'), blocks, show_ids)})"
    if op == "operator_length":
        return f"{t}Length({desc_input(ins.get('STRING'), blocks, show_ids)})"
    if op == "operator_contains":
        return f"{t}Contains({desc_input(ins.get('STRING1'), blocks, show_ids)}, {desc_input(ins.get('STRING2'), blocks, show_ids)})"
    if op == "operator_subtract":
        return f"{t}({desc_input(ins.get('NUM1'), blocks, show_ids)} - {desc_input(ins.get('NUM2'), blocks, show_ids)})"
    if op == "operator_add":
        return f"{t}({desc_input(ins.get('NUM1'), blocks, show_ids)} + {desc_input(ins.get('NUM2'), blocks, show_ids)})"
    if op == "operator_mod":
        return f"{t}({desc_input(ins.get('NUM1'), blocks, show_ids)} mod {desc_input(ins.get('NUM2'), blocks, show_ids)})"
    if op == "operator_equals":
        return f"{t}({desc_input(ins.get('OPERAND1'), blocks, show_ids)} == {desc_input(ins.get('OPERAND2'), blocks, show_ids)})"
    if op == "operator_gt":
        return f"{t}({desc_input(ins.get('OPERAND1'), blocks, show_ids)} > {desc_input(ins.get('OPERAND2'), blocks, show_ids)})"
    if op == "operator_lt":
        return f"{t}({desc_input(ins.get('OPERAND1'), blocks, show_ids)} < {desc_input(ins.get('OPERAND2'), blocks, show_ids)})"
    if op == "operator_divide":
        return f"{t}({desc_input(ins.get('NUM1'), blocks, show_ids)} / {desc_input(ins.get('NUM2'), blocks, show_ids)})"
    if op == "operator_multiply":
        return f"{t}({desc_input(ins.get('NUM1'), blocks, show_ids)} * {desc_input(ins.get('NUM2'), blocks, show_ids)})"
    if op == "sensing_timer":
        return f"{t}Sensing.Timer()"
    if op == "operator_or":
        return f"{t}({desc_input(ins.get('OPERAND1'), blocks, show_ids)} Or {desc_input(ins.get('OPERAND2'), blocks, show_ids)})"
    if op == "operator_and":
        return f"{t}({desc_input(ins.get('OPERAND1'), blocks, show_ids)} And {desc_input(ins.get('OPERAND2'), blocks, show_ids)})"
    if op == "operator_not":
        return f"{t}Not({desc_input(ins.get('OPERAND'), blocks, show_ids)})"
    if op == "operator_random":
        return f"{t}Random({desc_input(ins.get('FROM'), blocks, show_ids)}, {desc_input(ins.get('TO'), blocks, show_ids)})"
    if op == "data_variable":
        return f"{t}{flds.get('VARIABLE', [None])[0]}"
    if op == "data_itemoflist":
        return f"{t}{flds.get('LIST', [None])[0]}[{desc_input(ins.get('INDEX'), blocks, show_ids)}]"
    if op == "data_lengthoflist":
        return f"{t}List.Length({flds.get('LIST', [None])[0]})"
    if op == "data_listcontainsitem":
        return f"{t}List.Contains({flds.get('LIST', [None])[0]}, {desc_input(ins.get('ITEM'), blocks, show_ids)})"
    if op == "data_itemnumoflist":
        return f"{t}List.IndexOf({flds.get('LIST', [None])[0]}, {desc_input(ins.get('ITEM'), blocks, show_ids)})"
    if op == "sensing_mousedown":
        return f"{t}Sensing.MouseDown()"
    if op == "sensing_of":
        prop = flds.get("PROPERTY", [None])[0]
        obj = desc_input(ins.get("OBJECT"), blocks, show_ids)
        return f"{t}Sensing.Of({prop}, {obj})"
    if op == "sensing_touchingobject":
        return f"{t}Sensing.TouchingObject({desc_input(ins.get('TOUCHINGOBJECTMENU'), blocks, show_ids)})"
    if op == "looks_costumenumbername":
        return f"{t}Costume.GetNumberName({flds.get('NUMBER_NAME', [None])[0]})"
    if op == "looks_costume":
        return f"{t}{flds.get('COSTUME', [None])[0]}"
    if op == "sensing_touchingobjectmenu" or op == "control_create_clone_of_menu" or op == "sensing_of_object_menu":
        key = "TOUCHINGOBJECTMENU" if "TOUCHINGOBJECTMENU" in flds else ("CLONE_OPTION" if "CLONE_OPTION" in flds else "OBJECT")
        return f"{t}{flds.get(key, [None])[0]}"
    if op == "argument_reporter_string_number":
        return f"{t}{flds.get('VALUE', [None])[0]}"
    return f"{t}{op}({flds})"


def dump_stmt(bid, blocks, log, show_ids, depth=0, seen=None):
    if seen is None:
        seen = set()
    while bid is not None:
        if bid in seen:
            log.append("  " * depth + f"<cycle back to {bid}>")
            return
        seen = seen | {bid}
        b = blocks[bid]
        op = b["opcode"]
        ins = b.get("inputs", {})
        flds = b.get("fields", {})
        indent = "  " * depth
        t = tag(bid, show_ids)
        if op == "data_setvariableto":
            log.append(f"{indent}{t}{flds['VARIABLE'][0]} = {desc_input(ins['VALUE'], blocks, show_ids)};")
        elif op == "data_changevariableby":
            log.append(f"{indent}{t}{flds['VARIABLE'][0]} += {desc_input(ins['VALUE'], blocks, show_ids)};")
        elif op == "control_wait":
            log.append(f"{indent}{t}Control.Wait({desc_input(ins['DURATION'], blocks, show_ids)});")
        elif op == "control_repeat_until":
            log.append(f"{indent}{t}Repeat Until ({desc_input(ins['CONDITION'], blocks, show_ids)})")
            log.append(f"{indent}{{")
            dump_stmt(ins["SUBSTACK"][1], blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
        elif op == "control_repeat":
            log.append(f"{indent}{t}Repeat ({desc_input(ins['TIMES'], blocks, show_ids)})")
            log.append(f"{indent}{{")
            dump_stmt(ins["SUBSTACK"][1], blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
        elif op == "control_forever":
            log.append(f"{indent}{t}Forever")
            log.append(f"{indent}{{")
            dump_stmt(ins["SUBSTACK"][1], blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
        elif op == "control_wait_until":
            log.append(f"{indent}{t}Wait Until ({desc_input(ins['CONDITION'], blocks, show_ids)});")
        elif op == "control_if":
            log.append(f"{indent}{t}If ({desc_input(ins['CONDITION'], blocks, show_ids)})")
            log.append(f"{indent}{{")
            dump_stmt(ins["SUBSTACK"][1], blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
        elif op == "control_if_else":
            log.append(f"{indent}{t}If ({desc_input(ins['CONDITION'], blocks, show_ids)})")
            log.append(f"{indent}{{")
            dump_stmt(ins["SUBSTACK"][1], blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
            log.append(f"{indent}Else")
            log.append(f"{indent}{{")
            dump_stmt(ins["SUBSTACK2"][1], blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
        elif op == "control_stop":
            log.append(f"{indent}{t}Stop({flds.get('STOP_OPTION', [None])[0]});")
        elif op == "event_broadcast":
            log.append(f"{indent}{t}Event.Broadcast({desc_input(ins['BROADCAST_INPUT'], blocks, show_ids)});")
        elif op == "control_create_clone_of":
            log.append(f"{indent}{t}Control.CreateCloneOf({desc_input(ins['CLONE_OPTION'], blocks, show_ids)});")
        elif op == "control_start_as_clone":
            log.append(f"{indent}{t}Control.WhenIStartAsClone()")
        elif op == "looks_switchcostumeto":
            log.append(f"{indent}{t}Looks.SwitchCostumeTo({desc_input(ins['COSTUME'], blocks, show_ids)});")
        elif op == "looks_show":
            log.append(f"{indent}{t}Looks.Show();")
        elif op == "looks_hide":
            log.append(f"{indent}{t}Looks.Hide();")
        elif op == "looks_seteffectto":
            log.append(f"{indent}{t}Looks.SetEffectTo({flds.get('EFFECT', [None])[0]}, {desc_input(ins.get('VALUE'), blocks, show_ids)});")
        elif op == "looks_gotofrontback":
            log.append(f"{indent}{t}Costume.GoToFrontBack({flds.get('FRONT_BACK', [None])[0]});")
        elif op == "motion_setx":
            log.append(f"{indent}{t}Motion.SetX({desc_input(ins.get('X'), blocks, show_ids)});")
        elif op == "sensing_resettimer":
            log.append(f"{indent}{t}Sensing.ResetTimer();")
        elif op == "motion_gotoxy":
            log.append(f"{indent}{t}Motion.GoToXY({desc_input(ins.get('X'), blocks, show_ids)}, {desc_input(ins.get('Y'), blocks, show_ids)});")
        elif op == "motion_goto":
            log.append(f"{indent}{t}Motion.GoTo({desc_input(ins.get('TO'), blocks, show_ids)});")
        elif op == "motion_changexby":
            log.append(f"{indent}{t}Motion.ChangeXBy({desc_input(ins.get('DX'), blocks, show_ids)});")
        elif op == "sound_play" or op == "sound_playuntildone":
            log.append(f"{indent}{t}Sound.Play({desc_input(ins.get('SOUND_MENU'), blocks, show_ids)});")
        elif op == "data_addtolist":
            log.append(f"{indent}{t}List.Add({flds['LIST'][0]}, {desc_input(ins['ITEM'], blocks, show_ids)});")
        elif op == "data_deletealloflist":
            log.append(f"{indent}{t}List.DeleteAll({flds['LIST'][0]});")
        elif op == "data_replaceitemoflist":
            log.append(f"{indent}{t}List.ReplaceItem({flds['LIST'][0]}, {desc_input(ins['INDEX'], blocks, show_ids)}, {desc_input(ins['ITEM'], blocks, show_ids)});")
        elif op == "data_showlist":
            log.append(f"{indent}{t}List.Show({flds['LIST'][0]});")
        elif op == "data_hidelist":
            log.append(f"{indent}{t}List.Hide({flds['LIST'][0]});")
        elif op == "procedures_call":
            mutation = b.get("mutation", {})
            proto = mutation.get("proccode", "?")
            arg_ids = json.loads(mutation.get("argumentids", "[]"))
            args = [desc_input(ins[aid], blocks, show_ids) for aid in arg_ids if aid in ins]
            log.append(f"{indent}{t}Call {proto.replace('%s','').strip()}({', '.join(args)});")
        elif op == "event_whenflagclicked":
            log.append(f"{indent}{t}WhenGreenFlagClicked()")
            log.append(f"{indent}{{")
            dump_stmt(b.get("next"), blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
            return
        elif op == "event_whenbroadcastreceived":
            log.append(f"{indent}{t}WhenBroadcastReceived({flds['BROADCAST_OPTION'][0]})")
            log.append(f"{indent}{{")
            dump_stmt(b.get("next"), blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
            return
        elif op == "event_whenthisspriteclicked":
            log.append(f"{indent}{t}WhenThisSpriteClicked()")
            log.append(f"{indent}{{")
            dump_stmt(b.get("next"), blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
            return
        elif op == "event_whenkeypressed":
            log.append(f"{indent}{t}WhenKeyPressed({flds['KEY_OPTION'][0]})")
            log.append(f"{indent}{{")
            dump_stmt(b.get("next"), blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
            return
        elif op == "procedures_definition":
            proto_block = blocks[ins["custom_block"][1]]
            proto = proto_block.get("mutation", {}).get("proccode", "?")
            log.append(f"{indent}{t}Define {proto}")
            log.append(f"{indent}{{")
            bid2 = b.get("next")
            dump_stmt(bid2, blocks, log, show_ids, depth + 1, seen)
            log.append(f"{indent}}}")
            return
        else:
            log.append(f"{indent}{t}{op} fields={flds} inputs={{ {', '.join(f'{k}: {desc_input(v, blocks, show_ids)}' for k, v in ins.items())} }};")
        bid = b.get("next")


def dump_target(target, show_ids=False):
    blocks = target["blocks"]
    log = []
    for bid, b in blocks.items():
        if isinstance(b, dict) and b.get("topLevel"):
            dump_stmt(bid, blocks, log, show_ids)
            log.append("")
    return "\n".join(log)
