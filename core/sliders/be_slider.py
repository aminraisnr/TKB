import time
import math
import maya.cmds as cmds
import maya.utils
from maya import mel

from . import slider_utils

EASE_SHAPE_POWER = 3.0
EASE_POWER_INCREMENT = 2.5
MAX_EASE_POWER = 40.0

bePushClick = False
beStoredAnimCurves = []
beStoredKeysSel = []
beMfnCache = {}
beGetFrom = "graphEditor"

beStoredMfnCurves = {}
beStoredSetters = {}
beStoredReaders = {}
beStoredKeyValues = {}
beStoredKeyTimes = {}
beStoredIndexes = {}

beLastSelectionSignature = None
beFrozenBoundaryData = {}
beTargetPowersPositive = {}
beTargetPowersNegative = {}


def _resolve_channelbox_curves(selected):
    channel_attrs = []
    try:
        channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        channel_attrs = cmds.channelBox(channel_box, query=True, selectedMainAttributes=True) or []
    except:
        channel_attrs = []
    curves = []
    for obj in selected:
        attrs = channel_attrs if channel_attrs else (cmds.listAttr(obj, keyable=True, unlocked=True) or [])
        for attr in attrs:
            plug = obj + "." + attr
            if not cmds.objExists(plug):
                continue
            conns = cmds.listConnections(plug, source=True, destination=False) or []
            for c in conns:
                if cmds.nodeType(c).startswith("animCurve") and c not in curves:
                    curves.append(c)
    return curves


def _ease_value(t, exponent=slider_utils.SLIDER_EASE_EXPONENT):
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    return t ** exponent


def _smoothstep(t):
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _measure_implied_power(currentValue, fv, lv, ratio, isPositive):
    span = lv - fv
    if abs(span) < 1e-9:
        return None
    shaped = (currentValue - fv) / span
    if shaped <= 1e-9 or shaped >= (1.0 - 1e-9):
        return None
    if ratio <= 1e-9 or ratio >= (1.0 - 1e-9):
        return None
    try:
        if isPositive:
            base = 1.0 - ratio
            val = 1.0 - shaped
            if base <= 1e-9 or base >= (1.0 - 1e-9) or val <= 0.0:
                return None
            power = math.log(val) / math.log(base)
        else:
            if ratio <= 0.0 or shaped <= 0.0:
                return None
            power = math.log(shaped) / math.log(ratio)
    except (ValueError, ZeroDivisionError):
        return None
    if power != power:
        return None
    return power


def _setup_blend_ease_data():
    global beStoredKeyValues, beStoredKeyTimes, beStoredIndexes
    global beStoredMfnCurves, beStoredSetters, beStoredReaders
    beStoredKeyValues = {}
    beStoredKeyTimes = {}
    beStoredIndexes = {}
    beStoredMfnCurves = {}
    beStoredSetters = {}
    beStoredReaders = {}
    angle_unit, linear_unit = slider_utils.get_current_units()
    for n, curve in enumerate(beStoredAnimCurves):
        if not beStoredKeysSel[n]:
            continue
        mfn = beMfnCache.get(curve)
        if mfn is None:
            mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        beStoredMfnCurves[curve] = mfn
        reader = slider_utils.make_value_reader(mfn, angle_unit, linear_unit)
        setter = slider_utils.make_value_setter(mfn, angle_unit, linear_unit)
        beStoredReaders[curve] = reader
        beStoredSetters[curve] = setter
        numKeys = mfn.numKeys
        if not numKeys:
            continue
        keyTimes = slider_utils.get_all_key_times(mfn)
        if not keyTimes:
            continue
        if numKeys == 1:
            inOffsetTime = 1
            inOffsetVal = 0
            outOffsetTime = 1
            outOffsetVal = 0
            firstRealValue = reader(0)
            lastRealValue = reader(0)
        else:
            inOffsetTime = keyTimes[1] - keyTimes[0]
            outOffsetTime = keyTimes[-1] - keyTimes[-2]
            frozen = beFrozenBoundaryData.get(curve)
            if frozen is not None:
                inOffsetVal, outOffsetVal, firstRealValue, lastRealValue = frozen
            else:
                inOffsetVal = reader(1) - reader(0)
                outOffsetVal = reader(numKeys - 1) - reader(numKeys - 2)
                firstRealValue = reader(0)
                lastRealValue = reader(numKeys - 1)
                beFrozenBoundaryData[curve] = (inOffsetVal, outOffsetVal, firstRealValue, lastRealValue)
        paddedTimes = [keyTimes[0] - 2 * inOffsetTime, keyTimes[0] - inOffsetTime]
        paddedTimes.extend(keyTimes)
        paddedTimes.append(keyTimes[-1] + outOffsetTime)
        paddedTimes.append(keyTimes[-1] + 2 * outOffsetTime)
        beStoredKeyTimes[curve] = paddedTimes
        indexes = []
        keysSelTemp = sorted(beStoredKeysSel[n])
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
        beStoredIndexes[curve] = indexes
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
        beStoredKeyValues[curve] = keyValuesMap


