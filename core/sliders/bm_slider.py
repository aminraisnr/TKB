import os
import sys
import time
import math
import platform
import maya.cmds as cmds
import maya.utils
import maya.api.OpenMaya as om2
from maya import mel

from . import slider_utils

try:
    import builtins
except ImportError:
    import __builtin__ as builtins

min = builtins.min
max = builtins.max
abs = builtins.abs
round = builtins.round
sorted = builtins.sorted
set = builtins.set
list = builtins.list
dict = builtins.dict

IS_MACOS = platform.system() == "Darwin"


def _ensure_mirror_launcher_on_path():
    sliders_dir = os.path.dirname(os.path.abspath(__file__))
    animo_data_path = os.path.normpath(os.path.join(sliders_dir, ".."))
    mirror_launcher_dir = os.path.normpath(os.path.join(animo_data_path, "Animo_Launcher"))
    if mirror_launcher_dir not in sys.path:
        sys.path.insert(0, mirror_launcher_dir)


_ensure_mirror_launcher_on_path()

builtins._ANIMO_MIRROR_LAUNCHER_SUPPRESS_AUTORUN = True
try:
    import mirror_launcher as ml
except ImportError:
    ml = None
finally:
    builtins._ANIMO_MIRROR_LAUNCHER_SUPPRESS_AUTORUN = False


def _round_t(t):
    return round(t, 5)


def _partner_for(obj, table_objects):
    entry = table_objects.get(obj)
    if not entry:
        return None
    partner = entry.get("partner")
    if partner and partner != obj and cmds.objExists(partner):
        return partner
    return None


def _euler_to_quat(rx, ry, rz, order):
    euler = om2.MEulerRotation(math.radians(rx), math.radians(ry), math.radians(rz), order)
    return euler.asQuaternion()


def _quat_to_euler(quat, order):
    euler = quat.asEulerRotation()
    euler.reorderIt(order)
    return (math.degrees(euler.x), math.degrees(euler.y), math.degrees(euler.z))


def _slerp_quat(qa, qb, t):
    dot = qa.x * qb.x + qa.y * qb.y + qa.z * qb.z + qa.w * qb.w
    if dot < 0.0:
        qb = om2.MQuaternion(-qb.x, -qb.y, -qb.z, -qb.w)
        dot = -dot
    if dot > 0.9995:
        result = om2.MQuaternion(
            qa.x + t * (qb.x - qa.x),
            qa.y + t * (qb.y - qa.y),
            qa.z + t * (qb.z - qa.z),
            qa.w + t * (qb.w - qa.w),
        )
        return result.normalizeIt()
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return om2.MQuaternion(
        s0 * qa.x + s1 * qb.x,
        s0 * qa.y + s1 * qb.y,
        s0 * qa.z + s1 * qb.z,
        s0 * qa.w + s1 * qb.w,
    )


def _has_anim_curve(plug):
    try:
        conns = cmds.listConnections(plug, source=True, destination=False) or []
    except Exception:
        conns = []
    for c in conns:
        try:
            if cmds.nodeType(c).startswith("animCurve"):
                return True
        except Exception:
            continue
    return False


def _channelbox_attrs():
    try:
        channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        return cmds.channelBox(channel_box, query=True, selectedMainAttributes=True) or []
    except:
        return []


def _get_selected_graph_editor_keys():
    anim_curves, get_from = slider_utils.get_anim_curves()
    if get_from != "graphEditor" or not anim_curves:
        return []
    keys_sel = slider_utils.get_keys_sel(anim_curves, get_from)
    result = []
    for curve, times in zip(anim_curves, keys_sel):
        if not times:
            continue
        conns = cmds.listConnections(curve + ".output", plugs=True) or []
        node, attr = (conns[0].split(".", 1) if conns else (None, None))
        if not node:
            continue
        for t in times:
            result.append((curve, node, attr, t))
    return result


_targets = {}
_position = {}
_active_targets = []
_dragging = False
_click_baseline = None
_orig_graph_keys = []


def _compute_value(target, position):
    orig = target["orig"]
    mirror_target = target["target"]
    diff = orig - mirror_target
    if position >= 0:
        t = min(position, 1.0)
        return orig + (mirror_target - orig) * t
    push = -position
    return orig + diff * push


