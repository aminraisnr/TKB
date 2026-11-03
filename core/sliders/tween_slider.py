import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import time

try:
    from PySide2 import QtCore
except ImportError:
    from PySide6 import QtCore

try:
    from . import slider_utils
except ImportError:
    import slider_utils

IS_MACOS = slider_utils.IS_MACOS

TWEEN_OVERSHOOT_AMPLIFY = 2.5


def _amplify_overshoot_bias(bias):
    if bias > 1.0:
        return 1.0 + (bias - 1.0) * TWEEN_OVERSHOOT_AMPLIFY
    if bias < 0.0:
        return bias * TWEEN_OVERSHOOT_AMPLIFY
    return bias

pushClick = False
originalValues = {}
storedAnimCurves = []
storedKeysSel = []
storedMfnCurves = {}
storedKeyIndexes = {}
storedBoundaryValues = {}
storedGetFrom = "graphEditor"
storedSetters = {}
storedReaders = {}
storedUnitAngle = None
storedUnitLinear = None

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


def _make_value_setter(mfn, angle_unit_name, linear_unit_name):
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


def _make_value_reader(mfn, angle_unit_name, linear_unit_name):
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


def initialize_tween_undo():
    global originalValues, storedAnimCurves, storedKeysSel, storedMfnCurves, storedKeyIndexes, storedBoundaryValues, storedGetFrom
    global storedSetters, storedReaders, storedUnitAngle, storedUnitLinear
    slider_utils.safe_undo_chunk_open("Tween")
    originalValues = {}
    storedMfnCurves = {}
    storedKeyIndexes = {}
    storedBoundaryValues = {}
    storedSetters = {}
    storedReaders = {}
    storedUnitAngle = cmds.currentUnit(query=True, angle=True)
    storedUnitLinear = cmds.currentUnit(query=True, linear=True)
    getCurves = slider_utils.get_anim_curves()
    storedAnimCurves = getCurves[0]
    storedGetFrom = getCurves[1]
    if not storedAnimCurves:
        return
    storedKeysSel = slider_utils.get_keys_sel(storedAnimCurves, storedGetFrom)
    hasSelectedKeys = any(keyList for keyList in storedKeysSel if keyList)
    if not hasSelectedKeys:
        current_time = cmds.currentTime(query=True)
        for curve in storedAnimCurves:
            if cmds.objExists(curve):
                existingKeys = cmds.keyframe(curve, query=True, timeChange=True)
                keyExists = existingKeys and current_time in existingKeys
                cmds.setKeyframe(curve, time=current_time, insert=True)
                if not keyExists:
                    prev_key = cmds.findKeyframe(curve, time=(current_time,current_time), which="previous")
                    next_key = cmds.findKeyframe(curve, time=(current_time,current_time), which="next")
                    out_tangent_type = "auto"
                    if prev_key is not None:
                        try:
                            prev_out_tangent = cmds.keyTangent(curve, time=(prev_key,prev_key), query=True, outTangentType=True)[0]
                            if prev_out_tangent == "step":
                                out_tangent_type = "step"
                        except:
                            pass
                    if out_tangent_type != "step" and next_key is not None:
                        try:
                            next_out_tangent = cmds.keyTangent(curve, time=(next_key,next_key), query=True, outTangentType=True)[0]
                            if next_out_tangent == "step":
                                out_tangent_type = "step"
                        except:
                            pass
                    cmds.keyTangent(curve, time=(current_time, current_time), inTangentType="auto", outTangentType=out_tangent_type)
        storedKeysSel = []
        for curve in storedAnimCurves:
            if cmds.objExists(curve):
                storedKeysSel.append([current_time])
            else:
                storedKeysSel.append([])
    
    for n, curve in enumerate(storedAnimCurves):
        if not storedKeysSel[n]:
            continue
        mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        storedMfnCurves[curve] = mfn
        setter = _make_value_setter(mfn, storedUnitAngle, storedUnitLinear)
        reader = _make_value_reader(mfn, storedUnitAngle, storedUnitLinear)
        storedSetters[curve] = setter
        storedReaders[curve] = reader
        originalValues[curve] = {}
        storedKeyIndexes[curve] = {}

        num_keys = mfn.numKeys

        selected_indexes = []
        for key_time in storedKeysSel[n]:
            idx = slider_utils.get_key_index_at_time(mfn, key_time)
            if idx >= 0:
                originalValues[curve][key_time] = reader(idx)
                storedKeyIndexes[curve][key_time] = idx
                selected_indexes.append(idx)

        if not selected_indexes:
            continue

        first_selected_idx = min(selected_indexes)
        last_selected_idx = max(selected_indexes)

        if first_selected_idx > 0:
            left_value = reader(first_selected_idx - 1)
        else:
            left_value = reader(first_selected_idx)

        if last_selected_idx < num_keys - 1:
            right_value = reader(last_selected_idx + 1)
        else:
            right_value = reader(last_selected_idx)

        storedBoundaryValues[curve] = (left_value, right_value)


