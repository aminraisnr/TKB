import time
import maya.cmds as cmds
import maya.api.OpenMaya as om2
from maya import mel

from . import slider_utils

ppPushClick = False
ppMode = None
ppObjectsData = {}
ppCurveSegments = []
ppMfnCache = {}
ppSetters = {}
ppReaders = {}
ppFastMode = False
ppLastP = 1.0


def _round_t(t):
    return round(t, 5)


def _get_selected_key_times(obj):
    times = cmds.keyframe(obj, query=True, selected=True, timeChange=True)
    if not times:
        return []
    return sorted(set(times))


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


def _curves_for_object(node, channel_attrs):
    attrs = channel_attrs if channel_attrs else _keyable_attrs(node)
    curves = []
    for attr in attrs:
        plug = node + "." + attr
        if not cmds.objExists(plug):
            continue
        curve = _resolve_curve(plug)
        if curve and curve not in curves:
            curves.append(curve)
    return curves


def _auto_curves_for_selection(selection):
    channel_attrs = _channelbox_attrs()

    all_curves = []
    for obj in selection:
        for curve in _curves_for_object(obj, channel_attrs):
            if curve not in all_curves:
                all_curves.append(curve)

    return all_curves


def _ensure_current_time_keys(curves, current_time):
    for curve in curves:
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


def _get_all_key_times(obj):
    times = cmds.keyframe(obj, query=True, timeChange=True)
    if not times:
        return []
    return sorted(set(times))


def _get_timeline_range():
    try:
        playback_slider = mel.eval('$tmp=$gPlayBackSlider')
        time_range = cmds.timeControl(playback_slider, query=True, rangeArray=True)
    except:
        return None
    start = int(time_range[0])
    end = int(time_range[1]) - 1
    if end > start:
        return start, end
    return None


def _build_curve_push_pull_segments(curve, selected_times):
    times = cmds.keyframe(curve, query=True, timeChange=True) or []
    values = cmds.keyframe(curve, query=True, valueChange=True) or []
    n = len(times)
    if n == 0:
        return None

    index_of = {}
    for i, t in enumerate(times):
        index_of[_round_t(t)] = i

    runs = []
    current_run = []
    for t in selected_times:
        rt = _round_t(t)
        if rt not in index_of:
            continue
        idx = index_of[rt]
        if current_run and idx == current_run[-1] + 1:
            current_run.append(idx)
        else:
            if current_run:
                runs.append(current_run)
            current_run = [idx]
    if current_run:
        runs.append(current_run)

    if not runs:
        return None

    segments = []
    for run in runs:
        first_idx = run[0]
        last_idx = run[-1]

        if first_idx > 0:
            bf_time = times[first_idx - 1]
            bf_value = values[first_idx - 1]
        elif n >= 2:
            bf_time = times[0] - (times[1] - times[0])
            bf_value = values[0] - (values[1] - values[0])
        else:
            bf_time = times[0] - 1.0
            bf_value = values[0]

        if last_idx < n - 1:
            bl_time = times[last_idx + 1]
            bl_value = values[last_idx + 1]
        elif n >= 2:
            bl_time = times[n - 1] + (times[n - 1] - times[n - 2])
            bl_value = values[n - 1] + (values[n - 1] - values[n - 2])
        else:
            bl_time = times[n - 1] + 1.0
            bl_value = values[n - 1]

        if bl_time == bf_time:
            continue

        has_real_boundary = (first_idx > 0) or (last_idx < n - 1)

        segments.append({
            "indexes": run,
            "boundaryFirstTime": bf_time,
            "boundaryFirstValue": bf_value,
            "boundaryLastTime": bl_time,
            "boundaryLastValue": bl_value,
            "hasRealBoundary": has_real_boundary,
        })

    if not segments:
        return None

    return {"times": times, "values": values, "segments": segments}


