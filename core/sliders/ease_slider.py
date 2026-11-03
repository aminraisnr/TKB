import maya.cmds as cmds
from maya import mel
import maya.utils
import platform
import time

try:
    from . import slider_utils
except ImportError:
    import slider_utils

try:
    import __builtin__ as builtins
except ImportError:
    import builtins

try:
    max = builtins.max
    min = builtins.min
    sum = builtins.sum
    abs = builtins.abs
    len = builtins.len
    int = builtins.int
    str = builtins.str
    set = builtins.set
    range = builtins.range
    list = builtins.list
    dict = builtins.dict
except:
    pass

IS_MACOS = platform.system() == "Darwin"

EASE_SENSITIVITY = 0.6

pushClick = False
openChunk = True
originalValues = {}
storedSelection = []
storedAnimCurves = []
storedKeysSel = []
_tweenData = {}

blendPushClick = False
blendOpenChunk = True
blendStoredKeyValues = {}
blendStoredKeyTimes = {}
blendStoredIndexes = {}
blendStoredAnimCurves = []
blendStoredKeysSel = []
blendLastValue = 0
blendScaleValue = 1

last_update_time = 0
update_throttle_ms = 1


def safe_undo_chunk_close():
    try:
        if IS_MACOS:
            cmds.refresh()
            maya.utils.processIdleEvents()
        cmds.undoInfo(closeChunk=True)
    except:
        pass


def safe_undo_chunk_open(chunk_name="Ease Operation"):
    try:
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        if IS_MACOS:
            maya.utils.processIdleEvents()
    except:
        pass


def get_anim_curves():
    anim_curves = cmds.keyframe(query=True, name=True, selected=True)
    get_from = "graphEditor"
    
    if not anim_curves:
        get_from = "timeline"
        play_back_slider = mel.eval('$temp=$gPlayBackSlider')
        anim_curves = cmds.timeControl(play_back_slider, query=True, animCurveNames=True)
    
    return [anim_curves, get_from]


def get_timeline_range():
    play_back_slider = mel.eval('$temp_playBackSlider=$gPlayBackSlider')
    time_range = cmds.timeControl(play_back_slider, query=True, rangeArray=True)
    start_range = int(time_range[0])
    end_range = int(time_range[1] - 1)
    return [start_range, end_range]


def get_keys_sel(anim_curves, get_from):
    if not anim_curves:
        return []
    
    keys_sel = []
    if get_from == "graphEditor":
        for node in anim_curves:
            keys = cmds.keyframe(node, selected=True, query=True, timeChange=True)
            keys_sel.append(keys if keys else [])
    else:
        range_val = get_timeline_range()
        for node in anim_curves:
            if not cmds.objExists(node):
                keys_sel.append([])
                continue
                
            all_keys = cmds.keyframe(node, query=True, timeChange=True)
            if all_keys:
                range_keys = [k for k in all_keys if range_val[0] <= k < range_val[1]]
                keys_sel.append(range_keys)
            else:
                keys_sel.append([])
    return keys_sel


def get_key_indexes(curve, key_times):
    if not cmds.objExists(curve) or not key_times:
        return []
    
    all_key_times = cmds.keyframe(curve, query=True, timeChange=True)
    if not all_key_times:
        return []
    
    indexes = []
    for key_time in key_times:
        for i, curve_time in enumerate(all_key_times):
            if abs(key_time - curve_time) < 0.001:
                indexes.append(i)
                break
    return indexes