def _compute_target_powers(isPositive):
    targetPowers = {}
    for curve in beStoredAnimCurves:
        if curve not in beStoredIndexes or curve not in beStoredKeyValues:
            continue
        keyValues = beStoredKeyValues[curve]
        keyTimes = beStoredKeyTimes.get(curve)
        if keyTimes is None:
            continue
        segments = beStoredIndexes[curve]
        powers = []
        for segment in segments:
            realPositions = segment[1:-1]
            if not realPositions:
                powers.append(EASE_SHAPE_POWER)
                continue
            fv = keyValues[segment[0]]
            lv = keyValues[segment[-1]]
            t_fv = keyTimes[segment[0]]
            t_lv = keyTimes[segment[-1]]
            span = t_lv - t_fv
            measurements = []
            for keyIndex in realPositions:
                currentValue = keyValues[keyIndex]
                keyTime = keyTimes[keyIndex]
                if span != 0:
                    ratio = (keyTime - t_fv) / span
                else:
                    ratio = 0.5
                if ratio < 0.0:
                    ratio = 0.0
                elif ratio > 1.0:
                    ratio = 1.0
                implied = _measure_implied_power(currentValue, fv, lv, ratio, isPositive)
                if implied is not None:
                    measurements.append(implied)
            if measurements:
                measurements.sort()
                mid = len(measurements) // 2
                if len(measurements) % 2 == 1:
                    currentPower = measurements[mid]
                else:
                    currentPower = (measurements[mid - 1] + measurements[mid]) / 2.0
            else:
                currentPower = MAX_EASE_POWER
            if currentPower < EASE_SHAPE_POWER:
                currentPower = EASE_SHAPE_POWER
            targetPower = currentPower + EASE_POWER_INCREMENT
            if targetPower > MAX_EASE_POWER:
                targetPower = MAX_EASE_POWER
            powers.append(targetPower)
        targetPowers[curve] = powers
    return targetPowers


def _resolve_target_powers():
    global beTargetPowersPositive, beTargetPowersNegative
    beTargetPowersPositive = _compute_target_powers(True)
    beTargetPowersNegative = _compute_target_powers(False)


