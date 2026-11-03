import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import time

try:
    from . import slider_utils
except ImportError:
    import slider_utils

cascadePushClick = False
cascadeStoredKeyValues = {}
cascadeStoredAnimCurves = []
cascadeStoredKeysSel = []
cascadeMfnCurves = {}
cascadeLastAffectedKeys = {}


def _find_key_index(all_key_times, target_time):
    if target_time is None:
        return None
    for i, key_time in enumerate(all_key_times):
        if abs(key_time - target_time) < 0.001:
            return i
    return None


def _compute_cascade_move(selected_entry, all_key_times, original_values, t_value):
    if isinstance(selected_entry, tuple):
        left_time, right_time = selected_entry
        left_idx = _find_key_index(all_key_times, left_time)
        right_idx = _find_key_index(all_key_times, right_time)
        if left_idx is None and right_idx is None:
            return None
        if t_value < 1.0:
            pivot_idx = right_idx if right_idx is not None else left_idx
            if pivot_idx is None or pivot_idx >= len(original_values):
                return None
            pivot_value = original_values[pivot_idx]
            if left_idx is not None:
                neighbor_value = original_values[left_idx]
            elif pivot_idx < len(original_values) - 1:
                neighbor_value = pivot_value - (original_values[pivot_idx + 1] - pivot_value)
            else:
                neighbor_value = pivot_value
            blend_factor = 1.0 - t_value
            target_value = pivot_value + (neighbor_value - pivot_value) * blend_factor
            keys_to_move = list(range(pivot_idx, len(original_values)))
        else:
            pivot_idx = left_idx if left_idx is not None else right_idx
            if pivot_idx is None or pivot_idx >= len(original_values):
                return None
            pivot_value = original_values[pivot_idx]
            if right_idx is not None:
                neighbor_value = original_values[right_idx]
            elif pivot_idx > 0:
                neighbor_value = pivot_value - (original_values[pivot_idx - 1] - pivot_value)
            else:
                neighbor_value = pivot_value
            blend_factor = t_value - 1.0
            target_value = pivot_value + (neighbor_value - pivot_value) * blend_factor
            keys_to_move = list(range(0, pivot_idx + 1))
        movement_offset = target_value - pivot_value
        return pivot_idx, keys_to_move, movement_offset

    selected_idx = _find_key_index(all_key_times, selected_entry)
    if selected_idx is None or selected_idx >= len(original_values):
        return None
    selected_original_value = original_values[selected_idx]
    left_neighbor_value = None
    right_neighbor_value = None
    if selected_idx > 0:
        left_neighbor_value = original_values[selected_idx - 1]
    if selected_idx < len(original_values) - 1:
        right_neighbor_value = original_values[selected_idx + 1]
    if left_neighbor_value is None and right_neighbor_value is None:
        return None
    if left_neighbor_value is None:
        left_neighbor_value = selected_original_value - (right_neighbor_value - selected_original_value)
    if right_neighbor_value is None:
        right_neighbor_value = selected_original_value - (left_neighbor_value - selected_original_value)
    if t_value < 1.0:
        blend_factor = 1.0 - t_value
        target_value = selected_original_value + (left_neighbor_value - selected_original_value) * blend_factor
        keys_to_move = list(range(selected_idx, len(original_values)))
    else:
        blend_factor = t_value - 1.0
        target_value = selected_original_value + (right_neighbor_value - selected_original_value) * blend_factor
        keys_to_move = list(range(0, selected_idx + 1))
    movement_offset = target_value - selected_original_value
    return selected_idx, keys_to_move, movement_offset


