import json
import sys
sys.path.insert(0, ".")
from block_builder import *

WORK = "nightguard_extract"
proj_path = WORK + "/project.json"
data = json.load(open(proj_path, encoding="utf-8"))
office = next(t for t in data["targets"] if t["name"] == "Office")["blocks"]

POWER_VAR = ("power", "cvDH$;9j@b_?E@g.5GQ~")
TIME_VAR = ("time", "(H:tSA50Z^)bE@NZ1w7D")
RIGHTDOOR = ("rightdoorstate", "kWwpbLAXTnqMRh?mebX0")
LEFTDOOR = ("leftdoorstate", "g@nlPnWg(+zgQ9Rs{.5I")


def build_length_aware_decrement(blocks, parent, var):
    """If Length(var)==2: var = Join(Letter(1,var)-1, '%')
       Else:               var = Join(Join(Letter(1,var),Letter(2,var))-1, '%')
       Returns a control_if_else block id (next=None)."""
    name, vid = var
    len_id = add_length(blocks, None, var_ref(name, vid))
    eq_id = add_equals(blocks, None, block_ref_value(len_id), str_lit("2"))
    reparent(blocks, len_id, eq_id)

    l1 = add_letter_of(blocks, None, 1, var_ref(name, vid))
    sub1 = add_subtract(blocks, None, block_ref_value(l1), num_lit(1))
    reparent(blocks, l1, sub1)
    join1 = add_join(blocks, None, block_ref_value(sub1), str_lit("%"))
    reparent(blocks, sub1, join1)
    set1 = add_setvar(blocks, None, name, vid, join1)
    reparent(blocks, join1, set1)

    l1b = add_letter_of(blocks, None, 1, var_ref(name, vid))
    l2b = add_letter_of(blocks, None, 2, var_ref(name, vid))
    joindigits = add_join(blocks, None, block_ref_value(l1b), block_ref_value(l2b))
    reparent(blocks, l1b, joindigits)
    reparent(blocks, l2b, joindigits)
    sub2 = add_subtract(blocks, None, block_ref_value(joindigits), num_lit(1))
    reparent(blocks, joindigits, sub2)
    join2 = add_join(blocks, None, block_ref_value(sub2), str_lit("%"))
    reparent(blocks, sub2, join2)
    set2 = add_setvar(blocks, None, name, vid, join2)
    reparent(blocks, join2, set2)

    ifelse = add_ifelse(blocks, parent, eq_id, set1, set2)
    reparent(blocks, eq_id, ifelse)
    reparent(blocks, set1, ifelse)
    reparent(blocks, set2, ifelse)
    return ifelse


# =====================================================================
# POWER: replace the whole buggy loop with one unified, length-safe,
# digit-boundary-safe loop. No more "-1%" sentinel, no more dead 3-digit
# branch, and door-closed now correctly double-drains at every digit count.
# =====================================================================
POWER_HAT = "Pa$?2%*%h(IEva$tWE3d"
OLD_LOOP = "AZZm6Yr$[WLhKwn^POz0"

assert office[POWER_HAT]["next"] == OLD_LOOP

# --- build: If (doors closed) { decrement; If (power != "0%") { wait 5; decrement } } Else { decrement } ---
door_cond_1 = add_equals(office, None, var_ref(*RIGHTDOOR), str_lit("closed"))
door_cond_2 = add_equals(office, None, var_ref(*LEFTDOOR), str_lit("closed"))
doors_or = add_or(office, None, block_ref_bool(door_cond_1), block_ref_bool(door_cond_2))
reparent(office, door_cond_1, doors_or)
reparent(office, door_cond_2, doors_or)

dec_a = build_length_aware_decrement(office, None, POWER_VAR)

not_zero_eq = add_equals(office, None, var_ref(*POWER_VAR), str_lit("0%"))
not_zero = add_not_equals_via_not(office, None, not_zero_eq)
reparent(office, not_zero_eq, not_zero)

wait5 = add_wait(office, None, 5)
dec_b = build_length_aware_decrement(office, None, POWER_VAR)
chain(office, [wait5, dec_b])
guarded_second_dec = add_if(office, None, not_zero, wait5)
reparent(office, not_zero, guarded_second_dec)
reparent(office, wait5, guarded_second_dec)

chain(office, [dec_a, guarded_second_dec])

dec_open = build_length_aware_decrement(office, None, POWER_VAR)

door_ifelse = add_ifelse(office, None, doors_or, dec_a, dec_open)
reparent(office, doors_or, door_ifelse)
reparent(office, dec_a, door_ifelse)
reparent(office, dec_open, door_ifelse)

wait6 = add_wait(office, None, 6)
chain(office, [wait6, door_ifelse])

loop_cond = add_equals(office, None, var_ref(*POWER_VAR), str_lit("0%"))
new_loop = add_repeat_until(office, POWER_HAT, loop_cond, wait6)
reparent(office, loop_cond, new_loop)
reparent(office, wait6, new_loop)

office[POWER_HAT]["next"] = new_loop

# delete the entire old buggy loop subtree
def collect_subtree(blocks, root):
    ids = set()
    stack = [root]
    while stack:
        bid = stack.pop()
        if bid in ids or bid not in blocks:
            continue
        ids.add(bid)
        b = blocks[bid]
        if b.get("next"):
            stack.append(b["next"])
        for v in (b.get("inputs") or {}).values():
            if isinstance(v, list) and len(v) >= 2 and isinstance(v[1], str):
                stack.append(v[1])
    return ids