def _live_value(target):
    if target["kind"] == "key":
        try:
            v = cmds.keyframe(target["curve"], time=(target["time"], target["time"]),
                               query=True, valueChange=True)
        except Exception:
            return None
        return v[0] if v else target["orig"]
    plug = target["node"] + "." + target["attr"]
    try:
        return cmds.getAttr(plug)
    except Exception:
        return target["orig"]


def _read_axis_live(node, axis_info):
    if axis_info["kind"] == "key":
        try:
            v = cmds.keyframe(axis_info["curve"], time=(axis_info["time"], axis_info["time"]),
                               query=True, valueChange=True)
        except Exception:
            return None
        return v[0] if v else None
    plug = node + "." + axis_info["attr"]
    try:
        return cmds.getAttr(plug)
    except Exception:
        return None


def _target_diverged(key):
    target = _targets.get(key)
    if target is None:
        return False
    position = _position.get(key, 0.0)
    if target["kind"] == "rotation":
        t = _rotation_t(position)
        q_expected = _slerp_quat(target["orig_quat"], target["target_quat"], t)
        rx, ry, rz = _quat_to_euler(q_expected, target["order"])
        expected = {"X": rx, "Y": ry, "Z": rz}
        for axis_name, axis_info in target["axes"].items():
            live = _read_axis_live(target["node"], axis_info)
            if live is None:
                continue
            try:
                if abs(expected[axis_name] - live) > 1e-2:
                    return True
            except Exception:
                return True
        return False
    expected = _compute_value(target, position)
    live = _live_value(target)
    try:
        return abs(expected - live) > 1e-4
    except Exception:
        return True


def _resolve_anim_curve(plug):
    try:
        conns = cmds.listConnections(plug, source=True, destination=False) or []
    except Exception:
        conns = []
    for c in conns:
        try:
            if cmds.nodeType(c).startswith("animCurve"):
                return c
        except Exception:
            continue
    return None


def _ensure_key_at_time(plug, t):
    curve = _resolve_anim_curve(plug)
    if curve is None:
        return None
    existing = cmds.keyframe(curve, query=True, time=(t, t))
    if not existing:
        try:
            cmds.setKeyframe(plug, time=(t,))
        except Exception:
            return None
        curve = _resolve_anim_curve(plug)
    return curve


def _read_value(node, attr, time_val):
    plug = node + "." + attr
    if not cmds.objExists(plug):
        return None
    if time_val is None:
        try:
            return cmds.getAttr(plug)
        except Exception:
            return None
    curve = _resolve_anim_curve(plug)
    if curve:
        vals = cmds.keyframe(curve, query=True, time=(time_val, time_val), valueChange=True)
        if vals:
            return vals[0]
    try:
        return cmds.getAttr(plug)
    except Exception:
        return None


def _settable_value(node, attr):
    plug = node + "." + attr
    if not cmds.objExists(plug):
        return None
    try:
        if not cmds.getAttr(plug, settable=True):
            return None
    except Exception:
        return None
    try:
        value = cmds.getAttr(plug)
    except Exception:
        return None
    if isinstance(value, list):
        return None
    return value


def _register_target(key, node, attr, orig, target_value, time_val=None):
    if key in _targets:
        return
    plug = node + "." + attr
    if time_val is not None or _has_anim_curve(plug):
        resolved_time = time_val if time_val is not None else cmds.currentTime(query=True)
        curve = _ensure_key_at_time(plug, resolved_time)
        if curve:
            _targets[key] = {"kind": "key", "curve": curve, "node": node, "attr": attr,
                              "time": resolved_time, "orig": orig, "target": target_value}
        else:
            _targets[key] = {"kind": "attr", "node": node, "attr": attr,
                              "orig": orig, "target": target_value}
    else:
        _targets[key] = {"kind": "attr", "node": node, "attr": attr,
                          "orig": orig, "target": target_value}
    _position.setdefault(key, 0.0)


