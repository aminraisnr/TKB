import time
import math
import maya.cmds as cmds
from maya import mel
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2

_undo_chunk_open = False

_ANGLE_UNIT_MAP = {
    "deg": om2.MAngle.kDegrees,
    "rad": om2.MAngle.kRadians,
}

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

_ANGLE_CURVE_TYPES = (oma2.MFnAnimCurve.kAnimCurveTA, oma2.MFnAnimCurve.kAnimCurveUA)
_DISTANCE_CURVE_TYPES = (oma2.MFnAnimCurve.kAnimCurveTL, oma2.MFnAnimCurve.kAnimCurveUL)

SLIDER_EASE_EXPONENT = 2.0


def safe_undo_chunk_open(chunk_name="Slider Operation"):
    global _undo_chunk_open
    if _undo_chunk_open:
        return
    try:
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        _undo_chunk_open = True
    except:
        pass


def safe_undo_chunk_close():
    global _undo_chunk_open
    if not _undo_chunk_open:
        return
    try:
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


def get_all_key_times(mfn):
    num_keys = mfn.numKeys
    return [mfn.input(i).value for i in range(num_keys)]


def get_keys_sel(anim_curves, get_from):
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
            mfn = get_mfn_anim_curve(node)
            if mfn is None:
                keys_sel.append([])
                continue
            num_keys = mfn.numKeys
            if num_keys == 0:
                keys_sel.append([])
                continue
            key_times = get_all_key_times(mfn)
            range_keys = [t for t in key_times if range_val[0] <= t < range_val[1]]
            keys_sel.append(range_keys)
    return keys_sel


def get_key_index_at_time(mfn, time_val):
    num_keys = mfn.numKeys
    for i in range(num_keys):
        if abs(mfn.input(i).value - time_val) < 0.001:
            return i
    return -1


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


def ease_value(t, exponent=SLIDER_EASE_EXPONENT):
    if t == 0:
        return 0.0
    sign = 1.0 if t > 0 else -1.0
    return sign * (abs(t) ** exponent)


_dragging = False
_original_values = {}
_pivot_values = {}
_stored_keys_sel = []
_stored_anim_curves = []
_stored_key_indexes = {}
_value_setters = {}
_value_readers = {}
_get_from = "graphEditor"
_last_scale_value = 1.0
_stored_key_ranges = {}
_fast_mode = False


def _group_into_ranges(indexes):
    if not indexes:
        return []
    ranges = []
    start = indexes[0]
    prev = indexes[0]
    for idx in indexes[1:]:
        if idx == prev + 1:
            prev = idx
        else:
            ranges.append((start, prev))
            start = idx
            prev = idx
    ranges.append((start, prev))
    return ranges


def _get_curve_node_attr(curve):
    conns = cmds.listConnections(curve + ".output", plugs=True) or []
    if conns:
        return conns[0].split(".", 1)
    return None, None


def _get_default_pivot(curve):
    node, attr = _get_curve_node_attr(curve)
    if node and attr:
        try:
            vals = cmds.attributeQuery(attr, node=node, listDefault=True)
            if vals:
                return vals[0]
        except:
            pass
    return 0.0


def cache_original_values():
    global _original_values, _pivot_values, _stored_keys_sel, _stored_anim_curves
    global _stored_key_indexes, _value_setters, _value_readers, _get_from
    global _last_scale_value, _stored_key_ranges, _fast_mode
    _original_values = {}
    _pivot_values = {}
    _stored_key_indexes = {}
    _value_setters = {}
    _value_readers = {}
    _last_scale_value = 1.0
    _stored_key_ranges = {}
    get_curves = get_anim_curves()
    _stored_anim_curves = get_curves[0]
    _get_from = get_curves[1]
    if not _stored_anim_curves:
        return
    _stored_keys_sel = get_keys_sel(_stored_anim_curves, _get_from)
    has_selected_keys = any(key_list for key_list in _stored_keys_sel if key_list)
    _fast_mode = not (has_selected_keys and _get_from == "graphEditor")
    if not has_selected_keys:
        current_time = cmds.currentTime(query=True)
        for curve in _stored_anim_curves:
            if cmds.objExists(curve):
                existing_keys = cmds.keyframe(curve, query=True, timeChange=True)
                key_exists = existing_keys and current_time in existing_keys
                cmds.setKeyframe(curve, time=current_time, insert=True)
                if not key_exists:
                    prev_key = cmds.findKeyframe(curve, time=(current_time, current_time), which="previous")
                    next_key = cmds.findKeyframe(curve, time=(current_time, current_time), which="next")
                    out_tangent_type = "auto"
                    if prev_key is not None:
                        try:
                            prev_out_tangent = cmds.keyTangent(curve, time=(prev_key, prev_key), query=True, outTangentType=True)[0]
                            if prev_out_tangent == "step":
                                out_tangent_type = "step"
                        except:
                            pass
                    if out_tangent_type != "step" and next_key is not None:
                        try:
                            next_out_tangent = cmds.keyTangent(curve, time=(next_key, next_key), query=True, outTangentType=True)[0]
                            if next_out_tangent == "step":
                                out_tangent_type = "step"
                        except:
                            pass
                    cmds.keyTangent(curve, time=(current_time, current_time), inTangentType="auto", outTangentType=out_tangent_type)
        _stored_keys_sel = []
        for curve in _stored_anim_curves:
            if cmds.objExists(curve):
                _stored_keys_sel.append([current_time])
            else:
                _stored_keys_sel.append([])
    angle_unit, linear_unit = get_current_units()
    for n, curve in enumerate(_stored_anim_curves):
        if not _stored_keys_sel[n]:
            continue
        mfn = get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        reader = make_value_reader(mfn, angle_unit, linear_unit)
        setter = make_value_setter(mfn, angle_unit, linear_unit)
        _value_readers[curve] = reader
        _value_setters[curve] = setter
        sel_times = _stored_keys_sel[n]
        indexes = []
        original_pairs = []
        for time_val in sel_times:
            idx = get_key_index_at_time(mfn, time_val)
            if idx >= 0:
                indexes.append(idx)
                original_pairs.append((time_val, reader(idx)))
        if not original_pairs:
            continue
        _stored_key_indexes[curve] = indexes
        _original_values[curve] = original_pairs
        _stored_key_ranges[curve] = _group_into_ranges(indexes)
        _pivot_values[curve] = _get_default_pivot(curve)


