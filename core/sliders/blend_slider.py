import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import time

try:
    from . import slider_utils
except ImportError:
    import slider_utils

IS_MACOS = slider_utils.IS_MACOS

blendPushClick = False
blendStoredKeyValues = {}
blendStoredKeyTimes = {}
blendStoredIndexes = {}
blendStoredAnimCurves = []
blendStoredKeysSel = []
blendStoredMfnCurves = {}
blendStoredSetters = {}
blendStoredReaders = {}
blendMfnCache = {}
blendKeyTimesCache = {}
blendGetFrom = "graphEditor"
blendUnitAngle = None
blendUnitLinear = None

blendGraphEditorScaleMode = False
blendLastValue = 0
blendScaleValue = 1
blendPadKeyValues = {}
blendPadKeyTimes = {}
blendPadIndexes = {}

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


def _channelbox_attrs():
    try:
        channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        return cmds.channelBox(channel_box, query=True, selectedMainAttributes=True) or []
    except:
        return []


def _keyable_attrs(node):
    return cmds.listAttr(node, keyable=True, unlocked=True) or []


def _resolve_curve(plug):
    conns = cmds.listConnections(plug, source=True, destination=False) or []
    for c in conns:
        if cmds.nodeType(c).startswith("animCurve"):
            return c
    return None


def _auto_curves_for_selection(selection):
    channel_attrs = _channelbox_attrs()
    all_curves = []
    for obj in selection:
        attrs = channel_attrs if channel_attrs else _keyable_attrs(obj)
        for attr in attrs:
            plug = obj + "." + attr
            if not cmds.objExists(plug):
                continue
            curve = _resolve_curve(plug)
            if curve and curve not in all_curves:
                all_curves.append(curve)
    return all_curves


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


def setup_blend_key_transform_data():
    global blendStoredKeyValues, blendStoredKeyTimes, blendStoredIndexes, blendStoredMfnCurves, blendStoredSetters, blendStoredReaders, blendGetFrom
    global blendUnitAngle, blendUnitLinear
    blendStoredKeyValues = {}
    blendStoredKeyTimes = {}
    blendStoredIndexes = {}
    blendStoredMfnCurves = {}
    blendStoredSetters = {}
    blendStoredReaders = {}
    blendUnitAngle = cmds.currentUnit(query=True, angle=True)
    blendUnitLinear = cmds.currentUnit(query=True, linear=True)
    for n, curve in enumerate(blendStoredAnimCurves):
        if not blendStoredKeysSel[n]:
            continue
        mfn = blendMfnCache.get(curve)
        if mfn is None:
            mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        blendStoredMfnCurves[curve] = mfn
        reader = _make_value_reader(mfn, blendUnitAngle, blendUnitLinear)
        blendStoredSetters[curve] = _make_value_setter(mfn, blendUnitAngle, blendUnitLinear)
        blendStoredReaders[curve] = reader
        numKeys = mfn.numKeys
        if not numKeys:
            continue
        keyTimes = blendKeyTimesCache.get(curve)
        if keyTimes is None:
            keyTimes = slider_utils.get_all_key_times(mfn)
        if not keyTimes:
            continue
        if numKeys == 1:
            inOffsetTime = 1
            inOffsetVal = 0
            outOffsetTime = 1
            outOffsetVal = 0
        else:
            inOffsetTime = keyTimes[1] - keyTimes[0]
            inOffsetVal = reader(1) - reader(0)
            outOffsetTime = keyTimes[-1] - keyTimes[-2]
            outOffsetVal = reader(numKeys - 1) - reader(numKeys - 2)
        paddedTimes = [keyTimes[0] - 2 * inOffsetTime, keyTimes[0] - inOffsetTime]
        paddedTimes.extend(keyTimes)
        paddedTimes.append(keyTimes[-1] + outOffsetTime)
        paddedTimes.append(keyTimes[-1] + 2 * outOffsetTime)
        blendStoredKeyTimes[curve] = paddedTimes
        indexes = []
        keysSelTemp = sorted(blendStoredKeysSel[n])
        si = 0
        firstTime = True
        for i, keyTime in enumerate(paddedTimes):
            if si < len(keysSelTemp) and abs(keysSelTemp[si] - keyTime) < 0.001:
                if firstTime:
                    indexes.append([])
                    firstTime = False
                indexes[-1].append(i)
                si += 1
            else:
                firstTime = True
        for i, segment in enumerate(indexes):
            indexes[i].insert(0, segment[0] - 1)
            indexes[i].append(segment[-1] + 1)
        blendStoredIndexes[curve] = indexes
        firstRealValue = reader(0)
        lastRealValue = reader(numKeys - 1)
        neededPositions = set()
        for segment in indexes:
            neededPositions.update(segment)
        keyValuesMap = {}
        for pos in neededPositions:
            if pos == 0:
                keyValuesMap[pos] = firstRealValue - 2 * inOffsetVal
            elif pos == 1:
                keyValuesMap[pos] = firstRealValue - inOffsetVal
            elif pos == numKeys + 2:
                keyValuesMap[pos] = lastRealValue + outOffsetVal
            elif pos == numKeys + 3:
                keyValuesMap[pos] = lastRealValue + 2 * outOffsetVal
            else:
                realIdx = pos - 2
                if 0 <= realIdx < numKeys:
                    keyValuesMap[pos] = reader(realIdx)
        blendStoredKeyValues[curve] = keyValuesMap