def _execute(value):
    if not beStoredAnimCurves:
        return
    dragStrength = abs(value) / 100.0
    if dragStrength > 1.0:
        dragStrength = 1.0
    isPositive = value > 0
    targetPowers = beTargetPowersPositive if isPositive else beTargetPowersNegative
    for curve in beStoredAnimCurves:
        if curve not in beStoredIndexes or curve not in beStoredSetters:
            continue
        if curve not in beStoredMfnCurves:
            continue
        mfn = beStoredMfnCurves[curve]
        setter = beStoredSetters[curve]
        try:
            num_keys = mfn.numKeys
        except:
            continue
        keyValues = beStoredKeyValues[curve]
        keyTimes = beStoredKeyTimes[curve]
        segments = beStoredIndexes[curve]
        powers = targetPowers.get(curve, [])
        for segIdx, segment in enumerate(segments):
            realPositions = segment[1:-1]
            if not realPositions:
                continue
            effectivePower = powers[segIdx] if segIdx < len(powers) else EASE_SHAPE_POWER
            fv = keyValues[segment[0]]
            lv = keyValues[segment[-1]]
            t_fv = keyTimes[segment[0]]
            t_lv = keyTimes[segment[-1]]
            span = t_lv - t_fv
            for keyIndex in realPositions:
                realIndex = keyIndex - 2
                if not (0 <= realIndex < num_keys):
                    continue
                originalValue = keyValues[keyIndex]
                if dragStrength <= 0.0:
                    newValue = originalValue
                else:
                    keyTime = keyTimes[keyIndex]
                    if span != 0:
                        ratio = (keyTime - t_fv) / span
                    else:
                        ratio = 0.5
                    if ratio < 0.0:
                        ratio = 0.0
                    elif ratio > 1.0:
                        ratio = 1.0
                    if isPositive:
                        shaped = 1.0 - (1.0 - ratio) ** effectivePower
                    else:
                        shaped = ratio ** effectivePower
                    targetValue = fv + (lv - fv) * shaped
                    newValue = originalValue + (targetValue - originalValue) * dragStrength
                try:
                    setter(realIndex, newValue)
                except:
                    continue


def _commit():
    for curve in beStoredAnimCurves:
        if curve not in beStoredIndexes or curve not in beStoredMfnCurves:
            continue
        if curve not in beStoredReaders or curve not in beStoredSetters:
            continue
        if not cmds.objExists(curve):
            continue
        reader = beStoredReaders[curve]
        setter = beStoredSetters[curve]
        keyValues = beStoredKeyValues[curve]
        try:
            num_keys_local = beStoredMfnCurves[curve].numKeys
        except:
            continue
        segments = beStoredIndexes[curve]
        committedIndexes = set()
        for segment in segments:
            for i, keyIndex in enumerate(segment):
                if 1 <= i <= len(segment) - 2:
                    realIndex = keyIndex - 2
                    if realIndex in committedIndexes:
                        continue
                    if 0 <= realIndex < num_keys_local:
                        committedIndexes.add(realIndex)
                        try:
                            finalValue = reader(realIndex)
                            originalValue = keyValues[keyIndex]
                            setter(realIndex, originalValue)
                            cmds.keyframe(curve, edit=True, index=(realIndex, realIndex), valueChange=finalValue, absolute=True)
                        except:
                            continue


