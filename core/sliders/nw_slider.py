import random
import math
import time
import maya.cmds as cmds

from . import slider_utils

WAVE_AMPLITUDE = 1.0
WAVE_FREQUENCY = 0.5
NOISE_AMPLITUDE = 1.0
NOISE_SEED = None
NW_EASE_STRENGTH = 6.0
NW_REPEAT_GROWTH = 3.0
NW_REPEAT_MAX_MULT = 50.0

nwPushClick = False
nwStoredAnimCurves = []
nwStoredKeysSel = []
nwGetFrom = "graphEditor"

nwMfnCache = {}
nwKeyTimesCache = {}

nwStoredSetters = {}
nwStoredReaders = {}
nwStoredRealIndexes = {}
nwStoredOriginalValues = {}
nwStoredWaveOffsets = {}
nwStoredNoiseOffsets = {}
nwStoredRepeatMult = {}

NW_USAGE_ATTR = "nwUsageCount"


def _get_usage_count(curve):
    if cmds.attributeQuery(NW_USAGE_ATTR, node=curve, exists=True):
        try:
            return cmds.getAttr(curve + "." + NW_USAGE_ATTR)
        except:
            return 0
    return 0


def _bump_usage_count(curve):
    if not cmds.attributeQuery(NW_USAGE_ATTR, node=curve, exists=True):
        try:
            cmds.addAttr(curve, longName=NW_USAGE_ATTR, attributeType="long", defaultValue=0, keyable=False)
        except:
            return
    current = _get_usage_count(curve)
    try:
        cmds.setAttr(curve + "." + NW_USAGE_ATTR, current + 1)
    except:
        pass


def _repeat_multiplier(curve):
    count = _get_usage_count(curve)
    return min(NW_REPEAT_GROWTH ** count, NW_REPEAT_MAX_MULT)


def _setup_data():
    global nwStoredSetters, nwStoredReaders
    global nwStoredRealIndexes, nwStoredOriginalValues
    global nwStoredWaveOffsets, nwStoredNoiseOffsets, nwStoredRepeatMult

    nwStoredSetters = {}
    nwStoredReaders = {}
    nwStoredRealIndexes = {}
    nwStoredOriginalValues = {}
    nwStoredWaveOffsets = {}
    nwStoredNoiseOffsets = {}
    nwStoredRepeatMult = {}

    unit_angle, unit_linear = slider_utils.get_current_units()
    rng = random.Random(NOISE_SEED)

    for n, curve in enumerate(nwStoredAnimCurves):
        sel_times = nwStoredKeysSel[n] if n < len(nwStoredKeysSel) else []
        if not sel_times:
            continue

        mfn = nwMfnCache.get(curve)
        if mfn is None:
            mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue

        reader = slider_utils.make_value_reader(mfn, unit_angle, unit_linear)
        setter = slider_utils.make_value_setter(mfn, unit_angle, unit_linear)
        nwStoredReaders[curve] = reader
        nwStoredSetters[curve] = setter

        key_times = nwKeyTimesCache.get(curve)
        if key_times is None:
            key_times = slider_utils.get_all_key_times(mfn)
        if not key_times:
            continue

        real_indexes = []
        sorted_sel = sorted(sel_times)
        si = 0
        for i, t in enumerate(key_times):
            if si < len(sorted_sel) and abs(sorted_sel[si] - t) < 0.001:
                real_indexes.append(i)
                si += 1
        if not real_indexes:
            continue

        nwStoredRealIndexes[curve] = real_indexes
        nwStoredOriginalValues[curve] = {idx: reader(idx) for idx in real_indexes}

        wave_offsets = {}
        noise_offsets = {}
        for i, idx in enumerate(real_indexes):
            wave_offsets[idx] = math.cos(2.0 * math.pi * WAVE_FREQUENCY * i)
            noise_offsets[idx] = rng.uniform(-1.0, 1.0)
        nwStoredWaveOffsets[curve] = wave_offsets
        nwStoredNoiseOffsets[curve] = noise_offsets
        nwStoredRepeatMult[curve] = _repeat_multiplier(curve)