def _gather_curve_targets(curves=None, current_time=None):
    global ppCurveSegments, ppMfnCache, ppSetters, ppReaders
    ppCurveSegments = []
    ppMfnCache = {}
    ppSetters = {}
    ppReaders = {}

    unit_angle, unit_linear = slider_utils.get_current_units()

    if curves is None:
        curves = cmds.keyframe(query=True, selected=True, name=True) or []
    for curve in curves:
        if current_time is None:
            selected_times = _get_selected_key_times(curve)
        else:
            selected_times = [current_time]
        if not selected_times:
            continue

        curve_data = _build_curve_push_pull_segments(curve, selected_times)
        if not curve_data:
            continue

        mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        ppMfnCache[curve] = mfn
        ppSetters[curve] = slider_utils.make_value_setter(mfn, unit_angle, unit_linear)
        ppReaders[curve] = slider_utils.make_value_reader(mfn, unit_angle, unit_linear)

        times = curve_data["times"]
        values = curve_data["values"]
        n = len(times)
        keys = []

        for segment in curve_data["segments"]:
            bf_time = segment["boundaryFirstTime"]
            bf_value = segment["boundaryFirstValue"]
            bl_time = segment["boundaryLastTime"]
            bl_value = segment["boundaryLastValue"]
            total_time = bl_time - bf_time

            run = segment["indexes"]
            raw_line_values = [
                ((bl_value - bf_value) / total_time) * (times[idx] - bf_time) + bf_value
                for idx in run
            ]

            if segment["hasRealBoundary"]:
                balance_offset = 0.0
            else:
                avg_original = sum(values[idx] for idx in run) / len(run)
                avg_raw_line = sum(raw_line_values) / len(run)
                balance_offset = avg_original - avg_raw_line

            for i, idx in enumerate(run):
                pivot = raw_line_values[i] + balance_offset
                keys.append((idx, pivot, values[idx], times[idx]))

        if keys:
            ppCurveSegments.append({"curve": curve, "keys": keys})

    return bool(ppCurveSegments)


def _apply_curve(p):
    for entry in ppCurveSegments:
        curve = entry["curve"]
        if not cmds.objExists(curve):
            continue
        setter = ppSetters.get(curve)
        if setter is None:
            continue
        for idx, pivot, orig_v, t in entry["keys"]:
            new_v = pivot + (orig_v - pivot) * p
            try:
                setter(idx, new_v)
            except:
                continue


def _apply_curve_graph_editor(p):
    global ppLastP
    if p == 0:
        p = 0.0000001
    if ppLastP != 0:
        relative_p = p / ppLastP
    else:
        relative_p = p
    for entry in ppCurveSegments:
        curve = entry["curve"]
        if not cmds.objExists(curve):
            continue
        for idx, pivot, orig_v, t in entry["keys"]:
            try:
                cmds.scaleKey(curve, index=(idx, idx), valuePivot=pivot, valueScale=relative_p)
            except:
                new_v = pivot + (orig_v - pivot) * p
                try:
                    cmds.keyframe(curve, index=(idx, idx), valueChange=new_v, absolute=True)
                except:
                    continue
    ppLastP = p


def _commit_curve():
    for entry in ppCurveSegments:
        curve = entry["curve"]
        if not cmds.objExists(curve):
            continue
        setter = ppSetters.get(curve)
        reader = ppReaders.get(curve)
        if setter is None or reader is None:
            continue
        for idx, pivot, orig_v, t in entry["keys"]:
            try:
                final_v = reader(idx)
                setter(idx, orig_v)
                cmds.keyframe(curve, index=(idx, idx), valueChange=final_v, absolute=True)
            except:
                continue


def _get_neighbor_key_times(obj, current_time):
    all_times = _get_all_key_times(obj)
    prev_time = None
    next_time = None
    for t in all_times:
        if t < current_time - 0.0001:
            prev_time = t
        elif t > current_time + 0.0001 and next_time is None:
            next_time = t
    return prev_time, next_time


def _build_segments_from_current_time(obj, current_time):
    prev_time, next_time = _get_neighbor_key_times(obj, current_time)
    if prev_time is None or next_time is None:
        return []
    return [{
        "firstFrame": prev_time,
        "lastFrame": next_time,
        "interiorTimes": [current_time],
    }]


def _build_segments_from_timeline(obj, start_frame, end_frame):
    key_times = cmds.keyframe(obj, query=True, time=(start_frame, end_frame))
    if not key_times:
        return []
    key_times = sorted(set(key_times))
    if len(key_times) < 3:
        return []
    return [{
        "firstFrame": key_times[0],
        "lastFrame": key_times[-1],
        "interiorTimes": key_times[1:-1],
    }]


