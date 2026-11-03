import maya.cmds as cmds
import os
import json


NUDGE_PREFS_FILE_NAME = "nudge_keys_prefs.json"
DEFAULT_NUDGE_AMOUNT = 1.0


def _prefs_file(prefs_path):
    return os.path.join(prefs_path, NUDGE_PREFS_FILE_NAME)


def load_last_amount(prefs_path):
    prefs_file = _prefs_file(prefs_path)
    try:
        with open(prefs_file, "r") as f:
            data = json.load(f)
        amount = float(data.get("amount", DEFAULT_NUDGE_AMOUNT))
        if amount <= 0:
            return DEFAULT_NUDGE_AMOUNT
        return amount
    except:
        return DEFAULT_NUDGE_AMOUNT


def save_last_amount(prefs_path, amount):
    prefs_file = _prefs_file(prefs_path)
    try:
        with open(prefs_file, "w") as f:
            json.dump({"amount": amount}, f)
    except:
        pass


def _show_message(message):
    try:
        cmds.inViewMessage(
            amg=message,
            pos="midCenter",
            fade=True,
            fadeStayTime=2000,
            fadeOutTime=500
        )
    except:
        pass


def _get_channelbox_attributes():
    channel_box = "mainChannelBox"
    attrs = []
    for flag in ("sma", "ssa", "sha", "soa"):
        try:
            result = cmds.channelBox(
                channel_box,
                q=True,
                **{flag: True}
            )
            if result:
                attrs.extend(result)
        except:
            pass
    return list(set(attrs))


def get_graph_editor_selected_keys():
    curves = cmds.keyframe(
        q=True,
        selected=True,
        name=True
    ) or []
    result = []
    for curve in set(curves):
        times = cmds.keyframe(
            curve,
            q=True,
            selected=True,
            timeChange=True
        ) or []
        for time in times:
            result.append((curve, time))
    return result


def _has_collision(curve, source_time, target_time, moving_times):
    tolerance = 0.0001
    existing_times = cmds.keyframe(
        curve,
        q=True,
        time=(target_time, target_time),
        timeChange=True
    ) or []
    for existing_time in existing_times:
        if abs(existing_time - target_time) < tolerance:
            if not any(
                abs(existing_time - moving_time) < tolerance
                for moving_time in moving_times
            ):
                return True
    return False


def shift_graph_editor_keys(amount):
    selected_keys = get_graph_editor_selected_keys()
    if not selected_keys:
        return False
    curve_keys = {}
    for curve, time in selected_keys:
        curve_keys.setdefault(curve, []).append(time)
    for curve, times in curve_keys.items():
        for time in times:
            target_time = time + amount
            if _has_collision(
                curve,
                time,
                target_time,
                times
            ):
                _show_message(
                    "Cannot shift keys: another key is in the way."
                )
                return False
    for curve, times in curve_keys.items():
        time_ranges = [(time, time) for time in times]
        try:
            cmds.keyframe(
                curve,
                e=True,
                time=time_ranges,
                relative=True,
                timeChange=amount
            )
        except:
            _show_message(
                "Cannot move keys: blocked by another keyframe."
            )
            return False
    return True


def get_timeline_range():
    try:
        slider = cmds.timeControl(
            "timeControl1",
            q=True,
            rangeArray=True
        )
        if slider and slider[1] > slider[0]:
            return slider[0], slider[1] - 1
    except:
        pass
    return (
        cmds.playbackOptions(q=True, min=True),
        cmds.playbackOptions(q=True, max=True)
    )


def get_animation_curves():
    curves = []
    objects = cmds.ls(selection=True) or []
    if not objects:
        return []
    attrs = _get_channelbox_attributes()
    if attrs:
        for obj in objects:
            for attr in attrs:
                plug = "{}.{}".format(obj, attr)
                if not cmds.objExists(plug):
                    continue
                connected = cmds.listConnections(
                    plug,
                    type="animCurve"
                ) or []
                curves.extend(connected)
    else:
        connected = cmds.listConnections(
            objects,
            type="animCurve"
        ) or []
        curves.extend(connected)
    return list(set(curves))


def get_timeline_keys():
    start, end = get_timeline_range()
    curves = get_animation_curves()
    result = {}
    for curve in curves:
        times = cmds.keyframe(
            curve,
            q=True,
            time=(start, end),
            timeChange=True
        ) or []
        if times:
            result[curve] = times
    return result


def shift_timeline_keys(amount):
    curve_keys = get_timeline_keys()
    if not curve_keys:
        _show_message("No keys found in the selected range.")
        return False
    for curve, times in curve_keys.items():
        for time in times:
            target_time = time + amount
            if _has_collision(
                curve,
                time,
                target_time,
                times
            ):
                _show_message(
                    "Cannot shift keys: another key is in the way."
                )
                return False
    for curve, times in curve_keys.items():
        time_ranges = [(time, time) for time in times]
        try:
            cmds.keyframe(
                curve,
                e=True,
                time=time_ranges,
                relative=True,
                timeChange=amount
            )
        except:
            _show_message(
                "Cannot move keys: blocked by another keyframe."
            )
            return False
    return True


def nudge_keys_by_amount(amount):
    if amount == 0:
        return
    cmds.waitCursor(state=True)
    cmds.undoInfo(openChunk=True)
    try:
        current_time = cmds.currentTime(q=True)
        graph_keys = get_graph_editor_selected_keys()
        if graph_keys:
            shift_graph_editor_keys(amount)
            cmds.refresh()
            return
        curves = get_animation_curves()
        if not curves:
            _show_message("No animation curves found.")
            return
        current_time_is_key = False
        for curve in curves:
            keys = cmds.keyframe(
                curve,
                q=True,
                time=(current_time, current_time),
                timeChange=True
            ) or []
            if keys:
                current_time_is_key = True
                break
        moved = shift_timeline_keys(amount)
        if moved and current_time_is_key:
            cmds.currentTime(
                current_time + amount,
                edit=True
            )
        cmds.refresh()
    finally:
        cmds.undoInfo(closeChunk=True)
        cmds.waitCursor(state=False)