def _register_rotation_target(key, node, values, time_val):
    if key in _targets:
        return
    try:
        order = int(cmds.getAttr(node + ".rotateOrder"))
    except Exception:
        order = 0

    orig_rx, target_rx = values["rotateX"]
    orig_ry, target_ry = values["rotateY"]
    orig_rz, target_rz = values["rotateZ"]
    orig_quat = _euler_to_quat(orig_rx, orig_ry, orig_rz, order)
    target_quat = _euler_to_quat(target_rx, target_ry, target_rz, order)

    axes = {}
    for axis_name, attr in (("X", "rotateX"), ("Y", "rotateY"), ("Z", "rotateZ")):
        plug = node + "." + attr
        curve = None
        resolved_time = None
        if time_val is not None or _has_anim_curve(plug):
            resolved_time = time_val if time_val is not None else cmds.currentTime(query=True)
            curve = _ensure_key_at_time(plug, resolved_time)
        if curve:
            axes[axis_name] = {"attr": attr, "kind": "key", "curve": curve, "time": resolved_time}
        else:
            axes[axis_name] = {"attr": attr, "kind": "attr", "curve": None, "time": None}

    _targets[key] = {
        "kind": "rotation",
        "node": node,
        "order": order,
        "axes": axes,
        "orig_euler": (orig_rx, orig_ry, orig_rz),
        "target_euler": (target_rx, target_ry, target_rz),
        "orig_quat": orig_quat,
        "target_quat": target_quat,
    }
    _position.setdefault(key, 0.0)


def _register_node_targets(active_list, mode, node, values, time_val=None):
    rotate_names = ("rotateX", "rotateY", "rotateZ")
    if all(name in values for name in rotate_names):
        key = (mode, node, "rotate", time_val)
        _register_rotation_target(key, node, values, time_val)
        active_list.append(key)
        values = dict((a, v) for a, v in values.items() if a not in rotate_names)
    for attr, (orig, target_value) in values.items():
        key = (mode, node, attr, time_val)
        _register_target(key, node, attr, orig, target_value, time_val=time_val)
        active_list.append(key)


def _common_keyable_attrs(node_a, node_b, channel_attrs):
    attrs_a = set(ml._getKeyableUnlockedAttrs(node_a))
    attrs_b = set(ml._getKeyableUnlockedAttrs(node_b))
    common = attrs_a & attrs_b
    if channel_attrs:
        common = common & set(channel_attrs)
    return sorted(common)


def _gather_from_selection(selection, table_objects, selection_set, channel_attrs):
    processed_flip_pairs = set()
    for obj in selection:
        partner = _partner_for(obj, table_objects)
        axis = ml.mirrorAxisFor(obj, partner, table_objects)

        if partner and partner in selection_set:
            pair_key = frozenset((obj, partner))
            if pair_key in processed_flip_pairs:
                continue
            processed_flip_pairs.add(pair_key)

            attrs = _common_keyable_attrs(obj, partner, channel_attrs)
            values_a = {}
            values_b = {}
            for attr in attrs:
                orig_a = _settable_value(obj, attr)
                orig_b = _settable_value(partner, attr)
                if orig_a is None or orig_b is None:
                    continue
                values_a[attr] = (orig_a, ml.formatValue(attr, orig_b, axis))
                values_b[attr] = (orig_b, ml.formatValue(attr, orig_a, axis))
            _register_node_targets(_active_targets, "flip", obj, values_a)
            _register_node_targets(_active_targets, "flip", partner, values_b)

        elif partner:
            attrs = _common_keyable_attrs(obj, partner, channel_attrs)
            values = {}
            for attr in attrs:
                orig_src = _settable_value(obj, attr)
                orig_dest = _settable_value(partner, attr)
                if orig_src is None or orig_dest is None:
                    continue
                values[attr] = (orig_dest, ml.formatValue(attr, orig_src, axis))
            _register_node_targets(_active_targets, "mirror", partner, values)

        else:
            attrs = channel_attrs if channel_attrs else ml._getKeyableUnlockedAttrs(obj)
            values = {}
            for attr in attrs:
                orig = _settable_value(obj, attr)
                if orig is None:
                    continue
                values[attr] = (orig, ml.formatValue(attr, orig, axis))
            _register_node_targets(_active_targets, "self", obj, values)


