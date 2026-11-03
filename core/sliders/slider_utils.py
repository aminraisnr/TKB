import maya.cmds as cmds
from maya import mel
import maya.utils
import platform
import os
import json
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import math

IS_MACOS = platform.system() == "Darwin"

_undo_chunk_open = False

OVERSHOOT_PREFS_FILE_NAME = "sliders_overshoot.json"
OVERSHOOT_RANGE_RATIO = 0.3
_overshoot_enabled_cache = None


def get_animo_data_path():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(script_dir, ".."))
    except NameError:
        version_script_dir = cmds.internalVar(userScriptDir=True)
        script_dir = os.path.normpath(os.path.join(version_script_dir, "..", "..", "scripts"))
        return os.path.join(script_dir, "Animo_Data")


def get_prefs_path():
    animo_data = get_animo_data_path()
    prefs_dir = os.path.join(animo_data, "Animo_Prefs")
    if not os.path.exists(prefs_dir):
        try:
            os.makedirs(prefs_dir)
        except:
            pass
    return prefs_dir


def get_overshoot_prefs_file():
    return os.path.join(get_prefs_path(), OVERSHOOT_PREFS_FILE_NAME)


def is_overshoot_enabled():
    global _overshoot_enabled_cache
    if _overshoot_enabled_cache is not None:
        return _overshoot_enabled_cache
    prefs_file = get_overshoot_prefs_file()
    try:
        with open(prefs_file, "r") as f:
            data = json.load(f)
        _overshoot_enabled_cache = bool(data.get("overshoot_enabled", False))
    except:
        _overshoot_enabled_cache = False
    return _overshoot_enabled_cache


def set_overshoot_enabled(enabled):
    global _overshoot_enabled_cache
    _overshoot_enabled_cache = bool(enabled)
    prefs_file = get_overshoot_prefs_file()
    try:
        with open(prefs_file, "w") as f:
            json.dump({"overshoot_enabled": bool(enabled)}, f)
    except:
        pass


def safe_undo_chunk_open(chunk_name="Slider Operation"):
    global _undo_chunk_open
    if _undo_chunk_open:
        return
    try:
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        _undo_chunk_open = True
        if IS_MACOS:
            maya.utils.processIdleEvents()
    except:
        pass


def safe_undo_chunk_close():
    global _undo_chunk_open
    if not _undo_chunk_open:
        return
    try:
        if IS_MACOS:
            cmds.refresh()
            maya.utils.processIdleEvents()
        cmds.undoInfo(closeChunk=True)
        _undo_chunk_open = False
    except:
        pass


def get_mobject(node_name):
    try:
        sel = om2.MSelectionList()
        sel.add(node_name)
        return sel.getDependNode(0)
    except:
        return None


def get_mfn_anim_curve(node_name):
    mobj = get_mobject(node_name)
    if mobj is None:
        return None
    try:
        return oma2.MFnAnimCurve(mobj)
    except:
        return None


def get_mfn_anim_curves_bulk(node_names):
    result = {}
    if not node_names:
        return result
    sel = om2.MSelectionList()
    ordered_names = []
    for name in node_names:
        try:
            sel.add(name)
            ordered_names.append(name)
        except:
            continue
    for i, name in enumerate(ordered_names):
        try:
            mobj = sel.getDependNode(i)
            result[name] = oma2.MFnAnimCurve(mobj)
        except:
            continue
    return result


def is_angle_curve(mfn):
    """Check if the anim curve is for a rotation/angle attribute (returns radians)"""
    try:
        return mfn.animCurveType == oma2.MFnAnimCurve.kAnimCurveTA
    except:
        return False


def get_key_value(mfn, index):
    """Get key value, converting radians to degrees for rotation curves"""
    value = mfn.value(index)
    if is_angle_curve(mfn):
        value = math.degrees(value)
    return value


def get_anim_curves():
    anim_curves = cmds.keyframe(query=True, name=True, selected=True)
    get_from = "graphEditor"
    if not anim_curves:
        get_from = "channelBox"
        selected_objects = cmds.ls(selection=True)
        if selected_objects:
            channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
            selected_attrs = cmds.channelBox(channel_box, query=True, selectedMainAttributes=True)
            if selected_attrs:
                plugs = [
                    '{0}.{1}'.format(obj, attr)
                    for obj in selected_objects
                    for attr in selected_attrs
                ]
                valid_plugs = cmds.ls(plugs) if plugs else []
                if valid_plugs:
                    connections = cmds.listConnections(
                        valid_plugs,
                        source=True,
                        destination=False,
                        type='animCurve'
                    )
                    if connections:
                        anim_curves = list(set(connections))
    if not anim_curves:
        get_from = "timeline"
        play_back_slider = mel.eval('$temp=$gPlayBackSlider')
        anim_curves = cmds.timeControl(play_back_slider, query=True, animCurveNames=True)
    return [anim_curves, get_from]


def get_timeline_range():
    play_back_slider = mel.eval('$temp_playBackSlider=$gPlayBackSlider')
    time_range = cmds.timeControl(play_back_slider, query=True, rangeArray=True)
    start_range = int(time_range[0])
    end_range = int(time_range[1] - 1)
    return [start_range, end_range]


