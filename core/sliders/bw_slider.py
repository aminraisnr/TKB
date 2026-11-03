import time
import math
import maya.cmds as cmds
import maya.api.OpenMaya as om2

from . import slider_utils

bwPushClick = False
bwObjects = []
bwTime = None
bwBaseMatrix = {}
bwPrevMatrix = {}
bwNextMatrix = {}
bwChannels = {}
bwBaseLocal = {}

_LOCAL_CHANNELS = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")

_CHANNEL_ALIASES = {
    "translateX": "tx", "translateY": "ty", "translateZ": "tz",
    "tx": "tx", "ty": "ty", "tz": "tz",
    "rotateX": "rx", "rotateY": "ry", "rotateZ": "rz",
    "rx": "rx", "ry": "ry", "rz": "rz",
    "scaleX": "sx", "scaleY": "sy", "scaleZ": "sz",
    "sx": "sx", "sy": "sy", "sz": "sz",
}


def _world_matrix(obj):
    return cmds.xform(obj, query=True, worldSpace=True, matrix=True)


def _world_matrix_at_time(obj, t):
    return cmds.getAttr(obj + ".worldMatrix[0]", time=t)


def _decompose(matrix):
    mmatrix = om2.MMatrix(matrix)
    xform = om2.MTransformationMatrix(mmatrix)
    translation = xform.translation(om2.MSpace.kWorld)
    rotation = xform.rotation(asQuaternion=True)
    scale = xform.scale(om2.MSpace.kWorld)
    return translation, rotation, scale


def _compose(translation, rotation, scale):
    xform = om2.MTransformationMatrix()
    xform.setTranslation(translation, om2.MSpace.kWorld)
    xform.setRotation(rotation)
    xform.setScale(scale, om2.MSpace.kWorld)
    return list(xform.asMatrix())


def _extrapolated_slerp(rotation_a, rotation_b, t):
    if abs(t) < 1e-9:
        return om2.MQuaternion(rotation_a)
    delta = rotation_a.inverse() * rotation_b
    delta.normalizeIt()
    w = max(-1.0, min(1.0, delta.w))
    angle = 2.0 * math.acos(w)
    if angle < 1e-9:
        return om2.MQuaternion(rotation_a)
    s = math.sin(angle / 2.0)
    if abs(s) < 1e-9:
        return om2.MQuaternion(rotation_a)
    axis = om2.MVector(delta.x / s, delta.y / s, delta.z / s)
    scaled_delta = om2.MQuaternion(angle * t, axis)
    return rotation_a * scaled_delta


def _blend_matrices(matrix_a, matrix_b, t):
    translation_a, rotation_a, scale_a = _decompose(matrix_a)
    translation_b, rotation_b, scale_b = _decompose(matrix_b)
    blended_translation = translation_a + (translation_b - translation_a) * t
    blended_rotation = _extrapolated_slerp(rotation_a, rotation_b, t)
    blended_scale = [scale_a[i] + (scale_b[i] - scale_a[i]) * t for i in range(3)]
    return _compose(blended_translation, blended_rotation, blended_scale)


def _neighbor_key_times(obj, current_time):
    key_times = cmds.keyframe(obj, query=True)
    if not key_times:
        return None, None
    key_times = sorted(set(key_times))
    prev_time = None
    next_time = None
    for kt in key_times:
        if kt < current_time - 0.0001:
            prev_time = kt
        elif kt > current_time + 0.0001 and next_time is None:
            next_time = kt
    return prev_time, next_time


def _resolve_targets():
    anim_curves, get_from = slider_utils.get_anim_curves()
    channels_map = {}

    if get_from in ("graphEditor", "channelBox") and anim_curves:
        for curve in anim_curves:
            connections = cmds.listConnections(curve, destination=True, source=False, plugs=True) or []
            for plug in connections:
                node, attr = plug.split(".", 1)
                short = _CHANNEL_ALIASES.get(attr)
                if short is None:
                    continue
                long_names = cmds.ls(node, long=True) or []
                for long_name in long_names:
                    channels_map.setdefault(long_name, set()).add(short)

    if channels_map:
        return list(channels_map.keys()), channels_map

    return cmds.ls(selection=True, long=True) or [], {}


def _gather_targets():
    global bwObjects, bwTime, bwBaseMatrix, bwPrevMatrix, bwNextMatrix, bwChannels, bwBaseLocal

    selection, channels_map = _resolve_targets()
    if not selection:
        return False

    current_time = cmds.currentTime(query=True)
    bwObjects = selection
    bwTime = current_time
    bwBaseMatrix = {}
    bwPrevMatrix = {}
    bwNextMatrix = {}
    bwChannels = channels_map
    bwBaseLocal = {}

    for obj in selection:
        bwBaseMatrix[obj] = _world_matrix(obj)
        prev_time, next_time = _neighbor_key_times(obj, current_time)
        bwPrevMatrix[obj] = _world_matrix_at_time(obj, prev_time) if prev_time is not None else None
        bwNextMatrix[obj] = _world_matrix_at_time(obj, next_time) if next_time is not None else None
        if obj in bwChannels:
            local_values = {}
            for attr in _LOCAL_CHANNELS:
                try:
                    local_values[attr] = cmds.getAttr(obj + "." + attr)
                except:
                    continue
            bwBaseLocal[obj] = local_values

    return True


def _apply(value):
    if value >= 0:
        t = slider_utils.ease_value(value / 100.0)
        target_map = bwNextMatrix
    else:
        t = slider_utils.ease_value(-value / 100.0)
        target_map = bwPrevMatrix

    for obj in bwObjects:
        target = target_map.get(obj)
        if target is None:
            continue
        base = bwBaseMatrix.get(obj)
        if base is None:
            continue
        try:
            blended = _blend_matrices(base, target, t)
            cmds.xform(obj, worldSpace=True, matrix=blended)
        except:
            continue

        selected_channels = bwChannels.get(obj)
        if selected_channels:
            local_values = bwBaseLocal.get(obj, {})
            for attr in _LOCAL_CHANNELS:
                if attr in selected_channels:
                    continue
                if attr not in local_values:
                    continue
                try:
                    cmds.setAttr(obj + "." + attr, local_values[attr])
                except:
                    continue


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global bwPushClick

    status = "Blend to World: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    is_extreme = abs(value) >= 100
    if not is_extreme and current_time - last_update_time < update_throttle_ms and bwPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not bwPushClick:
        if not _gather_targets():
            return last_update_time, status
        bwPushClick = True
        slider_utils.safe_undo_chunk_open("Blend to World")

    cmds.refresh(suspend=True)
    try:
        _apply(value)
    finally:
        cmds.refresh(suspend=False)

    return last_update_time, status


def reset_slider(slider_widget):
    global bwPushClick, bwObjects, bwTime, bwBaseMatrix, bwPrevMatrix, bwNextMatrix, bwChannels, bwBaseLocal

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if bwPushClick:
        for obj in bwObjects:
            selected_channels = bwChannels.get(obj)
            if selected_channels:
                attrs = tuple(c for c in ("tx", "ty", "tz", "rx", "ry", "rz") if c in selected_channels)
            else:
                attrs = ("tx", "ty", "tz", "rx", "ry", "rz")
            if not attrs:
                continue
            try:
                cmds.setKeyframe(obj, attribute=attrs, time=(bwTime,))
            except:
                continue
        slider_utils.safe_undo_chunk_close()

    bwPushClick = False
    bwObjects = []
    bwTime = None
    bwBaseMatrix = {}
    bwPrevMatrix = {}
    bwNextMatrix = {}
    bwChannels = {}
    bwBaseLocal = {}