def set_key_tangents_smart(curves_and_times):
    if not curves_and_times:
        return
    
    step_count = 0
    checked_count = 0
    max_check_threshold = 30
    
    for curve, key_times in curves_and_times.items():
        if checked_count >= max_check_threshold:
            break
            
        try:
            all_keys = cmds.keyframe(curve, query=True, timeChange=True)
            if not all_keys or len(all_keys) < 2:
                continue
            
            for key_time in key_times:
                current_key_index = None
                for i, kt in enumerate(all_keys):
                    if abs(kt - key_time) < 0.001:
                        current_key_index = i
                        break
                
                if current_key_index is None:
                    continue
                
                checked_count += 1
                
                if current_key_index > 0:
                    prev_out_tangent = cmds.keyTangent(curve, index=(current_key_index-1,), 
                                                     query=True, outTangentType=True)
                    if prev_out_tangent and prev_out_tangent[0] == 'step':
                        step_count += 1
                
                if current_key_index < len(all_keys) - 1:
                    next_in_tangent = cmds.keyTangent(curve, index=(current_key_index+1,), 
                                                    query=True, inTangentType=True)
                    if next_in_tangent and next_in_tangent[0] == 'step':
                        step_count += 1
                
                if checked_count >= max_check_threshold:
                    break
        except:
            continue
    
    if step_count >= max_check_threshold:
        for curve, key_times in curves_and_times.items():
            try:
                all_keys = cmds.keyframe(curve, query=True, timeChange=True)
                if not all_keys:
                    continue
                
                for key_time in key_times:
                    current_key_index = None
                    for i, kt in enumerate(all_keys):
                        if abs(kt - key_time) < 0.001:
                            current_key_index = i
                            break
                    
                    if current_key_index is not None:
                        cmds.keyTangent(curve, index=(current_key_index,), 
                                      outTangentType='step')
            except:
                continue
    else:
        for curve, key_times in curves_and_times.items():
            try:
                all_keys = cmds.keyframe(curve, query=True, timeChange=True)
                if not all_keys or len(all_keys) < 2:
                    continue
                
                for key_time in key_times:
                    current_key_index = None
                    for i, kt in enumerate(all_keys):
                        if abs(kt - key_time) < 0.001:
                            current_key_index = i
                            break
                    
                    if current_key_index is None:
                        continue
                        
                    prev_is_step = False
                    next_is_step = False
                    
                    if current_key_index > 0:
                        prev_out_tangent = cmds.keyTangent(curve, index=(current_key_index-1,), 
                                                         query=True, outTangentType=True)
                        if prev_out_tangent and prev_out_tangent[0] == 'step':
                            prev_is_step = True
                    
                    if current_key_index < len(all_keys) - 1:
                        next_in_tangent = cmds.keyTangent(curve, index=(current_key_index+1,), 
                                                        query=True, inTangentType=True)
                        if next_in_tangent and next_in_tangent[0] == 'step':
                            next_is_step = True
                    
                    if prev_is_step and next_is_step:
                        cmds.keyTangent(curve, index=(current_key_index,), 
                                      outTangentType='step')
                    elif prev_is_step:
                        pass
                    elif next_is_step:
                        cmds.keyTangent(curve, index=(current_key_index,), outTangentType='step')
            except:
                continue


