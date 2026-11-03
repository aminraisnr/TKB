import bisect
import math
import time
import maya.cmds as cmds

from . import slider_utils

OFFSET_MODE = "time"

HANDLE_SMOOTHNESS = 1.5
HANDLE_FLATTEN_ENDS = False

STEP_PER_DRAG = 5.0
TIME_STEP_FRAMES = 20.0
POSITION_EASE_EXPONENT = 1
TANGENT_BLEND_SPEED = 50.0

toPushClick = False
toCurveData = {}
toActiveKeys = []
toActiveStepScale = {}
toActiveKeyCount = {}
toSplineConverted = set()
toSteppedKeys = set()
toBaselineData = {}
toBaselineSignature = None
toAccumulatedOffset = {}
toLastAppliedOffset = {}


def _round_t(t):
    return round(t, 5)


def _get_selected_keys():
    curves = cmds.keyframe(query=True, selected=True, name=True) or []
    result = {}
    for curve in curves:
        times = cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
        if times:
            result[curve] = sorted(times)
    return result


def _value_at_fractional_index_clamped(values, findex):
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return values[0]
    if findex <= 0:
        return values[0]
    if findex >= n - 1:
        return values[n - 1]
    lo = int(math.floor(findex))
    hi = lo + 1
    frac = findex - lo
    return values[lo] + (values[hi] - values[lo]) * frac


def _value_at_fractional_index_looped(values, findex):
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return values[0]
    period = n - 1
    span = values[-1] - values[0]
    cycle = math.floor(findex / period)
    local = findex - cycle * period
    lo = int(math.floor(local))
    if lo >= period:
        lo = period - 1
    if lo < 0:
        lo = 0
    hi = lo + 1
    frac = local - lo
    base = values[lo] + (values[hi] - values[lo]) * frac
    return base + cycle * span


def _segment_bounds(times, local_time, t_start, t_end):
    n = len(times)
    if local_time <= t_start:
        return 0, min(1, n - 1)
    if local_time >= t_end:
        return max(0, n - 2), n - 1
    hi = bisect.bisect_right(times, local_time)
    if hi <= 0:
        return 0, min(1, n - 1)
    if hi >= n:
        return n - 2, n - 1
    return hi - 1, hi


def _value_at_time_looped(times, values, sample_time):
    n = len(times)
    if n == 0:
        return 0.0
    if n == 1:
        return values[0]
    t_start = times[0]
    t_end = times[-1]
    period = t_end - t_start
    if period <= 0:
        return values[0]
    span = values[-1] - values[0]
    cycle = math.floor((sample_time - t_start) / period)
    local_time = sample_time - cycle * period
    local_time = max(t_start, min(t_end, local_time))
    lo, hi = _segment_bounds(times, local_time, t_start, t_end)
    seg_span = times[hi] - times[lo]
    frac = 0.0 if seg_span == 0 else (local_time - times[lo]) / seg_span
    base = values[lo] + (values[hi] - values[lo]) * frac
    return base + cycle * span


def _tangent_angle(val_p, val_c, val_n, time_p, time_c, time_n, softness):
    softness = max(0.0, min(1.0, softness))
    val_in = val_c - val_p
    val_out = val_n - val_c
    time_in = time_c - time_p
    time_out = time_n - time_c

    slope_in = (val_in / time_in) if time_in != 0 else 0.0
    slope_out = (val_out / time_out) if time_out != 0 else 0.0

    pow_in = 0.5
    pow_out = 0.5
    if (slope_in + slope_out) != 0:
        pow_in = 1.0 - (abs(slope_in) / (abs(slope_in) + abs(slope_out)))
        pow_out = 1.0 - pow_in

    pow_in = ((1.0 - softness) * pow_in) + (softness * 0.5)
    pow_out = ((1.0 - softness) * pow_out) + (softness * 0.5)

    new_slope = (pow_in * slope_in) + (pow_out * slope_out)
    angle = math.degrees(math.atan(new_slope))
    return angle, time_in, time_out


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

    toCurveData[curve] = {
        "times": times,
        "values": values,
        "in_types": in_types,
        "out_types": out_types,
        "in_angles": in_angles,
        "out_angles": out_angles,
        "weighted": weighted,
    }