def execute_blend_key_transform(slider_val):
    if not blendStoredAnimCurves:
        return
    tValue = (slider_val + 100) / 100.0
    p = slider_utils.folded_ease(slider_val)
    for curve in blendStoredAnimCurves:
        if curve not in blendStoredIndexes or curve not in blendStoredMfnCurves:
            continue
        mfn = blendStoredMfnCurves[curve]
        setter = blendStoredSetters[curve]
        try:
            num_keys = mfn.numKeys
        except:
            continue
        keyValues = blendStoredKeyValues[curve]
        segments = blendStoredIndexes[curve]
        for segment in segments:
            fv = keyValues[segment[0]]
            lv = keyValues[segment[-1]]
            has_real_left_neighbor = segment[0] > 1
            has_real_right_neighbor = segment[-1] < num_keys + 2
            if not has_real_left_neighbor and not has_real_right_neighbor:
                selected_keys_in_segment = segment[1:-1]
                if len(selected_keys_in_segment) >= 2:
                    fv = keyValues[selected_keys_in_segment[0]]
                    lv = keyValues[selected_keys_in_segment[-1]]
            elif not has_real_left_neighbor and len(segment) > 3:
                selected_keys_in_segment = segment[1:-1]
                if selected_keys_in_segment:
                    fv = keyValues[selected_keys_in_segment[0]]
            elif not has_real_right_neighbor and len(segment) > 3:
                selected_keys_in_segment = segment[1:-1]
                if selected_keys_in_segment:
                    lv = keyValues[selected_keys_in_segment[-1]]
            pivot = fv if tValue <= 1 else lv
            for i, keyIndex in enumerate(segment):
                if 1 <= i <= len(segment) - 2:
                    realIndex = keyIndex - 2
                    if 0 <= realIndex < num_keys:
                        originalValue = keyValues[keyIndex]
                        newValue = pivot + (originalValue - pivot) * p
                        try:
                            setter(realIndex, newValue)
                        except:
                            continue