def initialize_tween():
    global originalValues, storedAnimCurves, storedKeysSel, openChunk, _tweenData
    
    safe_undo_chunk_open("Ease Tween")
    originalValues = {}
    _tweenData = {}
    
    getCurves = slider_utils.get_anim_curves()
    storedAnimCurves = getCurves[0]
    getFrom = getCurves[1]
    
    if not storedAnimCurves:
        openChunk = False
        return False
        
    mfnCache = slider_utils.get_mfn_anim_curves_bulk(storedAnimCurves)
    storedKeysSel = slider_utils.get_keys_sel(storedAnimCurves, getFrom, mfn_cache=mfnCache)
    
    hasSelectedKeys = any(keyList for keyList in storedKeysSel if keyList)
    
    if not hasSelectedKeys:
        current_time = cmds.currentTime(query=True)
        for curve in storedAnimCurves:
            if cmds.objExists(curve):
                existingKeys = cmds.keyframe(curve, query=True, timeChange=True)
                keyExists = existingKeys and current_time in existingKeys
                
                cmds.setKeyframe(curve, time=current_time, insert=True)
                
                if not keyExists:
                    prev_key = cmds.findKeyframe(curve, time=(current_time, current_time), which="previous")
                    next_key = cmds.findKeyframe(curve, time=(current_time, current_time), which="next")
                    
                    in_tangent_type = "auto"
                    out_tangent_type = "auto"
                    
                    step_detected = False
                    
                    if prev_key is not None:
                        try:
                            prev_out_tangent = cmds.keyTangent(curve, time=(prev_key, prev_key), 
                                                             query=True, outTangentType=True)[0]
                            if prev_out_tangent == "step":
                                step_detected = True
                                in_tangent_type = "auto"
                                out_tangent_type = "step"
                        except:
                            pass
                    
                    if not step_detected and next_key is not None:
                        try:
                            next_out_tangent = cmds.keyTangent(curve, time=(next_key, next_key), 
                                                             query=True, outTangentType=True)[0]
                            if next_out_tangent == "step":
                                step_detected = True
                                in_tangent_type = "auto"
                                out_tangent_type = "step"
                        except:
                            pass
                    
                    cmds.keyTangent(curve, time=(current_time, current_time),
                                  inTangentType=in_tangent_type, outTangentType=out_tangent_type)
        
        storedKeysSel = []
        for curve in storedAnimCurves:
            if cmds.objExists(curve):
                storedKeysSel.append([current_time])
            else:
                storedKeysSel.append([])
    
    angle_unit, linear_unit = slider_utils.get_current_units()
    
    for n, curve in enumerate(storedAnimCurves):
        if not storedKeysSel[n]:
            continue
        
        mfn = mfnCache.get(curve)
        if mfn is None:
            mfn = slider_utils.get_mfn_anim_curve(curve)
        if mfn is None:
            continue
        
        reader = slider_utils.make_value_reader(mfn, angle_unit, linear_unit)
        setter = slider_utils.make_value_setter(mfn, angle_unit, linear_unit)
        numKeys = mfn.numKeys
        
        curveEntries = []
        originalValues[curve] = {}
        for key_time in storedKeysSel[n]:
            key_index = slider_utils.get_key_index_at_time(mfn, key_time)
            if key_index < 0:
                continue
            
            original_val = reader(key_index)
            originalValues[curve][key_time] = original_val
            
            prev_index = key_index - 1 if key_index > 0 else None
            next_index = key_index + 1 if key_index < numKeys - 1 else None
            
            curveEntries.append({
                "index": key_index,
                "original": original_val,
                "prev_index": prev_index,
                "next_index": next_index,
            })
        
        if curveEntries:
            runs = []
            runMembers = set()
            sortedEntries = sorted(curveEntries, key=lambda e: e["index"])
            group = []
            for entry in sortedEntries + [None]:
                if entry is not None and (not group or entry["index"] == group[-1]["index"] + 1):
                    group.append(entry)
                    continue
                if group and group[0]["prev_index"] is not None and group[-1]["next_index"] is not None:
                    runs.append({
                        "entries": group,
                        "start": reader(group[0]["prev_index"]),
                        "end": reader(group[-1]["next_index"]),
                    })
                    for member in group:
                        runMembers.add(member["index"])
                group = [entry] if entry is not None else []
            
            _tweenData[curve] = {
                "setter": setter,
                "reader": reader,
                "entries": curveEntries,
                "loose": [e for e in curveEntries if e["index"] not in runMembers],
                "runs": runs,
            }
    
    return True


def run_fraction(bias, k, count):
    ratio = (1.0 - bias) / bias
    if abs(ratio - 1.0) < 1e-9:
        return k / (count + 1.0)
    if ratio < 1.0:
        return (1.0 - ratio ** k) / (1.0 - ratio ** (count + 1))
    inv = 1.0 / ratio
    return (inv ** (count + 1 - k) - inv ** (count + 1)) / (1.0 - inv ** (count + 1))