def _gather_active_keys():
    global toActiveKeys, toActiveStepScale, toActiveKeyCount, toBaselineSignature

    selected = _get_selected_keys()

    signature = frozenset(
        (curve, _round_t(t))
        for curve, times in selected.items()
        for t in times
    )

    if signature != toBaselineSignature:
        toBaselineData.clear()
        toAccumulatedOffset.clear()
        toLastAppliedOffset.clear()
        toBaselineSignature = signature

    toActiveKeys = []
    toActiveStepScale = {}
    toActiveKeyCount = {}

    for curve, times in selected.items():
        _capture_curve(curve)
        data = toCurveData[curve]
        orig_times = data["times"]
        active_count = len(times)
        toActiveStepScale[curve] = max(1.0, float(active_count - 1)) if active_count > 1 else STEP_PER_DRAG
        toActiveKeyCount[curve] = active_count

        if curve not in toBaselineData:
            toBaselineData[curve] = {
                "times": list(data["times"]),
                "values": list(data["values"]),
            }
            toAccumulatedOffset[curve] = 0.0
        else:
            baseline = toBaselineData[curve]
            base_times = baseline["times"]
            base_values = baseline["values"]
            committed = toAccumulatedOffset.get(curve, 0.0)
            live_values = data["values"]
            live_times = data["times"]
            stale = len(live_values) != len(base_values)
            if not stale:
                for i, live_v in enumerate(live_values):
                    if OFFSET_MODE == "time":
                        expected = _value_at_time_looped(base_times, base_values, live_times[i] - committed)
                    else:
                        expected = _value_at_fractional_index_looped(base_values, i - committed)
                    if abs(expected - live_v) > 0.001:
                        stale = True
                        break
            if stale:
                toBaselineData[curve] = {
                    "times": list(live_times),
                    "values": list(live_values),
                }
                toAccumulatedOffset[curve] = 0.0
                toLastAppliedOffset.pop(curve, None)

        if curve not in toAccumulatedOffset:
            toAccumulatedOffset[curve] = 0.0

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
                toSteppedKeys.add(key)
            elif key not in toSplineConverted:
                try:
                    cmds.keyTangent(curve, edit=True, time=(t, t), itt="spline", ott="spline")
                except:
                    pass
                toSplineConverted.add(key)

            toActiveKeys.append((curve, t, idx))

    return bool(toActiveKeys)


def _live_value(curve, t):
    v = cmds.keyframe(curve, time=(t, t), query=True, valueChange=True)
    return v[0] if v else 0.0


def _neighbor_time_value(data, new_values, curve, idx, direction):
    times = data["times"]
    values = data["values"]
    n = len(times)
    j = idx + direction
    if j < 0 or j >= n:
        return None
    key = (curve, _round_t(times[j]))
    return times[j], new_values.get(key, values[j])


def _tangent_angle_for_key(curve, data, idx, new_values, softness, flatten_ends):
    times = data["times"]
    n = len(times)
    t_c = times[idx]
    key_c = (curve, _round_t(t_c))
    val_c = new_values.get(key_c, data["values"][idx])

    prev = _neighbor_time_value(data, new_values, curve, idx, -1)
    nxt = _neighbor_time_value(data, new_values, curve, idx, 1)

    if prev is None and nxt is None:
        return None

    if nxt is None:
        time_p, val_p = prev
        if flatten_ends:
            time_n, val_n = t_c, val_c
        else:
            time_n = t_c + (t_c - time_p)
            val_n = val_c + (val_c - val_p)
    elif prev is None:
        time_n, val_n = nxt
        if flatten_ends:
            time_p, val_p = t_c, val_c
        else:
            time_p = t_c - (time_n - t_c)
            val_p = val_c - (val_n - val_c)
    else:
        time_p, val_p = prev
        time_n, val_n = nxt

    return _tangent_angle(val_p, val_c, val_n, time_p, t_c, time_n, softness)