def setup_blend_scale_transform_data():
    global blendPadKeyValues, blendPadKeyTimes, blendPadIndexes
    blendPadKeyValues = {}
    blendPadKeyTimes = {}
    blendPadIndexes = {}
    for n, curve in enumerate(blendStoredAnimCurves):
        if not cmds.objExists(curve) or not blendStoredKeysSel[n]:
            continue
        keyValues = cmds.keyframe(curve, query=True, valueChange=True)
        keyTimes = cmds.keyframe(curve, query=True, timeChange=True)
        if not keyValues or not keyTimes:
            continue
        if len(keyTimes) == 1:
            inOffsetTime = 1
            inOffsetVal = 0
            outOffsetTime = 1
            outOffsetVal = 0
        else:
            inOffsetTime = keyTimes[1] - keyTimes[0]
            inOffsetVal = keyValues[1] - keyValues[0]
            outOffsetTime = keyTimes[-1] - keyTimes[-2]
            outOffsetVal = keyValues[-1] - keyValues[-2]
        keyValues.insert(0, keyValues[0] - inOffsetVal)
        keyTimes.insert(0, keyTimes[0] - inOffsetTime)
        keyValues.insert(0, keyValues[0] - inOffsetVal)
        keyTimes.insert(0, keyTimes[0] - inOffsetTime)
        keyValues.append(keyValues[-1] + outOffsetVal)
        keyTimes.append(keyTimes[-1] + outOffsetTime)
        keyValues.append(keyValues[-1] + outOffsetVal)
        keyTimes.append(keyTimes[-1] + outOffsetTime)
        blendPadKeyValues[curve] = keyValues
        blendPadKeyTimes[curve] = keyTimes
        indexes = []
        keysSelTemp = list(blendStoredKeysSel[n])
        firstTime = True
        for i, keyTime in enumerate(keyTimes):
            for j, selTime in enumerate(keysSelTemp):
                if abs(selTime - keyTime) < 0.001:
                    if firstTime:
                        indexes.append([])
                        firstTime = False
                    indexes[-1].append(i)
                    keysSelTemp.pop(j)
                    break
            else:
                firstTime = True
        for i, segment in enumerate(indexes):
            indexes[i].insert(0, segment[0] - 1)
            indexes[i].append(segment[-1] + 1)
        blendPadIndexes[curve] = indexes


def execute_blend_scale_transform(slider_val):
    global blendLastValue, blendScaleValue
    if not blendStoredAnimCurves:
        return
    tValue = (slider_val + 100) / 100.0
    p = slider_utils.folded_ease(slider_val)
    if p == 0:
        p = 0.0000001
    if blendPushClick and blendLastValue != 0:
        blendScaleValue = (1.0 / blendLastValue) * p
    else:
        blendScaleValue = p
    for curve in blendStoredAnimCurves:
        if curve not in blendPadIndexes or not cmds.objExists(curve):
            continue
        keyValues = blendPadKeyValues[curve]
        segments = blendPadIndexes[curve]
        allTimes = cmds.keyframe(curve, query=True, timeChange=True) or []
        numKeys = len(allTimes)
        for segment in segments:
            fv = keyValues[segment[0]]
            lv = keyValues[segment[-1]]
            has_real_left_neighbor = segment[0] > 1
            has_real_right_neighbor = segment[-1] < len(keyValues) - 2
            if not has_real_left_neighbor and not has_real_right_neighbor:
                selected_keys_in_segment = segment[1:-1]
                if len(selected_keys_in_segment) >= 2:
                    fv = keyValues[selected_keys_in_segment[0]]
                    lv = keyValues[selected_keys_in_segment[-1]]
            elif not has_real_left_neighbor and len(segment) > 3:
                selected_keys_in_segment = segment[1:-1]
                if selected_keys_in_segment:
                    fv = keyValues[selected_keys_in_segment[0]]
            elif not has_real_right_neighbor and len(segment) > 3:
                selected_keys_in_segment = segment[1:-1]
                if selected_keys_in_segment:
                    lv = keyValues[selected_keys_in_segment[-1]]
            pivot = fv if tValue <= 1 else lv
            if len(segment) >= 3:
                startReal = segment[1] - 2
                endReal = segment[-2] - 2
                startReal = max(0, startReal)
                endReal = min(numKeys - 1, endReal)
                if startReal <= endReal:
                    try:
                        cmds.scaleKey(curve, index=(startReal, endReal), valuePivot=pivot, valueScale=blendScaleValue)
                    except:
                        for realIndex in range(startReal, endReal + 1):
                            try:
                                currentVal = cmds.keyframe(curve, index=(realIndex, realIndex), query=True, valueChange=True)[0]
                                newValue = pivot + (currentVal - pivot) * blendScaleValue
                                cmds.keyframe(curve, edit=True, index=(realIndex, realIndex), valueChange=newValue)
                            except:
                                continue
    blendLastValue = p