def scale_keys(slider_val):
    global _original_values, _pivot_values, _stored_key_indexes, _value_setters, _last_scale_value, _fast_mode
    if not _original_values:
        return
    eased_val = ease_value(slider_val)
    if eased_val >= 0:
        scale_factor = 1 + eased_val
    else:
        scale_factor = 1 + eased_val * 2
    if scale_factor == 0:
        scale_factor = 0.0000001
    if _last_scale_value != 0:
        relative_scale = scale_factor / _last_scale_value
    else:
        relative_scale = scale_factor
    if _fast_mode:
        for curve in _original_values:
            if not cmds.objExists(curve):
                continue
            pivot_val = _pivot_values[curve]
            setter = _value_setters.get(curve)
            if setter is None:
                continue
            key_indexes = _stored_key_indexes.get(curve, [])
            original_pairs = _original_values[curve]
            for i, key_index in enumerate(key_indexes):
                if i >= len(original_pairs):
                    continue
                original_val = original_pairs[i][1]
                new_val = pivot_val + (original_val - pivot_val) * scale_factor
                try:
                    setter(key_index, new_val)
                except:
                    continue
    else:
        for curve in _original_values:
            if not cmds.objExists(curve):
                continue
            pivot_val = _pivot_values[curve]
            key_ranges = _stored_key_ranges.get(curve, [])
            for start_idx, end_idx in key_ranges:
                try:
                    cmds.scaleKey(curve, index=(start_idx, end_idx), valuePivot=pivot_val, valueScale=relative_scale)
                except:
                    key_indexes = _stored_key_indexes.get(curve, [])
                    original_pairs = _original_values[curve]
                    for key_index in range(start_idx, end_idx + 1):
                        try:
                            pos = key_indexes.index(key_index)
                            original_val = original_pairs[pos][1]
                            new_val = pivot_val + (original_val - pivot_val) * scale_factor
                            cmds.keyframe(curve, index=(key_index, key_index), valueChange=new_val)
                        except:
                            continue
    _last_scale_value = scale_factor


def commit_scale_keys():
    global _original_values, _stored_key_indexes, _value_setters, _value_readers
    for curve in _original_values:
        setter = _value_setters.get(curve)
        reader = _value_readers.get(curve)
        if setter is None or reader is None:
            continue
        if not cmds.objExists(curve):
            continue
        key_indexes = _stored_key_indexes.get(curve, [])
        original_pairs = _original_values[curve]
        for i, key_index in enumerate(key_indexes):
            if i >= len(original_pairs):
                continue
            try:
                final_value = reader(key_index)
                original_val = original_pairs[i][1]
                setter(key_index, original_val)
                cmds.keyframe(curve, index=(key_index, key_index), valueChange=final_value, absolute=True)
            except:
                continue


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global _dragging
    if not mouse_pressed:
        return last_update_time, "Scale From Default: {0}".format(value)
    slider_val = value / 100.0
    current_time = time.time() * 1000
    if not _dragging:
        _dragging = True
        last_update_time = current_time
        safe_undo_chunk_open("Scale From Default")
        cmds.refresh(suspend=True)
        try:
            cache_original_values()
            scale_keys(slider_val)
        finally:
            cmds.refresh(suspend=False)
    else:
        last_update_time = current_time
        cmds.refresh(suspend=True)
        try:
            scale_keys(slider_val)
        finally:
            cmds.refresh(suspend=False)
    return last_update_time, "Scale From Default: {0}".format(value)


def reset_slider(slider_widget):
    global _dragging, _original_values, _pivot_values, _stored_keys_sel, _stored_anim_curves
    global _stored_key_indexes, _value_setters, _value_readers
    global _last_scale_value, _stored_key_ranges, _fast_mode
    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)
    if _dragging:
        cmds.refresh(suspend=True)
        try:
            commit_scale_keys()
        finally:
            cmds.refresh(suspend=False)
        safe_undo_chunk_close()
        _dragging = False
    _original_values = {}
    _pivot_values = {}
    _stored_keys_sel = []
    _stored_anim_curves = []
    _stored_key_indexes = {}
    _value_setters = {}
    _value_readers = {}
    _last_scale_value = 1.0
    _stored_key_ranges = {}
    _fast_mode = False