def _gather_targets():
    global beStoredAnimCurves, beStoredKeysSel, beGetFrom, beMfnCache
    global beLastSelectionSignature, beFrozenBoundaryData

    selected = cmds.ls(selection=True)
    if not selected:
        return False

    getCurves = slider_utils.get_anim_curves()
    beStoredAnimCurves = getCurves[0] or []
    beGetFrom = getCurves[1]
    if not beStoredAnimCurves:
        beStoredAnimCurves = _resolve_channelbox_curves(selected)
        beGetFrom = "channelBox"
    if not beStoredAnimCurves:
        return False

    beMfnCache = slider_utils.get_mfn_anim_curves_bulk(beStoredAnimCurves)
    beStoredKeysSel = slider_utils.get_keys_sel(beStoredAnimCurves, beGetFrom, mfn_cache=beMfnCache)
    hasSelectedKeys = any(keyList for keyList in beStoredKeysSel if keyList)

    if not hasSelectedKeys:
        currentTime = cmds.currentTime(query=True)
        existingSet = set(cmds.ls(beStoredAnimCurves))
        pendingCurves = []
        stepCurves = []
        autoCurves = []
        for curve in beStoredAnimCurves:
            if curve not in existingSet:
                continue
            pendingCurves.append(curve)
            mfn = beMfnCache.get(curve)
            if mfn is None:
                mfn = slider_utils.get_mfn_anim_curve(curve)
            if mfn is None:
                autoCurves.append(curve)
                continue
            beMfnCache[curve] = mfn
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
                if prevIndex is not None and mfn.outTangentType(prevIndex) == slider_utils.oma2.MFnAnimCurve.kTangentStep:
                    isStep = True
                if not isStep and nextIndex is not None and mfn.outTangentType(nextIndex) == slider_utils.oma2.MFnAnimCurve.kTangentStep:
                    isStep = True
            except:
                isStep = False
            if isStep:
                stepCurves.append(curve)
            else:
                autoCurves.append(curve)
        if pendingCurves:
            cmds.setKeyframe(pendingCurves, time=currentTime, insert=True)
        if stepCurves:
            cmds.keyTangent(stepCurves, time=(currentTime, currentTime), inTangentType="auto", outTangentType="step")
        if autoCurves:
            cmds.keyTangent(autoCurves, time=(currentTime, currentTime), inTangentType="auto", outTangentType="auto")
        beStoredKeysSel = []
        for curve in beStoredAnimCurves:
            if curve in existingSet:
                beStoredKeysSel.append([currentTime])
            else:
                beStoredKeysSel.append([])

    signature = tuple(sorted(
        (curve, tuple(sorted(beStoredKeysSel[i])))
        for i, curve in enumerate(beStoredAnimCurves)
        if beStoredKeysSel[i]
    ))
    if signature != beLastSelectionSignature:
        beLastSelectionSignature = signature
        beFrozenBoundaryData = {}

    _setup_blend_ease_data()

    return True


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global bePushClick

    status = "Blend to Ease: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and bePushClick:
        return last_update_time, status
    last_update_time = current_time

    if not bePushClick:
        slider_utils.safe_undo_chunk_open("Blend to Ease")
        try:
            gathered = _gather_targets()
        except:
            gathered = False
        if not gathered:
            slider_utils.safe_undo_chunk_close()
            bePushClick = False
            beStoredAnimCurves = []
            beStoredKeysSel = []
            beMfnCache = {}
            beStoredMfnCurves = {}
            beStoredSetters = {}
            beStoredReaders = {}
            beStoredKeyValues = {}
            beStoredKeyTimes = {}
            beStoredIndexes = {}
            return last_update_time, status
        try:
            _resolve_target_powers()
        except:
            pass
        bePushClick = True

    cmds.refresh(suspend=True)
    try:
        _execute(value)
    except:
        pass
    finally:
        cmds.refresh(suspend=False)
        if slider_utils.IS_MACOS:
            cmds.refresh()
            maya.utils.processIdleEvents()

    return last_update_time, status


def reset_slider(slider_widget):
    global bePushClick, beStoredAnimCurves, beStoredKeysSel, beMfnCache
    global beStoredMfnCurves, beStoredSetters, beStoredReaders
    global beStoredKeyValues, beStoredKeyTimes, beStoredIndexes

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if bePushClick:
        try:
            cmds.refresh(suspend=True)
            try:
                _commit()
            except:
                pass
            finally:
                cmds.refresh(suspend=False)
        finally:
            slider_utils.safe_undo_chunk_close()
            bePushClick = False
            beStoredAnimCurves = []
            beStoredKeysSel = []
            beMfnCache = {}
            beStoredMfnCurves = {}
            beStoredSetters = {}
            beStoredReaders = {}
            beStoredKeyValues = {}
            beStoredKeyTimes = {}
            beStoredIndexes = {}
        return

    bePushClick = False
    beStoredAnimCurves = []
    beStoredKeysSel = []
    beMfnCache = {}
    beStoredMfnCurves = {}
    beStoredSetters = {}
    beStoredReaders = {}
    beStoredKeyValues = {}
    beStoredKeyTimes = {}
    beStoredIndexes = {}