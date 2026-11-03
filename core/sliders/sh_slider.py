import os
import sys
import time
import maya.cmds as cmds
import maya.utils
from maya import mel

from . import slider_utils

SMOOTH_PLUGIN_NAME = "AnimoSmoothKeysPlugin"
SMOOTH_STRENGTH = 0.5
SMOOTH_ITERATIONS = 5
HARSH_STRENGTH = 3.0

shPushClick = False
shStoredAnimCurves = []
shStoredKeysSel = []
shMfnCache = {}
shGetFrom = "graphEditor"
shTweenData = {}

_smooth_plugin_checked = False
_smooth_plugin_loaded = False


def _get_animo_tools_path():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.normpath(os.path.join(script_dir, "..", "Animo_Tools_Editor", "animo_tools", "tools"))
    except NameError:
        version_script_dir = cmds.internalVar(userScriptDir=True)
        script_dir = os.path.normpath(os.path.join(version_script_dir, "..", "..", "scripts"))
        return os.path.join(script_dir, "Animo_Data", "Animo_Tools_Editor", "animo_tools", "tools")


def _ensure_smooth_plugin_loaded():
    global _smooth_plugin_checked, _smooth_plugin_loaded
    if _smooth_plugin_checked and _smooth_plugin_loaded:
        return True
    tools_path = _get_animo_tools_path()
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)
    is_loaded = False
    try:
        is_loaded = cmds.pluginInfo(SMOOTH_PLUGIN_NAME, query=True, loaded=True)
    except:
        is_loaded = False
    if is_loaded:
        _smooth_plugin_checked = True
        _smooth_plugin_loaded = True
        return True
    plugin_path = None
    for ext in (".py", ".pyc"):
        potential_path = os.path.join(tools_path, SMOOTH_PLUGIN_NAME + ext)
        if os.path.exists(potential_path):
            plugin_path = potential_path
            break
    _smooth_plugin_checked = True
    if plugin_path:
        try:
            cmds.loadPlugin(plugin_path)
            _smooth_plugin_loaded = True
            return True
        except:
            _smooth_plugin_loaded = False
            return False
    _smooth_plugin_loaded = False
    return False


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


def _setup_smooth_target_data():
    global shTweenData
    shTweenData = {}
    angle_unit, linear_unit = slider_utils.get_current_units()

    perCurveEntries = {}
    for n, curve in enumerate(shStoredAnimCurves):
        if not shStoredKeysSel[n]:
            continue
        mfn = shMfnCache.get(curve)
        if mfn is None:
            mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        shMfnCache[curve] = mfn
        reader = slider_utils.make_value_reader(mfn, angle_unit, linear_unit)
        setter = slider_utils.make_value_setter(mfn, angle_unit, linear_unit)
        numKeys = mfn.numKeys
        entries = []
        for key_time in shStoredKeysSel[n]:
            index = slider_utils.get_key_index_at_time(mfn, key_time)
            if index < 0:
                continue
            original_val = reader(index)
            prev_index = index - 1 if index > 0 else None
            next_index = index + 1 if index < numKeys - 1 else None
            prev_val = reader(prev_index) if prev_index is not None else None
            next_val = reader(next_index) if next_index is not None else None
            entries.append({
                "index": index,
                "original": original_val,
                "prev": prev_val,
                "next": next_val,
            })
        if entries:
            perCurveEntries[curve] = {"mfn": mfn, "reader": reader, "setter": setter, "entries": entries}

    if not perCurveEntries:
        return

    try:
        cmds.smoothKeysAPI(strength=SMOOTH_STRENGTH, iterations=SMOOTH_ITERATIONS)
    except:
        return

    for curve, data in perCurveEntries.items():
        reader = data["reader"]
        setter = data["setter"]
        for entry in data["entries"]:
            try:
                entry["target"] = reader(entry["index"])
            except:
                entry["target"] = entry["original"]
        for entry in data["entries"]:
            try:
                setter(entry["index"], entry["original"])
                cmds.keyframe(curve, edit=True, index=(entry["index"], entry["index"]), valueChange=entry["original"], absolute=True)
            except:
                continue
        shTweenData[curve] = {"reader": reader, "setter": setter, "entries": data["entries"]}


