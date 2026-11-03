import time
import maya.cmds as cmds
import maya.utils
from maya import mel

from . import slider_utils

biPushClick = False
biStoredAnimCurves = []
biStoredKeysSel = []
biMfnCache = {}
biGetFrom = "graphEditor"

biStoredMfnCurves = {}
biStoredSetters = {}
biStoredReaders = {}
biStoredOriginalValues = {}
biStoredTargets = {}

biIterationCount = 0
biLastSelectionSignature = None
biUndoScriptJob = None
biUndoWatchRegistered = False


def _reset_iteration_count_on_undo(*args):
    global biIterationCount
    biIterationCount = 0


def _register_undo_watch():
    global biUndoScriptJob, biUndoWatchRegistered
    if biUndoWatchRegistered:
        return
    try:
        undoJob = cmds.scriptJob(event=["Undo", _reset_iteration_count_on_undo], protected=True)
        redoJob = cmds.scriptJob(event=["Redo", _reset_iteration_count_on_undo], protected=True)
        biUndoScriptJob = (undoJob, redoJob)
    except:
        biUndoScriptJob = None
    biUndoWatchRegistered = True


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


def _setup_blend_infinity_data():
    global biStoredOriginalValues, biStoredTargets
    global biStoredMfnCurves, biStoredSetters, biStoredReaders
    biStoredOriginalValues = {}
    biStoredTargets = {}
    biStoredMfnCurves = {}
    biStoredSetters = {}
    biStoredReaders = {}
    angle_unit, linear_unit = slider_utils.get_current_units()
    for n, curve in enumerate(biStoredAnimCurves):
        if not biStoredKeysSel[n]:
            continue
        mfn = biMfnCache.get(curve)
        if mfn is None:
            mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        biStoredMfnCurves[curve] = mfn
        reader = slider_utils.make_value_reader(mfn, angle_unit, linear_unit)
        setter = slider_utils.make_value_setter(mfn, angle_unit, linear_unit)
        biStoredReaders[curve] = reader
        biStoredSetters[curve] = setter
        numKeys = mfn.numKeys
        if not numKeys:
            continue
        originals = {}
        targets = {}
        sortedTimes = sorted(biStoredKeysSel[n])
        if not sortedTimes:
            continue
        indices = []
        for t in sortedTimes:
            idx = slider_utils.get_key_index_at_time(mfn, t)
            if idx != -1:
                indices.append(idx)
        if not indices:
            continue
        for idx in indices:
            originals[idx] = reader(idx)
        firstIdx = indices[0]
        if firstIdx - 1 >= 0:
            prevVal1 = reader(firstIdx - 1)
            t1 = mfn.input(firstIdx - 1).value
            slope = None
            haveTwoPrev = False
            prevVal2 = None
            if firstIdx - 2 >= 0:
                haveTwoPrev = True
                prevVal2 = reader(firstIdx - 2)
                t2 = mfn.input(firstIdx - 2).value
                deltaTime = t1 - t2
                if deltaTime != 0:
                    slope = (prevVal1 - prevVal2) / deltaTime
            for idx in indices:
                originalValue = originals[idx]
                tSel = mfn.input(idx).value
                targetLeft = 2 * prevVal1 - originalValue
                if haveTwoPrev:
                    if slope is not None:
                        targetRight = prevVal1 + slope * (tSel - t1)
                    else:
                        targetRight = prevVal1 + (prevVal1 - prevVal2)
                else:
                    targetRight = prevVal1
                targets[idx] = (targetRight, targetLeft)
        else:
            firstValue = originals[firstIdx]
            reversedValues = list(reversed([originals[i] for i in indices]))
            for pos, idx in enumerate(indices):
                targets[idx] = (firstValue, reversedValues[pos])
        biStoredOriginalValues[curve] = originals
        biStoredTargets[curve] = targets


def _execute(value):
    if not biStoredAnimCurves:
        return
    dragStrength = 0.0
    useLeft = value < 0
    if value != 0:
        dragStrength = abs(value) / 100.0
        if dragStrength > 1.0:
            dragStrength = 1.0
    for curve in biStoredAnimCurves:
        if curve not in biStoredTargets or curve not in biStoredSetters:
            continue
        if curve not in biStoredMfnCurves:
            continue
        setter = biStoredSetters[curve]
        originals = biStoredOriginalValues[curve]
        targets = biStoredTargets[curve]
        for idx, targetPair in targets.items():
            originalValue = originals[idx]
            target = targetPair[1] if useLeft else targetPair[0]
            if target is None or dragStrength <= 0.0:
                newValue = originalValue
            else:
                newValue = originalValue + (target - originalValue) * dragStrength
            try:
                setter(idx, newValue)
            except:
                continue