def execute_tween_on_curves(bias):
    global originalValues, storedAnimCurves, storedKeysSel, storedMfnCurves, storedKeyIndexes, storedBoundaryValues
    if not storedAnimCurves:
        return
    for n, curve in enumerate(storedAnimCurves):
        if not storedKeysSel[n] or curve not in storedMfnCurves:
            continue
        if curve not in storedBoundaryValues:
            continue
        
        left_value, right_value = storedBoundaryValues[curve]
        setter = storedSetters.get(curve)
        if setter is None:
            continue

        for key_time in storedKeysSel[n]:
            if curve not in originalValues or key_time not in originalValues[curve]:
                continue
            original_val = originalValues[curve][key_time]
            key_idx = storedKeyIndexes[curve].get(key_time, -1)
            if key_idx < 0:
                continue

            tweened_value = original_val
            if left_value is not None and right_value is not None:
                tweened_value = left_value + (right_value - left_value) * bias
            elif left_value is not None:
                if bias < 0.5:
                    blend_factor = (0.5 - bias) * 2
                    tweened_value = original_val + (left_value - original_val) * blend_factor
            elif right_value is not None:
                if bias > 0.5:
                    blend_factor = (bias - 0.5) * 2
                    tweened_value = original_val + (right_value - original_val) * blend_factor
            try:
                setter(key_idx, tweened_value)
            except:
                continue


def commit_tween_on_curves():
    global originalValues, storedAnimCurves, storedKeysSel, storedMfnCurves, storedKeyIndexes, storedSetters, storedReaders
    if not storedAnimCurves:
        return
    for n, curve in enumerate(storedAnimCurves):
        if not storedKeysSel[n] or curve not in storedMfnCurves:
            continue
        if curve not in storedSetters or curve not in storedReaders:
            continue
        setter = storedSetters[curve]
        reader = storedReaders[curve]
        for key_time in storedKeysSel[n]:
            if curve not in originalValues or key_time not in originalValues[curve]:
                continue
            key_idx = storedKeyIndexes[curve].get(key_time, -1)
            if key_idx < 0:
                continue
            try:
                finalValue = reader(key_idx)
                originalValue = originalValues[curve][key_time]
                setter(key_idx, originalValue)
                cmds.keyframe(curve, index=(key_idx, key_idx), valueChange=finalValue, absolute=True)
            except:
                continue


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global pushClick
    status = "Tween: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status
    current_time = time.time() * 1000
    time_since_last = current_time - last_update_time
    if time_since_last < update_throttle_ms and pushClick:
        return last_update_time, status
    last_update_time = current_time
    if not pushClick:
        selected = cmds.ls(selection=True)
        if not selected:
            return last_update_time, status
        pushClick = True
        if IS_MACOS:
            QtCore.QTimer.singleShot(20, initialize_tween_undo)
        else:
            initialize_tween_undo()
    bias = (value + 100) / 200.0
    bias = _amplify_overshoot_bias(bias)
    cmds.refresh(suspend=True)
    try:
        execute_tween_on_curves(bias)
    finally:
        cmds.refresh(suspend=False)
    return last_update_time, status


def reset_slider(slider_widget):
    global pushClick, originalValues, storedAnimCurves, storedKeysSel, storedMfnCurves, storedKeyIndexes, storedBoundaryValues
    global storedSetters, storedReaders
    final_value = slider_widget.value()
    if pushClick:
        bias = (final_value + 100) / 200.0
        bias = _amplify_overshoot_bias(bias)
        cmds.refresh(suspend=True)
        try:
            execute_tween_on_curves(bias)
            commit_tween_on_curves()
        finally:
            cmds.refresh(suspend=False)
    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)
    if pushClick:
        slider_utils.safe_undo_chunk_close()
    pushClick = False
    originalValues = {}
    storedAnimCurves = []
    storedKeysSel = []
    storedMfnCurves = {}
    storedKeyIndexes = {}
    storedBoundaryValues = {}
    storedSetters = {}
    storedReaders = {}