for bid in collect_subtree(office, OLD_LOOP):
    del office[bid]

print("Power loop rebuilt.")

# --- remove the "-1%" sentinel watcher loop entirely (Ta!S8U...) ---
SENTINEL_HAT = "Ta!S8U)j+vuN_#G!1{qe"
sentinel_body = office[SENTINEL_HAT]["next"]
for bid in collect_subtree(office, sentinel_body):
    del office[bid]
del office[SENTINEL_HAT]
print("Sentinel loop removed.")

# --- remove the now-fully-unused `stop = 0` initialization ---
RESET_SET = "?R1N~4F0Z}wL$ESXeC~9"
STOP_SET = "jZ9^q0vDO4kU5ixbVnQl"
COUNTER_SET = "8T^aCL,vi`8VB~wuSmrc"
assert office[RESET_SET]["next"] == STOP_SET
assert office[STOP_SET]["next"] == COUNTER_SET
office[RESET_SET]["next"] = COUNTER_SET
office[COUNTER_SET]["parent"] = RESET_SET
del office[STOP_SET]
print("Unused stop=0 init removed.")

# =====================================================================
# TIME: same length-safe extraction, zero behavior change, just removes
# reliance on implicit "letter of a 1-char hour + trailing space" coercion.
# time is stored as "H AM" (H = 1 or 2 digits); wraps "13 AM" -> "1 AM".
# =====================================================================
TIME_HAT = "D=1DkwO6c;:s|9$yQ?!g"
OLD_TIME_LOOP = "?BO9m4%Y+-##J|$D=qxl"
assert office[TIME_HAT]["next"] == OLD_TIME_LOOP


def build_time_increment(blocks, parent, var):
    """hour = length-safe numeric prefix of "H AM" (1 or 2 digits before the space).
       new time = Join(hour+1, " AM")."""
    name, vid = var
    len_id = add_length(blocks, None, var_ref(name, vid))
    eq_id = add_equals(blocks, None, block_ref_value(len_id), str_lit("4"))  # "10 AM".."12 AM" -> len 5? check below
    reparent(blocks, len_id, eq_id)
    return eq_id


# time strings are "H AM" (len 4, e.g. "1 AM") or "HH AM" (len 5, e.g. "12 AM")
def build_time_increment_full(blocks, parent, var):
    name, vid = var
    len_id = add_length(blocks, None, var_ref(name, vid))
    eq5 = add_equals(blocks, None, block_ref_value(len_id), str_lit("5"))
    reparent(blocks, len_id, eq5)

    # two-digit hour branch: hour = Join(Letter(1),Letter(2))
    l1b = add_letter_of(blocks, None, 1, var_ref(name, vid))
    l2b = add_letter_of(blocks, None, 2, var_ref(name, vid))
    joindigits = add_join(blocks, None, block_ref_value(l1b), block_ref_value(l2b))
    reparent(blocks, l1b, joindigits)
    reparent(blocks, l2b, joindigits)
    plus1_b = add_add(blocks, None, block_ref_value(joindigits), num_lit(1))
    reparent(blocks, joindigits, plus1_b)
    join_b = add_join(blocks, None, block_ref_value(plus1_b), str_lit(" AM"))
    reparent(blocks, plus1_b, join_b)
    set_b = add_setvar(blocks, None, name, vid, join_b)
    reparent(blocks, join_b, set_b)

    # one-digit hour branch: hour = Letter(1)
    l1a = add_letter_of(blocks, None, 1, var_ref(name, vid))
    plus1_a = add_add(blocks, None, block_ref_value(l1a), num_lit(1))
    reparent(blocks, l1a, plus1_a)
    join_a = add_join(blocks, None, block_ref_value(plus1_a), str_lit(" AM"))
    reparent(blocks, plus1_a, join_a)
    set_a = add_setvar(blocks, None, name, vid, join_a)
    reparent(blocks, join_a, set_a)

    ifelse = add_ifelse(blocks, parent, eq5, set_b, set_a)
    reparent(blocks, eq5, ifelse)
    reparent(blocks, set_b, ifelse)
    reparent(blocks, set_a, ifelse)
    return ifelse


wrap_cond = add_equals(office, None, var_ref(*TIME_VAR), str_lit("13 AM"))
wrap_set = add_setvar_literal(office, None, TIME_VAR[0], TIME_VAR[1], "1 AM")
wrap_if = add_if(office, None, wrap_cond, wrap_set)
reparent(office, wrap_cond, wrap_if)
reparent(office, wrap_set, wrap_if)

incr = build_time_increment_full(office, None, TIME_VAR)
wait60 = add_wait(office, None, 60)
chain(office, [wait60, incr, wrap_if])

time_loop_cond = add_equals(office, None, var_ref(*TIME_VAR), str_lit("6 AM"))
new_time_loop = add_repeat_until(office, TIME_HAT, time_loop_cond, wait60)
reparent(office, time_loop_cond, new_time_loop)
reparent(office, wait60, new_time_loop)

office[TIME_HAT]["next"] = new_time_loop

for bid in collect_subtree(office, OLD_TIME_LOOP):
    del office[bid]

print("Time loop rebuilt.")

check(office, "Office")
print("Sanity check passed.")

json.dump(data, open(proj_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("project.json (v7a) written.")