def commit_blend_key_transform():
    for curve in blendStoredAnimCurves:
        if curve not in blendStoredIndexes or curve not in blendStoredMfnCurves:
            continue
        if curve not in blendStoredReaders or curve not in blendStoredSetters:
            continue
        if curve not in blendStoredKeyValues:
            continue
        if not cmds.objExists(curve):
            continue
        mfn = blendStoredMfnCurves[curve]
        reader = blendStoredReaders[curve]
        setter = blendStoredSetters[curve]
        keyValues = blendStoredKeyValues[curve]
        try:
            num_keys = mfn.numKeys
        except:
            continue
        segments = blendStoredIndexes[curve]
        committedIndexes = set()
        for segment in segments:
            for i, keyIndex in enumerate(segment):
                if 1 <= i <= len(segment) - 2:
                    realIndex = keyIndex - 2
                    if realIndex in committedIndexes:
                        continue
                    if 0 <= realIndex < num_keys:
                        committedIndexes.add(realIndex)
                        try:
                            finalValue = reader(realIndex)
                            originalValue = keyValues[keyIndex]
                            setter(realIndex, originalValue)
                            cmds.keyframe(curve, edit=True, index=(realIndex, realIndex), valueChange=finalValue, absolute=True)
                        except:
                            continue


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global blendPushClick, blendStoredAnimCurves, blendStoredKeysSel, blendGetFrom
    global blendGraphEditorScaleMode, blendLastValue, blendScaleValue
    status = "Blend: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status
    current_time = time.time() * 1000
    time_since_last = current_time - last_update_time
    if time_since_last < update_throttle_ms and blendPushClick:
        return last_update_time, status
    last_update_time = current_time
    if not blendPushClick:
        selected = cmds.ls(selection=True)
        if selected:
            slider_utils.safe_undo_chunk_open("Blend to Neighbors")
            cmds.refresh(suspend=True)
            try:
                getCurves = slider_utils.get_anim_curves()
                blendStoredAnimCurves = getCurves[0] or []
                blendGetFrom = getCurves[1]
                if not blendStoredAnimCurves:
                    blendStoredAnimCurves = _auto_curves_for_selection(selected)
                    blendGetFrom = "channelBox"
                if not blendStoredAnimCurves:
                    slider_utils.safe_undo_chunk_close()
                    return last_update_time, status
                blendPushClick = True
                blendMfnCache.update(slider_utils.get_mfn_anim_curves_bulk(blendStoredAnimCurves))
                blendStoredKeysSel = slider_utils.get_keys_sel(blendStoredAnimCurves, blendGetFrom, mfn_cache=blendMfnCache, key_times_cache=blendKeyTimesCache)
                hasSelectedKeys = any(keyList for keyList in blendStoredKeysSel if keyList)
                blendGraphEditorScaleMode = bool(hasSelectedKeys and blendGetFrom == "graphEditor")
                if blendGraphEditorScaleMode:
                    blendLastValue = 0
                    blendScaleValue = 1
                    setup_blend_scale_transform_data()
                if not hasSelectedKeys:
                    currentTime = cmds.currentTime(query=True)
                    existingSet = set(cmds.ls(blendStoredAnimCurves))
                    pendingCurves = []
                    stepCurves = []
                    autoCurves = []
                    for curve in blendStoredAnimCurves:
                        if curve not in existingSet:
                            continue
                        pendingCurves.append(curve)
                        mfn = blendMfnCache.get(curve)
                        if mfn is None:
                            mfn = slider_utils.get_mfn_anim_curve(curve)
                        if mfn is None:
                            autoCurves.append(curve)
                            continue
                        blendMfnCache[curve] = mfn
                        keyTimes = blendKeyTimesCache.get(curve)
                        if keyTimes is None:
                            keyTimes = slider_utils.get_all_key_times(mfn)
                        if not keyTimes:
                            autoCurves.append(curve)
                            continue
                        keyExists = any(abs(t - currentTime) < 0.001 for t in keyTimes)
                        if keyExists:
                            continue
                        prevIndex = None
                        nextIndex = None
                        for idx, t in enumerate(keyTimes):
                            if t < currentTime - 0.001:
                                prevIndex = idx
                            elif t > currentTime + 0.001:
                                nextIndex = idx
                                break
                        isStep = False
                        try:
                            if prevIndex is not None:
                                if mfn.outTangentType(prevIndex) == oma2.MFnAnimCurve.kTangentStep:
                                    isStep = True
                            if not isStep and nextIndex is not None:
                                if mfn.outTangentType(nextIndex) == oma2.MFnAnimCurve.kTangentStep:
                                    isStep = True
                        except:
                            isStep = False
                        if isStep:
                            stepCurves.append(curve)
                        else:
                            autoCurves.append(curve)
                    if pendingCurves:
                        cmds.setKeyframe(pendingCurves, time=currentTime, insert=True)
                        for curve in pendingCurves:
                            blendKeyTimesCache.pop(curve, None)
                    if stepCurves:
                        cmds.keyTangent(stepCurves, time=(currentTime, currentTime), inTangentType="auto", outTangentType="step")
                    if autoCurves:
                        cmds.keyTangent(autoCurves, time=(currentTime, currentTime), inTangentType="auto", outTangentType="auto")
                    blendStoredKeysSel = []
                    for curve in blendStoredAnimCurves:
                        if curve in existingSet:
                            blendStoredKeysSel.append([currentTime])
                        else:
                            blendStoredKeysSel.append([])
                    setup_blend_key_transform_data()
                elif not blendGraphEditorScaleMode:
                    setup_blend_key_transform_data()
            finally:
                cmds.refresh(suspend=False)
        else:
            return last_update_time, status
    if blendStoredAnimCurves:
        cmds.refresh(suspend=True)
        try:
            if blendGraphEditorScaleMode:
                execute_blend_scale_transform(value)
            else:
                execute_blend_key_transform(value)
        finally:
            cmds.refresh(suspend=False)
    return last_update_time, status