def _execute(value):
    if not shTweenData:
        return
    if value >= 0:
        dragStrength = value / 100.0
        if dragStrength > 1.0:
            dragStrength = 1.0
        for curve, data in shTweenData.items():
            if not cmds.objExists(curve):
                continue
            setter = data["setter"]
            for entry in data["entries"]:
                originalValue = entry["original"]
                prevValue = entry.get("prev")
                nextValue = entry.get("next")
                if prevValue is not None and nextValue is not None:
                    neighborAverage = (prevValue + nextValue) / 2.0
                elif prevValue is not None:
                    neighborAverage = prevValue
                elif nextValue is not None:
                    neighborAverage = nextValue
                else:
                    neighborAverage = originalValue
                delta = originalValue - neighborAverage
                newValue = originalValue + delta * dragStrength * HARSH_STRENGTH
                try:
                    setter(entry["index"], newValue)
                except:
                    continue
    else:
        dragStrength = (-value) / 100.0
        if dragStrength > 1.0:
            dragStrength = 1.0
        for curve, data in shTweenData.items():
            if not cmds.objExists(curve):
                continue
            setter = data["setter"]
            for entry in data["entries"]:
                originalValue = entry["original"]
                targetValue = entry.get("target", originalValue)
                newValue = originalValue + (targetValue - originalValue) * dragStrength
                try:
                    setter(entry["index"], newValue)
                except:
                    continue


def _commit():
    for curve, data in shTweenData.items():
        if not cmds.objExists(curve):
            continue
        reader = data["reader"]
        setter = data["setter"]
        for entry in data["entries"]:
            try:
                final_value = reader(entry["index"])
                setter(entry["index"], entry["original"])
                cmds.keyframe(curve, edit=True, index=(entry["index"], entry["index"]), valueChange=final_value, absolute=True)
            except:
                continue


def _gather_targets():
    global shStoredAnimCurves, shStoredKeysSel, shGetFrom, shMfnCache

    selected = cmds.ls(selection=True)
    if not selected:
        return False
    if not _ensure_smooth_plugin_loaded():
        return False

    getCurves = slider_utils.get_anim_curves()
    shStoredAnimCurves = getCurves[0] or []
    shGetFrom = getCurves[1]
    if not shStoredAnimCurves:
        shStoredAnimCurves = _resolve_channelbox_curves(selected)
        shGetFrom = "channelBox"
    if not shStoredAnimCurves:
        return False

    shMfnCache = slider_utils.get_mfn_anim_curves_bulk(shStoredAnimCurves)
    shStoredKeysSel = slider_utils.get_keys_sel(shStoredAnimCurves, shGetFrom, mfn_cache=shMfnCache)
    hasSelectedKeys = any(keyList for keyList in shStoredKeysSel if keyList)

    if not hasSelectedKeys:
        currentTime = cmds.currentTime(query=True)
        existingSet = set(cmds.ls(shStoredAnimCurves))
        pendingCurves = []
        for curve in shStoredAnimCurves:
            if curve not in existingSet:
                continue
            pendingCurves.append(curve)
        if pendingCurves:
            cmds.setKeyframe(pendingCurves, time=currentTime, insert=True)
            cmds.keyTangent(pendingCurves, time=(currentTime, currentTime), inTangentType="auto", outTangentType="auto")
        shStoredKeysSel = []
        for curve in shStoredAnimCurves:
            if curve in existingSet:
                shStoredKeysSel.append([currentTime])
            else:
                shStoredKeysSel.append([])

    _setup_smooth_target_data()
    return True


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global shPushClick

    status = "Smooth | Harsh: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and shPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not shPushClick:
        slider_utils.safe_undo_chunk_open("Smooth to Target")
        if not _gather_targets():
            slider_utils.safe_undo_chunk_close()
            return last_update_time, status
        shPushClick = True

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
    global shPushClick, shStoredAnimCurves, shStoredKeysSel, shMfnCache, shTweenData

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if shPushClick:
        cmds.refresh(suspend=True)
        try:
            _commit()
        finally:
            cmds.refresh(suspend=False)
        slider_utils.safe_undo_chunk_close()

    shPushClick = False
    shStoredAnimCurves = []
    shStoredKeysSel = []
    shMfnCache = {}
    shTweenData = {}