def _gather_from_graph_keys(graph_keys, table_objects, selection_set):
    grouped = {}
    order = []
    for curve, node, attr, t in graph_keys:
        rt = _round_t(t)
        gkey = (node, rt)
        if gkey not in grouped:
            grouped[gkey] = set()
            order.append(gkey)
        grouped[gkey].add(attr)

    processed_flip_keys = set()
    for node, rt in order:
        attrs = grouped[(node, rt)]
        partner = _partner_for(node, table_objects)
        axis = ml.mirrorAxisFor(node, partner, table_objects)

        if partner and partner in selection_set:
            pair_key = (frozenset((node, partner)), rt)
            if pair_key in processed_flip_keys:
                continue
            processed_flip_keys.add(pair_key)

            values_a = {}
            values_b = {}
            for attr in attrs:
                if not cmds.attributeQuery(attr, node=partner, exists=True):
                    continue
                orig_node = _read_value(node, attr, rt)
                orig_partner = _read_value(partner, attr, rt)
                if orig_node is None or orig_partner is None:
                    continue
                values_a[attr] = (orig_node, ml.formatValue(attr, orig_partner, axis))
                values_b[attr] = (orig_partner, ml.formatValue(attr, orig_node, axis))
            _register_node_targets(_active_targets, "flip", node, values_a, time_val=rt)
            _register_node_targets(_active_targets, "flip", partner, values_b, time_val=rt)

        elif partner:
            values = {}
            for attr in attrs:
                if not cmds.attributeQuery(attr, node=partner, exists=True):
                    continue
                orig_src = _read_value(node, attr, rt)
                orig_dest = _read_value(partner, attr, rt)
                if orig_src is None or orig_dest is None:
                    continue
                values[attr] = (orig_dest, ml.formatValue(attr, orig_src, axis))
            _register_node_targets(_active_targets, "mirror", partner, values, time_val=rt)

        else:
            values = {}
            for attr in attrs:
                orig = _read_value(node, attr, rt)
                if orig is None:
                    continue
                values[attr] = (orig, ml.formatValue(attr, orig, axis))
            _register_node_targets(_active_targets, "self", node, values, time_val=rt)


def _gather_targets():
    global _targets, _position, _active_targets, _orig_graph_keys

    if ml is None:
        cmds.warning("Mirror Blend Slider: mirror_launcher module not found, skipping.")
        return False

    stale = False
    for key in list(_targets.keys()):
        if _target_diverged(key):
            stale = True
            break
    if stale:
        _targets = {}
        _position = {}

    _active_targets = []

    selection = cmds.ls(selection=True) or []
    if not selection:
        cmds.warning("Select control(s) to blend.")
        return False

    table = ml.loadTable()
    if not ml.tableCoversSelection(table, selection):
        cmds.confirmDialog(
            title="Mirror Blend Slider",
            message="Please snapshot the default rig before using this slider.",
            button=["OK"],
            defaultButton="OK"
        )
        return False

    table_objects = table.get("controls", {})
    selection_set = set(selection)

    graph_keys = _get_selected_graph_editor_keys()
    _orig_graph_keys = graph_keys
    if graph_keys:
        _gather_from_graph_keys(graph_keys, table_objects, selection_set)
    else:
        channel_attrs = _channelbox_attrs()
        _gather_from_selection(selection, table_objects, selection_set, channel_attrs)

    return bool(_active_targets)


def _apply_value(target, new_v):
    if target["kind"] == "key":
        try:
            cmds.keyframe(target["curve"], edit=True,
                           time=(target["time"], target["time"]),
                           valueChange=new_v, absolute=True)
        except Exception:
            pass
        return
    plug = target["node"] + "." + target["attr"]
    try:
        cmds.setAttr(plug, new_v)
    except Exception:
        pass


def _rotation_t(position):
    if position >= 0:
        return position if position < 1.0 else 1.0
    return position


def _apply_rotation(target, position):
    t = _rotation_t(position)
    q = _slerp_quat(target["orig_quat"], target["target_quat"], t)
    rx, ry, rz = _quat_to_euler(q, target["order"])
    values = {"X": rx, "Y": ry, "Z": rz}
    for axis_name, axis_info in target["axes"].items():
        v = values[axis_name]
        if axis_info["kind"] == "key":
            try:
                cmds.keyframe(axis_info["curve"], edit=True,
                               time=(axis_info["time"], axis_info["time"]),
                               valueChange=v, absolute=True)
            except Exception:
                pass
        else:
            plug = target["node"] + "." + axis_info["attr"]
            try:
                cmds.setAttr(plug, v)
            except Exception:
                pass


