import time
import maya.cmds as cmds

from . import slider_utils
from . import to_slider

STAGGER_MIN_MULTIPLIER = 0.05

tsPushClick = False
tsCurveData = {}
tsActiveKeys = []
tsActiveStepScale = {}
tsActiveKeyCount = {}
tsCurveStagger = {}
tsSplineConverted = set()
tsSteppedKeys = set()
tsBaselineData = {}
tsBaselineSignature = None
tsAccumulatedOffset = {}
tsLastAppliedOffset = {}


def _round_t(t):
    return round(t, 5)


def _get_ordered_selection():
    try:
        if not cmds.selectPref(query=True, trackSelectionOrder=True):
            cmds.selectPref(trackSelectionOrder=True)
    except:
        pass
    return cmds.ls(selection=True, type="transform") or []


def _find_curve_owner(curve, ordered_selection):
    seen = set([curve])
    queue = [curve]
    fallback = None
    while queue:
        next_queue = []
        for node in queue:
            next_nodes = cmds.listConnections(node, source=False, destination=True, plugs=False) or []
            for nxt in next_nodes:
                if nxt in seen:
                    continue
                seen.add(nxt)
                if cmds.nodeType(nxt) == "transform":
                    if fallback is None:
                        fallback = nxt
                    if nxt in ordered_selection:
                        return nxt
                next_queue.append(nxt)
        queue = next_queue
        if len(seen) > 40:
            break
    return fallback


def _stagger_multiplier_for_curve(curve, ordered_selection):
    owner = _find_curve_owner(curve, ordered_selection)
    if owner is None or owner not in ordered_selection:
        return 1.0
    count = len(ordered_selection)
    if count <= 1:
        return 1.0
    forward_rank = ordered_selection.index(owner)
    rank = (count - 1) - forward_rank
    step = (1.0 - STAGGER_MIN_MULTIPLIER) / float(count - 1)
    multiplier = 1.0 - rank * step
    return max(STAGGER_MIN_MULTIPLIER, multiplier)


def _capture_curve(curve):
    times = cmds.keyframe(curve, query=True, timeChange=True) or []
    values = cmds.keyframe(curve, query=True, valueChange=True) or []
    n = len(times)

    in_types = ["auto"] * n
    out_types = ["auto"] * n
    in_angles = [0.0] * n
    out_angles = [0.0] * n

    if n:
        qi = cmds.keyTangent(curve, query=True, index=(0, n - 1), inAngle=True)
        if qi and len(qi) == n:
            in_angles = qi
        qo = cmds.keyTangent(curve, query=True, index=(0, n - 1), outAngle=True)
        if qo and len(qo) == n:
            out_angles = qo
        for i, tt in enumerate(times):
            ti = cmds.keyTangent(curve, query=True, time=(tt, tt), inTangentType=True)
            if ti:
                in_types[i] = ti[0]
            to = cmds.keyTangent(curve, query=True, time=(tt, tt), outTangentType=True)
            if to:
                out_types[i] = to[0]

    weighted = False
    wt = cmds.keyTangent(curve, query=True, weightedTangents=True)
    weighted = bool(wt and wt[0])

    tsCurveData[curve] = {
        "times": times,
        "values": values,
        "in_types": in_types,
        "out_types": out_types,
        "in_angles": in_angles,
        "out_angles": out_angles,
        "weighted": weighted,
    }


def _gather_active_keys():
    global tsActiveKeys, tsActiveStepScale, tsActiveKeyCount, tsCurveStagger, tsBaselineSignature

    selected = to_slider._get_selected_keys()
    ordered_selection = _get_ordered_selection()

    signature = frozenset(
        (curve, _round_t(t))
        for curve, times in selected.items()
        for t in times
    )

    if signature != tsBaselineSignature:
        tsBaselineData.clear()
        tsAccumulatedOffset.clear()
        tsLastAppliedOffset.clear()
        tsBaselineSignature = signature

    tsActiveKeys = []
    tsActiveStepScale = {}
    tsActiveKeyCount = {}
    tsCurveStagger = {}

    for curve, times in selected.items():
        _capture_curve(curve)
        data = tsCurveData[curve]
        orig_times = data["times"]
        active_count = len(times)
        tsActiveStepScale[curve] = max(1.0, float(active_count - 1)) if active_count > 1 else to_slider.STEP_PER_DRAG
        tsActiveKeyCount[curve] = active_count
        tsCurveStagger[curve] = _stagger_multiplier_for_curve(curve, ordered_selection)

        if curve not in tsBaselineData:
            tsBaselineData[curve] = {
                "times": list(data["times"]),
                "values": list(data["values"]),
            }
            tsAccumulatedOffset[curve] = 0.0
        else:
            baseline = tsBaselineData[curve]
            base_times = baseline["times"]
            base_values = baseline["values"]
            committed = tsAccumulatedOffset.get(curve, 0.0)
            live_values = data["values"]
            live_times = data["times"]
            stale = len(live_values) != len(base_values)
            if not stale:
                for i, live_v in enumerate(live_values):
                    if to_slider.OFFSET_MODE == "time":
                        expected = to_slider._value_at_time_looped(base_times, base_values, live_times[i] - committed)
                    else:
                        expected = to_slider._value_at_fractional_index_looped(base_values, i - committed)
                    if abs(expected - live_v) > 0.001:
                        stale = True
                        break
            if stale:
                tsBaselineData[curve] = {
                    "times": list(live_times),
                    "values": list(live_values),
                }
                tsAccumulatedOffset[curve] = 0.0
                tsLastAppliedOffset.pop(curve, None)

        if curve not in tsAccumulatedOffset:
            tsAccumulatedOffset[curve] = 0.0

        for t in times:
            rt = _round_t(t)
            idx = None
            for i, ot in enumerate(orig_times):
                if _round_t(ot) == rt:
                    idx = i
                    break
            if idx is None:
                continue

            out_type = data["out_types"][idx]
            live_out = cmds.keyTangent(curve, query=True, time=(t, t), outTangentType=True)
            if live_out:
                out_type = live_out[0]

            key = (curve, rt)
            if out_type == "step":
                tsSteppedKeys.add(key)
            elif key not in tsSplineConverted:
                try:
                    cmds.keyTangent(curve, edit=True, time=(t, t), itt="spline", ott="spline")
                except:
                    pass
                tsSplineConverted.add(key)

            tsActiveKeys.append((curve, t, idx))

    return bool(tsActiveKeys)