def _get_rotate_order(obj):
    return cmds.getAttr(obj + ".rotateOrder")


def _decompose_world(obj, t, rotate_order):
    world_matrix = cmds.getAttr(obj + ".worldMatrix[0]", time=t)
    mmatrix = om2.MMatrix(world_matrix)
    xform = om2.MTransformationMatrix(mmatrix)
    translation = xform.translation(om2.MSpace.kWorld)
    euler = xform.rotation(asQuaternion=True).asEulerRotation()
    euler.reorderIt(rotate_order)
    rotation = [
        om2.MAngle(euler.x).asDegrees(),
        om2.MAngle(euler.y).asDegrees(),
        om2.MAngle(euler.z).asDegrees(),
    ]
    return [translation.x, translation.y, translation.z], rotation


def _compose_world_matrix(translation, rotation, rotate_order):
    radians = [om2.MAngle(v, om2.MAngle.kDegrees).asRadians() for v in rotation]
    euler = om2.MEulerRotation(radians[0], radians[1], radians[2], rotate_order)
    xform = om2.MTransformationMatrix()
    xform.setTranslation(om2.MVector(translation), om2.MSpace.kWorld)
    xform.setRotation(euler.asQuaternion())
    return xform.asMatrix()


def _world_to_local(obj, world_matrix, t):
    parent_inverse = cmds.getAttr(obj + ".parentInverseMatrix[0]", time=t)
    parent_inverse_matrix = om2.MMatrix(parent_inverse)
    return world_matrix * parent_inverse_matrix


def _decompose_local(local_matrix, rotate_order):
    xform = om2.MTransformationMatrix(local_matrix)
    translation = xform.translation(om2.MSpace.kTransform)
    euler = xform.rotation(asQuaternion=True).asEulerRotation()
    euler.reorderIt(rotate_order)
    rotation = [
        om2.MAngle(euler.x).asDegrees(),
        om2.MAngle(euler.y).asDegrees(),
        om2.MAngle(euler.z).asDegrees(),
    ]
    return [translation.x, translation.y, translation.z], rotation


def _gather_targets():
    global ppMode, ppObjectsData, ppFastMode, ppLastP

    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        return False

    ppFastMode = False
    ppLastP = 1.0

    use_graph_editor = any(_get_selected_key_times(obj) for obj in selection)

    if use_graph_editor:
        if _gather_curve_targets():
            ppMode = "curve"
            return True
        return False

    current_time = cmds.currentTime(query=True)
    curves = _auto_curves_for_selection(selection)
    if curves:
        _ensure_current_time_keys(curves, current_time)
        if _gather_curve_targets(curves=curves, current_time=current_time):
            ppMode = "curve"
            ppFastMode = True
            return True

    ppObjectsData = {}

    raw_segments = {}
    time_range = _get_timeline_range()
    if time_range:
        start_frame, end_frame = time_range
        for obj in selection:
            segments = _build_segments_from_timeline(obj, start_frame, end_frame)
            if segments:
                raw_segments[obj] = segments
    else:
        current_time = cmds.currentTime(query=True)
        for obj in selection:
            segments = _build_segments_from_current_time(obj, current_time)
            if segments:
                raw_segments[obj] = segments

    if not raw_segments:
        return False

    objects_data = {}

    for obj, segments in raw_segments.items():
        rotate_order = _get_rotate_order(obj)
        resolved_segments = []

        for segment in segments:
            first_frame = segment["firstFrame"]
            last_frame = segment["lastFrame"]
            total_frames = last_frame - first_frame
            if total_frames == 0:
                continue

            first_translate, first_rotate = _decompose_world(obj, first_frame, rotate_order)
            last_translate, last_rotate = _decompose_world(obj, last_frame, rotate_order)

            interior_keys = []
            for frame in segment["interiorTimes"]:
                translate, rotate = _decompose_world(obj, frame, rotate_order)
                interior_keys.append({"time": frame, "translate": translate, "rotate": rotate})

            if not interior_keys:
                continue

            resolved_segments.append({
                "firstFrame": first_frame,
                "lastFrame": last_frame,
                "totalFrames": total_frames,
                "firstTranslate": first_translate,
                "firstRotate": first_rotate,
                "lastTranslate": last_translate,
                "lastRotate": last_rotate,
                "keys": interior_keys,
            })

        if resolved_segments:
            objects_data[obj] = {"rotateOrder": rotate_order, "segments": resolved_segments}

    if not objects_data:
        return False

    ppMode = "object"
    ppObjectsData = objects_data
    return True