def execute_tween(bias):
    global _tweenData
    
    if not _tweenData:
        return
    
    for curve, data in _tweenData.items():
        if not cmds.objExists(curve):
            continue
        
        setter = data["setter"]
        reader = data["reader"]
        
        for run in data["runs"]:
            count = len(run["entries"])
            span = run["end"] - run["start"]
            for k, entry in enumerate(run["entries"], 1):
                try:
                    setter(entry["index"], run["start"] + span * run_fraction(bias, k, count))
                except:
                    continue
        
        for entry in data["loose"]:
            original_val = entry["original"]
            prev_index = entry["prev_index"]
            next_index = entry["next_index"]
            
            prev_value = reader(prev_index) if prev_index is not None else None
            next_value = reader(next_index) if next_index is not None else None
            
            tweened_value = original_val
            
            if prev_value is not None and next_value is not None:
                tweened_value = prev_value + (next_value - prev_value) * bias
                
            elif prev_value is not None:
                if bias < 0.5:
                    blend_factor = (0.5 - bias) * 2
                    tweened_value = original_val + (prev_value - original_val) * blend_factor
                    
            elif next_value is not None:
                if bias > 0.5:
                    blend_factor = (bias - 0.5) * 2
                    tweened_value = original_val + (next_value - original_val) * blend_factor
            
            try:
                setter(entry["index"], tweened_value)
            except:
                continue


def commit_tween():
    global _tweenData
    
    for curve, data in _tweenData.items():
        if not cmds.objExists(curve):
            continue
        
        setter = data["setter"]
        reader = data["reader"]
        for entry in data["entries"]:
            try:
                final_value = reader(entry["index"])
                setter(entry["index"], entry["original"])
                cmds.keyframe(curve, index=(entry["index"], entry["index"]), valueChange=final_value, absolute=True)
            except:
                continue


def reset_tween():
    global pushClick, openChunk, originalValues, storedSelection, storedAnimCurves, storedKeysSel, _tweenData
    
    if pushClick and openChunk:
        cmds.refresh(suspend=True)
        try:
            commit_tween()
        finally:
            cmds.refresh(suspend=False)
        try:
            safe_undo_chunk_close()
        except:
            pass
        openChunk = False
    
    pushClick = False
    originalValues = {}
    storedSelection = []
    storedAnimCurves = []
    storedKeysSel = []
    _tweenData = {}


def setup_blend_key_transform_data():
    global blendStoredKeyValues, blendStoredKeyTimes, blendStoredIndexes
    
    blendStoredKeyValues = {}
    blendStoredKeyTimes = {}
    blendStoredIndexes = {}
    
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
        
        blendStoredKeyValues[curve] = keyValues
        blendStoredKeyTimes[curve] = keyTimes
        
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
        
        blendStoredIndexes[curve] = indexes


def execute_blend_key_transform(slider_val):
    global blendLastValue, blendScaleValue
    
    if not blendStoredAnimCurves:
        return
    
    tValue = (slider_val + 100) / 100.0
    
    if tValue <= 1: 
        p = tValue
    else:          
        p = 2 - tValue
    
    if p == 0:
        p = 0.0000001
    
    if blendPushClick and blendLastValue != 0:
        blendScaleValue = (1.0 / blendLastValue) * p
    else:
        blendScaleValue = p
    
    for n, curve in enumerate(blendStoredAnimCurves):
        if curve not in blendStoredIndexes or not cmds.objExists(curve):
            continue
            
        keyValues = blendStoredKeyValues[curve]
        keyTimes = blendStoredKeyTimes[curve]
        segments = blendStoredIndexes[curve]
        
        for s, segment in enumerate(segments):
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
            
            if tValue <= 1:
                pivot = fv
            else:
                pivot = lv
            
            for i, keyIndex in enumerate(segment):
                if 1 <= i <= len(segment) - 2:
                    realIndex = keyIndex - 2
                    
                    if 0 <= realIndex < len(cmds.keyframe(curve, query=True, timeChange=True) or []):
                        try:
                            cmds.scaleKey(curve, index=(realIndex, realIndex), 
                                        valuePivot=pivot, valueScale=blendScaleValue)
                        except:
                            try:
                                currentVal = cmds.keyframe(curve, index=(realIndex, realIndex), 
                                                         query=True, valueChange=True)[0]
                                newValue = pivot + (currentVal - pivot) * blendScaleValue
                                cmds.keyframe(curve, edit=True, index=(realIndex, realIndex), 
                                            valueChange=newValue)
                            except:
                                continue
    
    blendLastValue = p