def _apply(slider_val):
    if not nwStoredAnimCurves:
        return

    if slider_val >= 0:
        frac = slider_utils.ease_exponential(slider_val / 100.0, k=NW_EASE_STRENGTH)
        offsets_map = nwStoredWaveOffsets
        amplitude = WAVE_AMPLITUDE
    else:
        frac = slider_utils.ease_exponential(-slider_val / 100.0, k=NW_EASE_STRENGTH)
        offsets_map = nwStoredNoiseOffsets
        amplitude = NOISE_AMPLITUDE

    for curve in nwStoredAnimCurves:
        if curve not in nwStoredRealIndexes:
            continue
        if curve not in nwStoredSetters or curve not in nwStoredOriginalValues:
            continue
        setter = nwStoredSetters[curve]
        original_values = nwStoredOriginalValues[curve]
        offsets = offsets_map.get(curve, {})
        mult = nwStoredRepeatMult.get(curve, 1.0)
        for idx, orig_val in original_values.items():
            offset = offsets.get(idx, 0.0)
            new_value = orig_val + offset * amplitude * frac * mult
            try:
                setter(idx, new_value)
            except:
                continue


def _commit():
    for curve in nwStoredAnimCurves:
        if curve not in nwStoredRealIndexes:
            continue
        if curve not in nwStoredReaders or curve not in nwStoredSetters:
            continue
        if not cmds.objExists(curve):
            continue
        reader = nwStoredReaders[curve]
        setter = nwStoredSetters[curve]
        original_values = nwStoredOriginalValues[curve]
        changed = False
        for idx, orig_val in original_values.items():
            try:
                final_value = reader(idx)
                setter(idx, orig_val)
                cmds.keyframe(curve, edit=True, index=(idx, idx), valueChange=final_value, absolute=True)
                if abs(final_value - orig_val) > 1e-9:
                    changed = True
            except:
                continue
        if changed:
            _bump_usage_count(curve)


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global nwPushClick, nwStoredAnimCurves, nwStoredKeysSel, nwGetFrom

    status = "Wave / Noise: {0}".format(value)
    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    if current_time - last_update_time < update_throttle_ms and nwPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not nwPushClick:
        selected = cmds.ls(selection=True)
        if not selected:
            return last_update_time, status

        nwPushClick = True
        slider_utils.safe_undo_chunk_open("Wave / Noise")
        cmds.refresh(suspend=True)
        try:
            anim_curves, get_from = slider_utils.get_anim_curves()
            nwStoredAnimCurves = anim_curves or []
            nwGetFrom = get_from
            if not nwStoredAnimCurves:
                return last_update_time, status

            nwMfnCache.update(slider_utils.get_mfn_anim_curves_bulk(nwStoredAnimCurves))
            nwStoredKeysSel = slider_utils.get_keys_sel(
                nwStoredAnimCurves, nwGetFrom, mfn_cache=nwMfnCache, key_times_cache=nwKeyTimesCache
            )
            has_selected_keys = any(key_list for key_list in nwStoredKeysSel if key_list)
            if not has_selected_keys:
                nwStoredAnimCurves = []
                return last_update_time, status

            _setup_data()
        finally:
            cmds.refresh(suspend=False)

    if nwStoredAnimCurves:
        cmds.refresh(suspend=True)
        try:
            _apply(value)
        finally:
            cmds.refresh(suspend=False)

    return last_update_time, status


def reset_slider(slider_widget):
    global nwPushClick, nwStoredAnimCurves, nwStoredKeysSel
    global nwStoredSetters, nwStoredReaders
    global nwStoredRealIndexes, nwStoredOriginalValues
    global nwStoredWaveOffsets, nwStoredNoiseOffsets, nwStoredRepeatMult
    global nwMfnCache, nwKeyTimesCache

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    if nwPushClick:
        cmds.refresh(suspend=True)
        try:
            _commit()
        finally:
            cmds.refresh(suspend=False)
        slider_utils.safe_undo_chunk_close()

    nwPushClick = False
    nwStoredAnimCurves = []
    nwStoredKeysSel = []
    nwStoredSetters = {}
    nwStoredReaders = {}
    nwStoredRealIndexes = {}
    nwStoredOriginalValues = {}
    nwStoredWaveOffsets = {}
    nwStoredNoiseOffsets = {}
    nwStoredRepeatMult = {}
    nwMfnCache = {}
    nwKeyTimesCache = {}