def _edge_value_closeness(data, new_values, curve):
    times = data["times"]
    values = data["values"]
    n = len(times)
    if n < 2:
        return 0.0
    key_first = (curve, _round_t(times[0]))
    key_last = (curve, _round_t(times[-1]))
    val_first = new_values.get(key_first, values[0])
    val_last = new_values.get(key_last, values[-1])
    value_range = max(values) - min(values) if values else 0.0
    if value_range <= 0.0:
        return 1.0
    diff = abs(val_first - val_last)
    return max(0.0, 1.0 - min(1.0, diff / value_range))


def _apply(position):
    eased_position = slider_utils.ease_value(position, exponent=POSITION_EASE_EXPONENT)

    new_values = {}

    for curve, t, idx in toActiveKeys:
        baseline = toBaselineData[curve]
        base_times = baseline["times"]
        base_values = baseline["values"]
        committed = toAccumulatedOffset.get(curve, 0.0)

        if OFFSET_MODE == "time":
            drag_offset = eased_position * TIME_STEP_FRAMES
            total_offset = committed + drag_offset
            new_v = _value_at_time_looped(base_times, base_values, t - total_offset)
        else:
            effective_step = toActiveStepScale.get(curve, STEP_PER_DRAG)
            drag_offset = eased_position * effective_step
            total_offset = committed + drag_offset
            new_v = _value_at_fractional_index_looped(base_values, idx - total_offset)

        try:
            cmds.keyframe(curve, edit=True, time=(t, t), valueChange=new_v, absolute=True)
        except:
            continue
        new_values[(curve, _round_t(t))] = new_v
        toLastAppliedOffset[curve] = drag_offset

    blend = min(1.0, abs(eased_position) * TANGENT_BLEND_SPEED)

    for curve, t, idx in toActiveKeys:
        data = toCurveData[curve]
        key = (curve, _round_t(t))
        if key not in new_values or key in toSteppedKeys:
            continue

        result = _tangent_angle_for_key(curve, data, idx, new_values, HANDLE_SMOOTHNESS, HANDLE_FLATTEN_ENDS)
        if result is None:
            continue
        target_angle, time_in, time_out = result

        curve_n = len(data["times"])
        if curve_n >= 2 and (idx == 0 or idx == curve_n - 1):
            other_idx = curve_n - 1 if idx == 0 else 0
            other_result = _tangent_angle_for_key(curve, data, other_idx, new_values, HANDLE_SMOOTHNESS, HANDLE_FLATTEN_ENDS)
            if other_result is not None:
                other_angle = other_result[0]
                closeness = _edge_value_closeness(data, new_values, curve)
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
    global toPushClick

    status = "Time Offset: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and toPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not toPushClick:
        slider_utils.safe_undo_chunk_open("Time Offset")
        if not _gather_active_keys():
            slider_utils.safe_undo_chunk_close()
            return last_update_time, status
        toPushClick = True

    cmds.refresh(suspend=True)
    try:
        _apply(value / 100.0)
    finally:
        cmds.refresh(suspend=False)

    return last_update_time, status


def reset_slider(slider_widget):
    global toPushClick, toCurveData, toActiveKeys, toActiveStepScale, toActiveKeyCount, toSplineConverted, toSteppedKeys

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    for curve, drag_offset in toLastAppliedOffset.items():
        toAccumulatedOffset[curve] = toAccumulatedOffset.get(curve, 0.0) + drag_offset
    toLastAppliedOffset.clear()

    if toPushClick:
        slider_utils.safe_undo_chunk_close()

    toPushClick = False
    toCurveData = {}
    toActiveKeys = []
    toActiveStepScale = {}
    toActiveKeyCount = {}
    toSplineConverted = set()
    toSteppedKeys = set()