def initialize_blend():
    global blendStoredAnimCurves, blendStoredKeysSel, blendOpenChunk
    
    safe_undo_chunk_open("Blend to Neighbors")
    
    getCurves = get_anim_curves()
    blendStoredAnimCurves = getCurves[0]
    getFrom = getCurves[1]
    
    if not blendStoredAnimCurves:
        blendOpenChunk = False
        return False
        
    blendStoredKeysSel = get_keys_sel(blendStoredAnimCurves, getFrom)
    
    hasSelectedKeys = any(keyList for keyList in blendStoredKeysSel if keyList)
    
    if not hasSelectedKeys:
        currentTime = cmds.currentTime(query=True)
        curves_with_new_keys = {}
        for curve in blendStoredAnimCurves:
            if cmds.objExists(curve):
                existingKeys = cmds.keyframe(curve, query=True, timeChange=True)
                keyExists = existingKeys and currentTime in existingKeys
                
                cmds.setKeyframe(curve, time=currentTime, insert=True)
                
                if not keyExists:
                    curves_with_new_keys[curve] = [currentTime]
        
        if curves_with_new_keys:
            for curve, times in curves_with_new_keys.items():
                for key_time in times:
                    cmds.keyTangent(curve, time=(key_time, key_time), 
                                   inTangentType='auto', outTangentType='auto')
        
        blendStoredKeysSel = []
        for curve in blendStoredAnimCurves:
            if cmds.objExists(curve):
                blendStoredKeysSel.append([currentTime])
            else:
                blendStoredKeysSel.append([])
    
    setup_blend_key_transform_data()
    return True


def reset_blend():
    global blendPushClick, blendOpenChunk, blendStoredKeyValues, blendStoredKeyTimes, blendStoredIndexes
    global blendStoredAnimCurves, blendStoredKeysSel, blendLastValue, blendScaleValue
    
    if blendPushClick and blendOpenChunk:
        try:
            safe_undo_chunk_close()
        except:
            pass
        blendOpenChunk = False
    
    blendPushClick = False
    blendStoredKeyValues = {}
    blendStoredKeyTimes = {}
    blendStoredIndexes = {}
    blendStoredAnimCurves = []
    blendStoredKeysSel = []
    blendLastValue = 0
    blendScaleValue = 1


class EaseSlider:
    
    def __init__(self):
        self.is_active = False
        self.last_update_time = 0
        self.update_throttle_ms = 1
    
    def start(self):
        global pushClick, openChunk
        
        if self.is_active:
            return
        
        self.is_active = True
        pushClick = True
        openChunk = True
        
        initialize_tween()
    
    def update(self, value):
        global pushClick, openChunk, last_update_time
        
        if not self.is_active:
            self.start()
        
        current_time = time.time() * 1000
        time_since_last = current_time - self.last_update_time
        
        if time_since_last < self.update_throttle_ms and pushClick:
            return
        
        self.last_update_time = current_time
        
        bias = (value + 100) / 200.0
        bias = 0.5 + (bias - 0.5) * EASE_SENSITIVITY
        cmds.refresh(suspend=True)
        try:
            execute_tween(bias)
        finally:
            cmds.refresh(suspend=False)
    
    def finish(self):
        global pushClick, openChunk
        
        if not self.is_active:
            return
        
        self.is_active = False
        reset_tween()
    
    def cancel(self):
        self.finish()


_ease_slider_instance = None

def get_ease_slider():
    global _ease_slider_instance
    if _ease_slider_instance is None:
        _ease_slider_instance = EaseSlider()
    return _ease_slider_instance


def start_ease():
    get_ease_slider().start()


def update_ease(value):
    get_ease_slider().update(value)


def finish_ease():
    get_ease_slider().finish()


def ease_value(value):
    slider = get_ease_slider()
    slider.start()
    slider.update(value)
    slider.finish()