def reset_slider(slider_widget):
    global blendPushClick, blendStoredKeyValues, blendStoredKeyTimes, blendStoredIndexes
    global blendStoredAnimCurves, blendStoredKeysSel, blendStoredMfnCurves, blendStoredSetters, blendStoredReaders, blendMfnCache, blendKeyTimesCache
    global blendGraphEditorScaleMode, blendLastValue, blendScaleValue, blendPadKeyValues, blendPadKeyTimes, blendPadIndexes
    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)
    if blendPushClick:
        if blendGraphEditorScaleMode:
            slider_utils.safe_undo_chunk_close()
        else:
            cmds.refresh(suspend=True)
            try:
                commit_blend_key_transform()
            finally:
                cmds.refresh(suspend=False)
            slider_utils.safe_undo_chunk_close()
    blendPushClick = False
    blendGraphEditorScaleMode = False
    blendLastValue = 0
    blendScaleValue = 1
    blendPadKeyValues = {}
    blendPadKeyTimes = {}
    blendPadIndexes = {}
    blendStoredKeyValues = {}
    blendStoredKeyTimes = {}
    blendStoredIndexes = {}
    blendStoredAnimCurves = []
    blendStoredKeysSel = []
    blendStoredMfnCurves = {}
    blendStoredSetters = {}
    blendStoredReaders = {}
    blendMfnCache = {}
    blendKeyTimesCache = {}