def _apply(slider_value, commit):
    for key in _active_targets:
        target = _targets.get(key)
        if target is None:
            continue
        base_position = _position.get(key, 0.0)
        position = base_position + slider_value
        if target["kind"] == "rotation":
            _apply_rotation(target, position)
        else:
            new_v = _compute_value(target, position)
            _apply_value(target, new_v)
        if commit:
            _position[key] = position if position < 1.0 else 1.0

    cmds.refresh()
    if IS_MACOS:
        maya.utils.processIdleEvents()


def _relative_slider_value(value):
    if value >= 100:
        return 1000.0
    return (value - (_click_baseline or 0)) / 100.0


def _select_keys_for_targets():
    try:
        cmds.selectKey(clear=True)
    except Exception:
        pass
    for key in _active_targets:
        target = _targets.get(key)
        if target is None:
            continue
        if target["kind"] == "rotation":
            for axis_info in target["axes"].values():
                if axis_info["kind"] != "key":
                    continue
                try:
                    cmds.selectKey(axis_info["curve"], time=(axis_info["time"], axis_info["time"]), add=True)
                except Exception:
                    pass
        elif target["kind"] == "key":
            try:
                cmds.selectKey(target["curve"], time=(target["time"], target["time"]), add=True)
            except Exception:
                pass


_chunk_open = False


def _open_chunk():
    global _chunk_open
    if not _chunk_open:
        cmds.undoInfo(openChunk=True)
        _chunk_open = True


def _close_chunk():
    global _chunk_open
    if _chunk_open:
        cmds.undoInfo(closeChunk=True)
        _chunk_open = False


def _start_drag():
    global _dragging
    _open_chunk()
    try:
        if not _gather_targets():
            _close_chunk()
            return False
    except Exception:
        _close_chunk()
        raise
    _select_keys_for_targets()
    _dragging = True
    return True


def _reset_all():
    global _targets, _position, _active_targets, _dragging, _click_baseline
    _open_chunk()
    try:
        for key, target in list(_targets.items()):
            if _position.get(key, 0.0) == 0.0:
                continue
            if target["kind"] == "rotation":
                rx, ry, rz = target["orig_euler"]
                values = {"X": rx, "Y": ry, "Z": rz}
                for axis_name, axis_info in target["axes"].items():
                    v = values[axis_name]
                    if axis_info["kind"] == "key":
                        try:
                            cmds.keyframe(axis_info["curve"], edit=True,
                                           time=(axis_info["time"], axis_info["time"]),
                                           valueChange=v, absolute=True)
                        except Exception:
                            pass
                    else:
                        plug = target["node"] + "." + axis_info["attr"]
                        try:
                            cmds.setAttr(plug, v)
                        except Exception:
                            pass
            elif target["kind"] == "key":
                try:
                    cmds.keyframe(target["curve"], edit=True,
                                   time=(target["time"], target["time"]),
                                   valueChange=target["orig"], absolute=True)
                except Exception:
                    pass
            else:
                plug = target["node"] + "." + target["attr"]
                try:
                    cmds.setAttr(plug, target["orig"])
                except Exception:
                    pass
    finally:
        _close_chunk()

    _targets = {}
    _position = {}
    _active_targets = []
    _click_baseline = None
    _dragging = False


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global _dragging, _click_baseline

    if not mouse_pressed:
        return last_update_time, None

    now = time.time()
    if (now - last_update_time) * 1000.0 < update_throttle_ms:
        return last_update_time, None

    if not _dragging:
        if not _start_drag():
            return now, None
        _click_baseline = value

    rel_value = _relative_slider_value(value)
    _apply(rel_value, commit=False)

    return now, "Blend to Mirror: {0}".format(value)


def reset_slider(slider_widget):
    global _dragging, _targets, _position, _active_targets, _click_baseline, _orig_graph_keys

    try:
        if _dragging and slider_widget is not None:
            rel_value = _relative_slider_value(slider_widget.value())
            _apply(rel_value, commit=True)
        try:
            cmds.selectKey(clear=True)
            for curve, node, attr, t in _orig_graph_keys:
                cmds.selectKey(curve, time=(t, t), add=True)
        except Exception:
            pass
    finally:
        _close_chunk()
        _dragging = False
        _targets = {}
        _position = {}
        _active_targets = []
        _click_baseline = None
        _orig_graph_keys = []
        if slider_widget is not None:
            slider_widget.setValue(0)