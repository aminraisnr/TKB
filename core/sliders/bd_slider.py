import time
import maya.cmds as cmds
import maya.utils
from maya import mel

from . import slider_utils

bdPushClick = False
bdActive = []
bdMfnCache = {}
bdSetters = {}
bdReaders = {}
bdOriginal = {}
bdDefault = {}


def _keyable_attrs(node):
    return cmds.listAttr(node, keyable=True, unlocked=True) or []


def _default_value(node, attr):
    try:
        vals = cmds.attributeQuery(attr, node=node, listDefault=True)
        if vals:
            return vals[0]
    except:
        pass
    return 0.0


def _resolve_curve(plug):
    conns = cmds.listConnections(plug, source=True, destination=False) or []
    for c in conns:
        if cmds.nodeType(c).startswith("animCurve"):
            return c
    return None


def _channelbox_attrs():
    try:
        channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        return cmds.channelBox(channel_box, query=True, selectedMainAttributes=True) or []
    except:
        return []


def _register_key_target(curve, idx, node, attr, unit_angle, unit_linear):
    mfn = bdMfnCache.get(curve)
    if mfn is None:
        mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            return False
        bdMfnCache[curve] = mfn
    setter = slider_utils.make_value_setter(mfn, unit_angle, unit_linear)
    reader = slider_utils.make_value_reader(mfn, unit_angle, unit_linear)
    bdSetters[curve] = setter
    bdReaders[curve] = reader
    key = (curve, idx)
    bdOriginal[key] = reader(idx)
    bdDefault[key] = _default_value(node, attr)
    bdActive.append(("key", curve, idx))
    return True


def _gather_targets():
    global bdActive, bdMfnCache, bdSetters, bdReaders, bdOriginal, bdDefault
    bdActive = []
    bdMfnCache = {}
    bdSetters = {}
    bdReaders = {}
    bdOriginal = {}
    bdDefault = {}

    unit_angle, unit_linear = slider_utils.get_current_units()

    anim_curves, get_from = slider_utils.get_anim_curves()

    if get_from == "graphEditor" and anim_curves:
        keys_sel = slider_utils.get_keys_sel(anim_curves, get_from)
        for curve, times in zip(anim_curves, keys_sel):
            if not times:
                continue
            mfn = slider_utils.get_mfn_anim_curve(curve)
            if mfn is None:
                continue
            bdMfnCache[curve] = mfn
            conns = cmds.listConnections(curve + ".output", plugs=True) or []
            node, attr = (conns[0].split(".", 1) if conns else (None, None))
            for t in times:
                idx = slider_utils.get_key_index_at_time(mfn, t)
                if idx >= 0 and node:
                    _register_key_target(curve, idx, node, attr, unit_angle, unit_linear)
        return bool(bdActive)

    selected = cmds.ls(selection=True) or []
    if not selected:
        return False

    channel_attrs = _channelbox_attrs()
    current_time = cmds.currentTime(query=True)

    for node in selected:
        attrs = channel_attrs if channel_attrs else _keyable_attrs(node)
        for attr in attrs:
            plug = node + "." + attr
            if not cmds.objExists(plug):
                continue
            try:
                if not cmds.getAttr(plug, settable=True):
                    continue
                orig_val = cmds.getAttr(plug)
            except:
                continue
            if isinstance(orig_val, list):
                continue

            curve = _resolve_curve(plug)
            if curve:
                mfn = slider_utils.get_mfn_anim_curve(curve)
                if mfn is None:
                    continue
                idx = slider_utils.get_key_index_at_time(mfn, current_time)
                if idx < 0:
                    try:
                        cmds.setKeyframe(plug, time=(current_time,))
                    except:
                        continue
                    curve = _resolve_curve(plug)
                    mfn = slider_utils.get_mfn_anim_curve(curve) if curve else None
                    if mfn is None:
                        continue
                    idx = slider_utils.get_key_index_at_time(mfn, current_time)
                    if idx < 0:
                        continue
                bdMfnCache[curve] = mfn
                _register_key_target(curve, idx, node, attr, unit_angle, unit_linear)
            else:
                key = ("attr", plug)
                bdOriginal[key] = orig_val
                bdDefault[key] = _default_value(node, attr)
                bdActive.append(("attr", plug, None))

    return bool(bdActive)


def _target_value(orig, default, position):
    if position >= 0:
        t = position
        return orig + (default - orig) * t
    push = -position
    return orig + (orig - default) * push


def _apply(position):
    position = slider_utils.ease_value(position)
    for kind, ident, idx in bdActive:
        if kind == "key":
            key = (ident, idx)
            orig = bdOriginal.get(key)
            if orig is None:
                continue
            new_val = _target_value(orig, bdDefault.get(key, 0.0), position)
            setter = bdSetters.get(ident)
            if setter:
                try:
                    setter(idx, new_val)
                except:
                    continue
        else:
            key = ("attr", ident)
            orig = bdOriginal.get(key)
            if orig is None:
                continue
            new_val = _target_value(orig, bdDefault.get(key, 0.0), position)
            try:
                cmds.setAttr(ident, new_val)
            except:
                continue


def _commit():
    for kind, ident, idx in bdActive:
        if kind != "key":
            continue
        key = (ident, idx)
        orig = bdOriginal.get(key)
        if orig is None:
            continue
        reader = bdReaders.get(ident)
        setter = bdSetters.get(ident)
        if reader is None or setter is None:
            continue
        try:
            final_val = reader(idx)
            setter(idx, orig)
            cmds.keyframe(ident, edit=True, index=(idx, idx), valueChange=final_val, absolute=True)
        except:
            continue


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global bdPushClick

    status = "Blend to Default: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and bdPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not bdPushClick:
        slider_utils.safe_undo_chunk_open("Blend to Default")
        if not _gather_targets():
            slider_utils.safe_undo_chunk_close()
            return last_update_time, status
        bdPushClick = True

    cmds.refresh(suspend=True)
    try:
        _apply(value / 100.0)
    finally:
        cmds.refresh(suspend=False)
        if slider_utils.IS_MACOS:
            cmds.refresh()
            maya.utils.processIdleEvents()

    return last_update_time, status


def reset_slider(slider_widget):
    global bdPushClick, bdActive, bdMfnCache, bdSetters, bdReaders, bdOriginal, bdDefault

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if bdPushClick:
        cmds.refresh(suspend=True)
        try:
            _commit()
        finally:
            cmds.refresh(suspend=False)
        slider_utils.safe_undo_chunk_close()

    bdPushClick = False
    bdActive = []
    bdMfnCache = {}
    bdSetters = {}
    bdReaders = {}
    bdOriginal = {}
    bdDefault = {}