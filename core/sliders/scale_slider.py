import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import time

try:
    from . import slider_utils
except ImportError:
    import slider_utils

IS_MACOS = slider_utils.IS_MACOS

_dragging = False
_current_mode = None
_original_values = {}
_pivot_values = {}
_stored_keys_sel = []
_stored_anim_curves = []
_stored_key_indexes = {}
_mfn_curves = {}
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


def cache_original_values(mode):
    global _original_values, _pivot_values, _stored_keys_sel, _stored_anim_curves
    global _stored_key_indexes, _mfn_curves, _value_setters, _value_readers, _current_mode, _get_from
    global _last_scale_value, _stored_key_ranges, _fast_mode
    _original_values = {}
    _pivot_values = {}
    _stored_key_indexes = {}
    _mfn_curves = {}
    _value_setters = {}
    _value_readers = {}
    _current_mode = mode
    _last_scale_value = 1.0
    _stored_key_ranges = {}
    get_curves = slider_utils.get_anim_curves()
    _stored_anim_curves = get_curves[0]
    _get_from = get_curves[1]
    if not _stored_anim_curves:
        return
    _stored_keys_sel = slider_utils.get_keys_sel(_stored_anim_curves, _get_from)
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
    angle_unit, linear_unit = slider_utils.get_current_units()
    for n, curve in enumerate(_stored_anim_curves):
        if not _stored_keys_sel[n]:
            continue
        mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        _mfn_curves[curve] = mfn
        reader = slider_utils.make_value_reader(mfn, angle_unit, linear_unit)
        setter = slider_utils.make_value_setter(mfn, angle_unit, linear_unit)
        _value_readers[curve] = reader
        _value_setters[curve] = setter
        sel_times = _stored_keys_sel[n]
        num_keys = mfn.numKeys
        indexes = []
        original_pairs = []
        for time_val in sel_times:
            idx = slider_utils.get_key_index_at_time(mfn, time_val)
            if idx >= 0:
                indexes.append(idx)
                original_pairs.append((time_val, reader(idx)))
        if not original_pairs:
            continue
        _stored_key_indexes[curve] = indexes
        _original_values[curve] = original_pairs
        _stored_key_ranges[curve] = _group_into_ranges(indexes)
        if mode == "left":
            first_idx = indexes[0]
            if first_idx > 0:
                pivot_val = reader(first_idx - 1)
            else:
                pivot_val = original_pairs[0][1]
        elif mode == "right":
            last_idx = indexes[-1]
            if last_idx < num_keys - 1:
                pivot_val = reader(last_idx + 1)
            else:
                pivot_val = original_pairs[-1][1]
        else:
            values = [v for _, v in original_pairs]
            if len(values) == 1:
                single_idx = indexes[0]
                neighbor_values = []
                if single_idx > 0:
                    neighbor_values.append(reader(single_idx - 1))
                if single_idx < num_keys - 1:
                    neighbor_values.append(reader(single_idx + 1))
                if neighbor_values:
                    pivot_val = sum(neighbor_values) / len(neighbor_values)
                else:
                    pivot_val = 0.0
            else:
                min_val, max_val = min(values), max(values)
                pivot_val = (min_val + max_val) / 2.0
        _pivot_values[curve] = pivot_val


def scale_keys(slider_val):
    global _original_values, _pivot_values, _stored_key_indexes, _value_setters, _last_scale_value, _fast_mode
    if not _original_values:
        return
    eased_val = slider_utils.ease_value(slider_val)
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


def scale_left_logic(value, last_update_time, update_throttle_ms):
    global _dragging
    slider_val = value / 100.0
    current_time = time.time() * 1000
    time_since_last = current_time - last_update_time
    if not _dragging:
        _dragging = True
        last_update_time = current_time
        slider_utils.safe_undo_chunk_open("Scale Left")
        cmds.refresh(suspend=True)
        try:
            cache_original_values("left")
            scale_keys(slider_val)
        finally:
            cmds.refresh(suspend=False)
    else:
        if time_since_last >= update_throttle_ms:
            last_update_time = current_time
            cmds.refresh(suspend=True)
            try:
                scale_keys(slider_val)
            finally:
                cmds.refresh(suspend=False)
    return last_update_time, "Scale Left: {0}".format(value)


def scale_right_logic(value, last_update_time, update_throttle_ms):
    global _dragging
    slider_val = value / 100.0
    current_time = time.time() * 1000
    time_since_last = current_time - last_update_time
    if not _dragging:
        _dragging = True
        last_update_time = current_time
        slider_utils.safe_undo_chunk_open("Scale Right")
        cmds.refresh(suspend=True)
        try:
            cache_original_values("right")
            scale_keys(slider_val)
        finally:
            cmds.refresh(suspend=False)
    else:
        if time_since_last >= update_throttle_ms:
            last_update_time = current_time
            cmds.refresh(suspend=True)
            try:
                scale_keys(slider_val)
            finally:
                cmds.refresh(suspend=False)
    return last_update_time, "Scale Right: {0}".format(value)


def scale_avg_logic(value, last_update_time, update_throttle_ms):
    global _dragging
    slider_val = value / 100.0
    current_time = time.time() * 1000
    time_since_last = current_time - last_update_time
    if not _dragging:
        _dragging = True
        last_update_time = current_time
        slider_utils.safe_undo_chunk_open("Scale Average")
        cmds.refresh(suspend=True)
        try:
            cache_original_values("avg")
            scale_keys(slider_val)
        finally:
            cmds.refresh(suspend=False)
    else:
        if time_since_last >= update_throttle_ms:
            last_update_time = current_time
            cmds.refresh(suspend=True)
            try:
                scale_keys(slider_val)
            finally:
                cmds.refresh(suspend=False)
    return last_update_time, "Scale Average: {0}".format(value)


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms, shift_pressed, ctrl_pressed):
    if not mouse_pressed:
        return last_update_time, "Scale Left: {0}".format(value)
    if ctrl_pressed:
        return scale_avg_logic(value, last_update_time, update_throttle_ms)
    elif shift_pressed:
        return scale_right_logic(value, last_update_time, update_throttle_ms)
    else:
        return scale_left_logic(value, last_update_time, update_throttle_ms)


def reset_slider(slider_widget):
    global _dragging, _original_values, _pivot_values, _stored_keys_sel, _stored_anim_curves
    global _stored_key_indexes, _mfn_curves, _value_setters, _value_readers, _current_mode
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
        slider_utils.safe_undo_chunk_close()
        _dragging = False
    _original_values = {}
    _pivot_values = {}
    _stored_keys_sel = []
    _stored_anim_curves = []
    _stored_key_indexes = {}
    _mfn_curves = {}
    _value_setters = {}
    _value_readers = {}
    _current_mode = None
    _last_scale_value = 1.0
    _stored_key_ranges = {}
    _fast_mode = False