def _commit():
    for curve in biStoredAnimCurves:
        if curve not in biStoredTargets or curve not in biStoredMfnCurves:
            continue
        if curve not in biStoredReaders or curve not in biStoredSetters:
            continue
        if curve not in biStoredOriginalValues:
            continue
        if not cmds.objExists(curve):
            continue
        reader = biStoredReaders[curve]
        setter = biStoredSetters[curve]
        originals = biStoredOriginalValues[curve]
        targets = biStoredTargets[curve]
        for idx in targets:
            if idx not in originals:
                continue
            try:
                finalValue = reader(idx)
                originalValue = originals[idx]
                setter(idx, originalValue)
                cmds.keyframe(curve, edit=True, index=(idx, idx), valueChange=finalValue, absolute=True)
            except:
                continue


def _gather_targets():
    global biStoredAnimCurves, biStoredKeysSel, biGetFrom, biMfnCache
    global biIterationCount, biLastSelectionSignature

    selected = cmds.ls(selection=True)
    if not selected:
        return False

    getCurves = slider_utils.get_anim_curves()
    biStoredAnimCurves = getCurves[0] or []
    biGetFrom = getCurves[1]
    if not biStoredAnimCurves:
        biStoredAnimCurves = _resolve_channelbox_curves(selected)
        biGetFrom = "channelBox"
    if not biStoredAnimCurves:
        return False

    biMfnCache = slider_utils.get_mfn_anim_curves_bulk(biStoredAnimCurves)
    biStoredKeysSel = slider_utils.get_keys_sel(biStoredAnimCurves, biGetFrom, mfn_cache=biMfnCache)
    hasSelectedKeys = any(keyList for keyList in biStoredKeysSel if keyList)

    if not hasSelectedKeys:
        currentTime = cmds.currentTime(query=True)
        existingSet = set(cmds.ls(biStoredAnimCurves))
        pendingCurves = []
        stepCurves = []
        autoCurves = []
        for curve in biStoredAnimCurves:
            if curve not in existingSet:
                continue
            pendingCurves.append(curve)
            mfn = biMfnCache.get(curve)
            if mfn is None:
                mfn = slider_utils.get_mfn_anim_curve(curve)
            if mfn is None:
                autoCurves.append(curve)
                continue
            biMfnCache[curve] = mfn
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
        biStoredKeysSel = []
        for curve in biStoredAnimCurves:
            if curve in existingSet:
                biStoredKeysSel.append([currentTime])
            else:
                biStoredKeysSel.append([])

    _setup_blend_infinity_data()

    signature = tuple(sorted(
        (curve, tuple(sorted(biStoredKeysSel[i])))
        for i, curve in enumerate(biStoredAnimCurves)
        if biStoredKeysSel[i]
    ))
    if signature != biLastSelectionSignature:
        biIterationCount = 0
        biLastSelectionSignature = signature

    return True


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global biPushClick

    status = "Blend to Infinity: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and biPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not biPushClick:
        _register_undo_watch()
        slider_utils.safe_undo_chunk_open("Blend to Infinity")
        if not _gather_targets():
            slider_utils.safe_undo_chunk_close()
            return last_update_time, status
        biPushClick = True

    cmds.refresh(suspend=True)
    try:
        _execute(value)
    finally:
        cmds.refresh(suspend=False)
        if slider_utils.IS_MACOS:
            cmds.refresh()
            maya.utils.processIdleEvents()

    return last_update_time, status


def reset_slider(slider_widget):
    global biPushClick, biStoredAnimCurves, biStoredKeysSel, biMfnCache
    global biStoredMfnCurves, biStoredSetters, biStoredReaders
    global biStoredOriginalValues, biStoredTargets, biIterationCount

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if biPushClick:
        cmds.refresh(suspend=True)
        try:
            _commit()
        finally:
            cmds.refresh(suspend=False)
        slider_utils.safe_undo_chunk_close()
        biIterationCount += 1

    biPushClick = False
    biStoredAnimCurves = []
    biStoredKeysSel = []
    biMfnCache = {}
    biStoredMfnCurves = {}
    biStoredSetters = {}
    biStoredReaders = {}
    biStoredOriginalValues = {}
    biStoredTargets = {}