def _apply_object(value):
    p = slider_utils.centered_ease(value)

    for obj, data in ppObjectsData.items():
        rotate_order = data["rotateOrder"]

        for segment in data["segments"]:
            first_frame = segment["firstFrame"]
            total_frames = segment["totalFrames"]
            first_translate = segment["firstTranslate"]
            first_rotate = segment["firstRotate"]
            last_translate = segment["lastTranslate"]
            last_rotate = segment["lastRotate"]

            delta_translate = [last_translate[i] - first_translate[i] for i in range(3)]
            delta_rotate = [last_rotate[i] - first_rotate[i] for i in range(3)]

            for key_data in segment["keys"]:
                frame = key_data["time"]
                current_translate = key_data["translate"]
                current_rotate = key_data["rotate"]

                linear_translate = [
                    ((delta_translate[i] / total_frames) * (frame - first_frame)) + first_translate[i]
                    for i in range(3)
                ]
                linear_rotate = [
                    ((delta_rotate[i] / total_frames) * (frame - first_frame)) + first_rotate[i]
                    for i in range(3)
                ]

                new_translate = [
                    ((current_translate[i] - linear_translate[i]) * p) + linear_translate[i]
                    for i in range(3)
                ]
                new_rotate = [
                    ((current_rotate[i] - linear_rotate[i]) * p) + linear_rotate[i]
                    for i in range(3)
                ]

                try:
                    world_matrix = _compose_world_matrix(new_translate, new_rotate, rotate_order)
                    local_matrix = _world_to_local(obj, world_matrix, frame)
                    local_translate, local_rotate = _decompose_local(local_matrix, rotate_order)

                    cmds.setKeyframe(obj, attribute="translateX", time=(frame, frame), value=local_translate[0])
                    cmds.setKeyframe(obj, attribute="translateY", time=(frame, frame), value=local_translate[1])
                    cmds.setKeyframe(obj, attribute="translateZ", time=(frame, frame), value=local_translate[2])
                    cmds.setKeyframe(obj, attribute="rotateX", time=(frame, frame), value=local_rotate[0])
                    cmds.setKeyframe(obj, attribute="rotateY", time=(frame, frame), value=local_rotate[1])
                    cmds.setKeyframe(obj, attribute="rotateZ", time=(frame, frame), value=local_rotate[2])
                except:
                    continue


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global ppPushClick

    status = "Push / Pull: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and ppPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not ppPushClick:
        slider_utils.safe_undo_chunk_open("Push And Pull")
        if not _gather_targets():
            slider_utils.safe_undo_chunk_close()
            return last_update_time, "Push / Pull: no neighboring keys found"
        ppPushClick = True

    p = slider_utils.centered_ease(value)

    cmds.refresh(suspend=True)
    try:
        if ppMode == "curve":
            if ppFastMode:
                _apply_curve(p)
            else:
                _apply_curve_graph_editor(p)
        else:
            _apply_object(value)
    finally:
        cmds.refresh(suspend=False)

    return last_update_time, status


def reset_slider(slider_widget):
    global ppPushClick, ppMode, ppObjectsData, ppCurveSegments, ppMfnCache, ppSetters, ppReaders, ppFastMode, ppLastP

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if ppPushClick:
        if ppMode == "curve" and ppFastMode:
            cmds.refresh(suspend=True)
            try:
                _commit_curve()
            finally:
                cmds.refresh(suspend=False)

        slider_utils.safe_undo_chunk_close()

    ppPushClick = False
    ppMode = None
    ppObjectsData = {}
    ppCurveSegments = []
    ppMfnCache = {}
    ppSetters = {}
    ppReaders = {}
    ppFastMode = False
    ppLastP = 1.0