def _apply(position):
    raw_position = position
    eased_position = slider_utils.ease_value(raw_position, exponent=to_slider.POSITION_EASE_EXPONENT)

    new_values = {}

    for curve, t, idx in tsActiveKeys:
        stagger = tsCurveStagger.get(curve, 1.0)
        curve_position = eased_position * stagger

        baseline = tsBaselineData[curve]
        base_times = baseline["times"]
        base_values = baseline["values"]
        committed = tsAccumulatedOffset.get(curve, 0.0)

        if to_slider.OFFSET_MODE == "time":
            drag_offset = curve_position * to_slider.TIME_STEP_FRAMES
            total_offset = committed + drag_offset
            new_v = to_slider._value_at_time_looped(base_times, base_values, t - total_offset)
        else:
            effective_step = tsActiveStepScale.get(curve, to_slider.STEP_PER_DRAG)
            drag_offset = curve_position * effective_step
            total_offset = committed + drag_offset
            new_v = to_slider._value_at_fractional_index_looped(base_values, idx - total_offset)

        try:
            cmds.keyframe(curve, edit=True, time=(t, t), valueChange=new_v, absolute=True)
        except:
            continue
        new_values[(curve, _round_t(t))] = new_v
        tsLastAppliedOffset[curve] = drag_offset

    for curve, t, idx in tsActiveKeys:
        data = tsCurveData[curve]
        key = (curve, _round_t(t))
        if key not in new_values or key in tsSteppedKeys:
            continue

        stagger = tsCurveStagger.get(curve, 1.0)
        curve_position = eased_position * stagger
        blend = min(1.0, abs(curve_position) * to_slider.TANGENT_BLEND_SPEED)

        result = to_slider._tangent_angle_for_key(curve, data, idx, new_values, to_slider.HANDLE_SMOOTHNESS, to_slider.HANDLE_FLATTEN_ENDS)
        if result is None:
            continue
        target_angle, time_in, time_out = result

        curve_n = len(data["times"])
        if curve_n >= 2 and (idx == 0 or idx == curve_n - 1):
            other_idx = curve_n - 1 if idx == 0 else 0
            other_result = to_slider._tangent_angle_for_key(curve, data, other_idx, new_values, to_slider.HANDLE_SMOOTHNESS, to_slider.HANDLE_FLATTEN_ENDS)
            if other_result is not None:
                other_angle = other_result[0]
                closeness = to_slider._edge_value_closeness(data, new_values, curve)
                average_angle = (target_angle + other_angle) * 0.5
                target_angle = target_angle + (average_angle - target_angle) * closeness

        orig_in_list = data["in_angles"]
        orig_out_list = data["out_angles"]
        orig_in = orig_in_list[idx] if idx < len(orig_in_list) else 0.0
        orig_out = orig_out_list[idx] if idx < len(orig_out_list) else 0.0
        orig_avg = (orig_in + orig_out) * 0.5

        angle = orig_avg + (target_angle - orig_avg) * blend

        try:
            cmds.keyTangent(curve, edit=True, absolute=True, time=(t, t), inAngle=angle, outAngle=angle)
            if data.get("weighted"):
                in_weight = max(0.05, abs(time_in) / 3.0)
                out_weight = max(0.05, abs(time_out) / 3.0)
                cmds.keyTangent(curve, edit=True, time=(t, t), inWeight=in_weight, outWeight=out_weight)
        except:
            pass


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global tsPushClick

    status = "Time Offset Stagger: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and tsPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not tsPushClick:
        slider_utils.safe_undo_chunk_open("Time Offset Stagger")
        if not _gather_active_keys():
            slider_utils.safe_undo_chunk_close()
            return last_update_time, status
        tsPushClick = True

    cmds.refresh(suspend=True)
    try:
        _apply(value / 100.0)
    finally:
        cmds.refresh(suspend=False)

    return last_update_time, status


def reset_slider(slider_widget):
    global tsPushClick, tsCurveData, tsActiveKeys, tsActiveStepScale, tsActiveKeyCount, tsCurveStagger, tsSplineConverted, tsSteppedKeys

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    for curve, drag_offset in tsLastAppliedOffset.items():
        tsAccumulatedOffset[curve] = tsAccumulatedOffset.get(curve, 0.0) + drag_offset
    tsLastAppliedOffset.clear()

    if tsPushClick:
        slider_utils.safe_undo_chunk_close()

    tsPushClick = False
    tsCurveData = {}
    tsActiveKeys = []
    tsActiveStepScale = {}
    tsActiveKeyCount = {}
    tsCurveStagger = {}
    tsSplineConverted = set()
    tsSteppedKeys = set()