def apply_cascade_keys(t_value):
    global cascadeStoredAnimCurves, cascadeStoredKeysSel, cascadeStoredKeyValues, cascadeMfnCurves, cascadeLastAffectedKeys
    if not cascadeStoredAnimCurves:
        return
    for n, curve in enumerate(cascadeStoredAnimCurves):
        if not cascadeStoredKeysSel[n] or curve not in cascadeMfnCurves:
            continue
        mfn = cascadeMfnCurves[curve]
        try:
            num_keys = mfn.numKeys
        except:
            continue
        if num_keys == 0:
            continue
        original_values = cascadeStoredKeyValues.get(curve, [])
        if not original_values:
            continue
        all_key_times = slider_utils.get_all_key_times(mfn)
        pending_values = {}
        affected_indices = set()
        for selected_entry in cascadeStoredKeysSel[n]:
            result = _compute_cascade_move(selected_entry, all_key_times, original_values, t_value)
            if result is None:
                continue
            pivot_idx, keys_to_move, movement_offset = result
            for key_idx in keys_to_move:
                if key_idx >= len(original_values) or key_idx >= num_keys:
                    continue
                pending_values[key_idx] = original_values[key_idx] + movement_offset
                affected_indices.add(key_idx)
        previously_affected = cascadeLastAffectedKeys.get(curve, set())
        stale_indices = previously_affected - affected_indices
        for key_idx in stale_indices:
            if key_idx >= len(original_values) or key_idx >= num_keys:
                continue
            slider_utils.set_key_value(curve, key_idx, original_values[key_idx])
        for key_idx, new_value in pending_values.items():
            slider_utils.set_key_value(curve, key_idx, new_value)
        cascadeLastAffectedKeys[curve] = affected_indices


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global cascadePushClick, cascadeStoredAnimCurves, cascadeStoredKeysSel, cascadeStoredKeyValues, cascadeMfnCurves, cascadeLastAffectedKeys
    t_value = value / 100.0
    show_value = abs(round((t_value - 1.0) * 100.0, 2))
    if show_value >= 1 or show_value == 0:
        show_value = int(round(show_value))
    status = "Cascade: {0}%".format(show_value)
    if not mouse_pressed:
        return last_update_time, status
    current_time = time.time() * 1000
    time_since_last = current_time - last_update_time
    if time_since_last < update_throttle_ms and cascadePushClick:
        return last_update_time, status
    last_update_time = current_time
    if not cascadePushClick:
        cascadePushClick = True
        slider_utils.safe_undo_chunk_open("Cascade Keys")
        getCurves = slider_utils.get_anim_curves()
        cascadeStoredAnimCurves = getCurves[0]
        getFrom = getCurves[1]
        if not cascadeStoredAnimCurves:
            return last_update_time, status
        if getFrom == "graphEditor":
            cascadeStoredKeysSel = slider_utils.get_keys_sel(cascadeStoredAnimCurves, getFrom)
        else:
            current_frame = cmds.currentTime(query=True)
            cascadeStoredKeysSel = []
            for curve in cascadeStoredAnimCurves:
                mfn = slider_utils.get_mfn_anim_curve(curve)
                if mfn is None:
                    cascadeStoredKeysSel.append([])
                    continue
                num_keys = mfn.numKeys
                if num_keys == 0:
                    cascadeStoredKeysSel.append([])
                    continue
                key_times = slider_utils.get_all_key_times(mfn)
                exact_time = None
                for key_time in key_times:
                    if abs(key_time - current_frame) < 0.001:
                        exact_time = key_time
                        break
                if exact_time is not None:
                    cascadeStoredKeysSel.append([exact_time])
                else:
                    left_time = None
                    right_time = None
                    for key_time in key_times:
                        if key_time < current_frame:
                            if left_time is None or key_time > left_time:
                                left_time = key_time
                        elif key_time > current_frame:
                            if right_time is None or key_time < right_time:
                                right_time = key_time
                    if left_time is None and right_time is None:
                        cascadeStoredKeysSel.append([])
                    else:
                        cascadeStoredKeysSel.append([(left_time, right_time)])
        cascadeStoredKeyValues = {}
        cascadeMfnCurves = {}
        cascadeLastAffectedKeys = {}
        for n, curve in enumerate(cascadeStoredAnimCurves):
            if not cascadeStoredKeysSel[n]:
                continue
            mfn = slider_utils.get_mfn_anim_curve(curve)
            if mfn is None:
                continue
            cascadeMfnCurves[curve] = mfn
            all_key_values = slider_utils.get_all_key_values(mfn)
            if all_key_values:
                cascadeStoredKeyValues[curve] = list(all_key_values)
    apply_cascade_keys(t_value)
    return last_update_time, status


def reset_slider(slider_widget):
    global cascadePushClick, cascadeStoredKeyValues, cascadeStoredAnimCurves, cascadeStoredKeysSel, cascadeMfnCurves, cascadeLastAffectedKeys
    final_value = slider_widget.value()
    if final_value != 100 and cascadePushClick:
        t_value = final_value / 100.0
        apply_cascade_keys(t_value)
    slider_widget.blockSignals(True)
    slider_widget.setValue(100)
    slider_widget.blockSignals(False)
    if cascadePushClick:
        slider_utils.safe_undo_chunk_close()
        cascadePushClick = False
        cascadeStoredKeyValues = {}
        cascadeStoredAnimCurves = []
        cascadeStoredKeysSel = []
        cascadeMfnCurves = {}
        cascadeLastAffectedKeys = {}