def get_keys_sel(anim_curves, get_from, mfn_cache=None, key_times_cache=None):
    if not anim_curves:
        return []
    keys_sel = []
    if get_from == "graphEditor":
        for node in anim_curves:
            keys = cmds.keyframe(node, selected=True, query=True, timeChange=True)
            keys_sel.append(keys if keys else [])
    else:
        range_val = get_timeline_range()
        for node in anim_curves:
            mfn = mfn_cache.get(node) if mfn_cache is not None else None
            if mfn is None:
                mfn = get_mfn_anim_curve(node)
                if mfn is not None and mfn_cache is not None:
                    mfn_cache[node] = mfn
            if mfn is None:
                keys_sel.append([])
                continue
            num_keys = mfn.numKeys
            if num_keys == 0:
                keys_sel.append([])
                continue
            key_times = get_all_key_times(mfn)
            if key_times_cache is not None:
                key_times_cache[node] = key_times
            range_keys = [t for t in key_times if range_val[0] <= t < range_val[1]]
            keys_sel.append(range_keys)
    return keys_sel


def get_key_index_at_time(mfn, time_val):
    num_keys = mfn.numKeys
    for i in range(num_keys):
        if abs(mfn.input(i).value - time_val) < 0.001:
            return i
    return -1


def get_key_indexes(curve, key_times):
    if not key_times:
        return []
    mfn = get_mfn_anim_curve(curve)
    if mfn is None:
        return []
    indexes = []
    for key_time in key_times:
        idx = get_key_index_at_time(mfn, key_time)
        if idx >= 0:
            indexes.append(idx)
    return indexes


def get_all_key_times(mfn):
    num_keys = mfn.numKeys
    return [mfn.input(i).value for i in range(num_keys)]


def get_all_key_values(mfn):
    """Get all key values, converting radians to degrees for rotation curves"""
    num_keys = mfn.numKeys
    if is_angle_curve(mfn):
        return [math.degrees(mfn.value(i)) for i in range(num_keys)]
    return [mfn.value(i) for i in range(num_keys)]


def set_key_value(curve, index, value):
    cmds.keyframe(curve, index=(index, index), valueChange=value, absolute=True)


_DISTANCE_UNIT_MAP = {
    "mm": om2.MDistance.kMillimeters,
    "cm": om2.MDistance.kCentimeters,
    "m": om2.MDistance.kMeters,
    "km": om2.MDistance.kKilometers,
    "in": om2.MDistance.kInches,
    "ft": om2.MDistance.kFeet,
    "yd": om2.MDistance.kYards,
    "mi": om2.MDistance.kMiles,
}

_ANGLE_UNIT_MAP = {
    "deg": om2.MAngle.kDegrees,
    "rad": om2.MAngle.kRadians,
}

_ANGLE_CURVE_TYPES = (oma2.MFnAnimCurve.kAnimCurveTA, oma2.MFnAnimCurve.kAnimCurveUA)
_DISTANCE_CURVE_TYPES = (oma2.MFnAnimCurve.kAnimCurveTL, oma2.MFnAnimCurve.kAnimCurveUL)


def make_value_setter(mfn, angle_unit_name, linear_unit_name):
    curve_type = mfn.animCurveType
    if curve_type in _ANGLE_CURVE_TYPES:
        unit = _ANGLE_UNIT_MAP.get(angle_unit_name, om2.MAngle.kDegrees)
        toRadians = om2.MAngle(1.0, unit).asRadians()

        def setter(index, value):
            mfn.setValue(index, value * toRadians)

        return setter
    if curve_type in _DISTANCE_CURVE_TYPES:
        unit = _DISTANCE_UNIT_MAP.get(linear_unit_name, om2.MDistance.kCentimeters)
        toCentimeters = om2.MDistance(1.0, unit).asCentimeters()

        def setter(index, value):
            mfn.setValue(index, value * toCentimeters)

        return setter

    def setter(index, value):
        mfn.setValue(index, value)

    return setter


def make_value_reader(mfn, angle_unit_name, linear_unit_name):
    curve_type = mfn.animCurveType
    if curve_type in _ANGLE_CURVE_TYPES:
        unit = _ANGLE_UNIT_MAP.get(angle_unit_name, om2.MAngle.kDegrees)
        fromRadians = om2.MAngle(1.0, om2.MAngle.kRadians).asUnits(unit)

        def reader(index):
            return mfn.value(index) * fromRadians

        return reader
    if curve_type in _DISTANCE_CURVE_TYPES:
        unit = _DISTANCE_UNIT_MAP.get(linear_unit_name, om2.MDistance.kCentimeters)
        fromCentimeters = om2.MDistance(1.0, om2.MDistance.kCentimeters).asUnits(unit)

        def reader(index):
            return mfn.value(index) * fromCentimeters

        return reader

    def reader(index):
        return mfn.value(index)

    return reader


def get_current_units():
    return cmds.currentUnit(query=True, angle=True), cmds.currentUnit(query=True, linear=True)


SLIDER_EASE_EXPONENT = 2.0
SLIDER_EASE_STRENGTH = 6.0


def ease_value(t, exponent=SLIDER_EASE_EXPONENT):
    if t == 0:
        return 0.0
    sign = 1.0 if t > 0 else -1.0
    return sign * (abs(t) ** exponent)


def ease_exponential(t, k=SLIDER_EASE_STRENGTH):
    if t == 0:
        return 0.0
    sign = 1.0 if t > 0 else -1.0
    at = abs(t)
    denom = math.exp(k) - 1.0
    if denom == 0:
        return sign * at
    return sign * ((math.exp(k * at) - 1.0) / denom)


def centered_ease(value, exponent=SLIDER_EASE_EXPONENT):
    return 1.0 + ease_value(value / 100.0, exponent)


def folded_ease(value, exponent=SLIDER_EASE_EXPONENT):
    return 1.0 - ease_value(abs(value) / 100.0, exponent)