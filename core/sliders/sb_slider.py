import time
import bisect
import heapq
import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
from maya import mel

from . import slider_utils

MAX_INSERTS_PER_GAP = 8
UPDATE_THROTTLE_MS = 35
THROTTLE_PER_CHANNEL_MS = 1.2
MAX_THROTTLE_MS = 120

SAMPLES_PER_FRAME = 4
KEYFRAME_REDUCER_FULL_PASSES = 4
BASE_TOLERANCE_FRACTION = 0.02
MAX_TOLERANCE_FRACTION = 0.5
BASE_EXTREMA_FRACTION = 0.0001
MAX_EXTREMA_FRACTION = 1.0

sbPushClick = False
sbSelection = []
sbSelectedKeyTimes = {}
sbPlugs = []
sbTimeRange = None
sbCache = {}
sbCurveNames = {}
sbCurveFns = {}
sbFinePts = {}


def _get_timeline_range():
    try:
        playback_slider = mel.eval('$tmpVar=$gPlayBackSlider')
        range_visible = cmds.timeControl(playback_slider, query=True, rangeVisible=True)
        if range_visible:
            time_range = cmds.timeControl(playback_slider, query=True, rangeArray=True)
            start_range = int(time_range[0])
            end_range = int(time_range[1] - 1)
            if end_range > start_range:
                return (start_range, end_range)
        return None
    except:
        return None


def _get_graph_editor_selected_range():
    selected_times = cmds.keyframe(query=True, selected=True, timeChange=True)
    if not selected_times:
        return None
    return (min(selected_times), max(selected_times))


def _get_full_animation_range(objects):
    all_times = []
    for obj in objects:
        times = cmds.keyframe(obj, query=True, timeChange=True)
        if times:
            all_times.extend(times)
    if all_times:
        return (min(all_times), max(all_times))
    start = cmds.playbackOptions(query=True, animationStartTime=True)
    end = cmds.playbackOptions(query=True, animationEndTime=True)
    return (start, end)


def _determine_time_range(objects):
    selected_range = _get_graph_editor_selected_range()
    if selected_range:
        return selected_range
    timeline_range = _get_timeline_range()
    if timeline_range:
        return timeline_range
    return _get_full_animation_range(objects)


def _resolve_plugs_from_graph_editor_selection():
    curves = cmds.keyframe(query=True, selected=True, name=True)
    if not curves:
        return []
    plugs = []
    for c in set(curves):
        conns = cmds.listConnections(c, destination=True, plugs=True, source=False) or []
        for p in conns:
            if p not in plugs:
                plugs.append(p)
    return plugs


def _resolve_plugs_for_objects(objects):
    plugs = []
    for obj in objects:
        attrs = cmds.listAttr(obj, keyable=True, unlocked=True) or []
        for attr in attrs:
            plug = obj + "." + attr
            if not cmds.objExists(plug):
                continue
            conns = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
            if conns and plug not in plugs:
                plugs.append(plug)
    return plugs


def _resolve_plugs(objects):
    graph_editor_plugs = _resolve_plugs_from_graph_editor_selection()
    if graph_editor_plugs:
        return graph_editor_plugs
    return _resolve_plugs_for_objects(objects)


def _capture_selected_key_times(curves):
    result = {}
    for curve in curves:
        times = cmds.keyframe(curve, query=True, selected=True, timeChange=True)
        if times:
            result[curve] = list(times)
    return result


def _build_cache(curves, time_range):
    cache = {}
    for curve in curves:
        times = cmds.keyframe(curve, query=True, time=time_range, timeChange=True)
        if not times:
            cache[curve] = []
            continue
        values = cmds.keyframe(curve, query=True, time=time_range, valueChange=True)
        inTans = cmds.keyTangent(curve, query=True, time=time_range, inTangentType=True) or []
        outTans = cmds.keyTangent(curve, query=True, time=time_range, outTangentType=True) or []
        entries = []
        for i, t in enumerate(times):
            v = values[i] if i < len(values) else None
            inTan = inTans[i] if i < len(inTans) else None
            outTan = outTans[i] if i < len(outTans) else None
            entries.append((t, v, inTan, outTan))
        cache[curve] = entries
    return cache


def _get_current_curve_for_plug(plug):
    conns = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
    return conns[0] if conns else None


def _get_anim_curve_fn(curve_name):
    sel = om2.MSelectionList()
    sel.add(curve_name)
    mobj = sel.getDependNode(0)
    return oma2.MFnAnimCurve(mobj)


def _resolve_curve_caches(plugs):
    global sbCurveNames, sbCurveFns
    sbCurveNames = {}
    sbCurveFns = {}
    for plug in plugs:
        curve_name = _get_current_curve_for_plug(plug)
        if not curve_name:
            continue
        sbCurveNames[plug] = curve_name
        if curve_name not in sbCurveFns:
            try:
                sbCurveFns[curve_name] = _get_anim_curve_fn(curve_name)
            except:
                continue


def _get_curve_name(plug):
    curve_name = sbCurveNames.get(plug)
    if curve_name and cmds.objExists(curve_name):
        return curve_name
    curve_name = _get_current_curve_for_plug(plug)
    if curve_name:
        sbCurveNames[plug] = curve_name
    return curve_name


def _get_curve_fn(curve_name):
    fn_curve = sbCurveFns.get(curve_name)
    if fn_curve is not None:
        return fn_curve
    try:
        fn_curve = _get_anim_curve_fn(curve_name)
        sbCurveFns[curve_name] = fn_curve
        return fn_curve
    except:
        return None


def _recreate_curve_from_cache(plug, entries):
    for t, v, inTan, outTan in entries:
        try:
            cmds.setKeyframe(plug, time=t, value=v)
        except:
            continue
    new_curve_name = _get_current_curve_for_plug(plug)
    if new_curve_name:
        sbCurveNames[plug] = new_curve_name
        try:
            sbCurveFns[new_curve_name] = _get_anim_curve_fn(new_curve_name)
        except:
            sbCurveFns.pop(new_curve_name, None)
    return new_curve_name


def _restore_curve_from_cache(plug, time_range):
    entries = sbCache.get(plug)
    if entries is None:
        return
    curve_name = _get_curve_name(plug)
    if not curve_name:
        return
    try:
        cmds.cutKey(curve_name, time=time_range, clear=True)
    except:
        pass
    if not entries:
        return

    curve_exists = cmds.objExists(curve_name)
    added_via_api = False
    if curve_exists:
        fn_curve = _get_curve_fn(curve_name)
        if fn_curve is not None:
            try:
                unit = om2.MTime.uiUnit()
                angular = fn_curve.animCurveType in (oma2.MFnAnimCurve.kAnimCurveTA, oma2.MFnAnimCurve.kAnimCurveUA)
                times = om2.MTimeArray()
                values = om2.MDoubleArray()
                for t, v, inTan, outTan in entries:
                    times.append(om2.MTime(t, unit))
                    values.append(om2.MAngle(v, om2.MAngle.uiUnit()).asRadians() if angular else v)
                fn_curve.addKeys(times, values)
                added_via_api = True
            except:
                added_via_api = False

    if not added_via_api:
        recreated_name = _recreate_curve_from_cache(plug, entries)
        if recreated_name:
            curve_name = recreated_name

    if not curve_name or not cmds.objExists(curve_name):
        return

    tangent_groups = {}
    for t, v, inTan, outTan in entries:
        if not (inTan and outTan):
            continue
        tangent_groups.setdefault((inTan, outTan), []).append((t, t))
    for (inTan, outTan), time_pairs in tangent_groups.items():
        try:
            cmds.keyTangent(curve_name, time=time_pairs, inTangentType=inTan, outTangentType=outTan)
        except:
            continue


def _sample_curve(fn_curve, t0, t1, samples_per_frame):
    n = max(2, int(round((t1 - t0) * samples_per_frame)))
    unit = om2.MTime.uiUnit()
    angular = fn_curve.animCurveType in (oma2.MFnAnimCurve.kAnimCurveTA, oma2.MFnAnimCurve.kAnimCurveUA)
    pts = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * (float(i) / n)
        v = fn_curve.evaluate(om2.MTime(t, unit))
        if angular:
            v = om2.MAngle(v, om2.MAngle.kRadians).asUnits(om2.MAngle.uiUnit())
        pts.append((t, v))
    return pts


def _compute_fine_points_cache(plugs, cache):
    fine_cache = {}
    for plug in plugs:
        entries = cache.get(plug)
        if not entries or len(entries) < 3:
            continue
        curve_name = _get_curve_name(plug)
        if not curve_name:
            continue
        fn_curve = _get_curve_fn(curve_name)
        if fn_curve is None:
            continue
        candidates = [(t, v) for t, v, inTan, outTan in entries]
        t0 = candidates[0][0]
        t1 = candidates[-1][0]
        try:
            fine_pts = _sample_curve(fn_curve, t0, t1, SAMPLES_PER_FRAME)
        except:
            continue
        fine_times = [pt[0] for pt in fine_pts]
        fine_cache[plug] = (fine_pts, fine_times, candidates)
    return fine_cache


def _line_value(t, t0, v0, t1, v1):
    if t1 == t0:
        return v0
    frac = (t - t0) / (t1 - t0)
    return v0 + frac * (v1 - v0)


def _max_deviation(fine_pts, fine_times, t0, v0, t1, v1):
    lo = bisect.bisect_left(fine_times, t0)
    hi = bisect.bisect_right(fine_times, t1)
    max_dev = 0.0
    max_t = None
    for i in range(lo, hi):
        t, v = fine_pts[i]
        dev = abs(v - _line_value(t, t0, v0, t1, v1))
        if dev > max_dev:
            max_dev = dev
            max_t = t
    return max_dev, max_t


def _sign_of(d, eps):
    if d > eps:
        return 1
    if d < -eps:
        return -1
    return 0


def _find_extrema(candidates, eps):
    protected = set()
    n = len(candidates)
    if n < 3:
        return protected
    for i in range(1, n - 1):
        slope_in = _sign_of(candidates[i][1] - candidates[i - 1][1], eps)
        slope_out = _sign_of(candidates[i + 1][1] - candidates[i][1], eps)
        if slope_in != slope_out:
            protected.add(i)
    return protected


def _greedy_reduce(candidates, fine_pts, fine_times, tolerance, protected):
    n = len(candidates)
    if n < 3:
        return set(range(n))

    alive = [True] * n
    prev_idx = [i - 1 for i in range(n)]
    next_idx = [i + 1 for i in range(n)]
    prev_idx[0] = -1
    next_idx[n - 1] = -1
    versions = [0] * n

    def segment_cost(i):
        p = prev_idx[i]
        q = next_idx[i]
        if p < 0 or q >= n:
            return None
        t0, v0 = candidates[p]
        t1, v1 = candidates[q]
        err, _ = _max_deviation(fine_pts, fine_times, t0, v0, t1, v1)
        return err

    heap = []
    for i in range(1, n - 1):
        if i in protected:
            continue
        cost = segment_cost(i)
        if cost is not None:
            heapq.heappush(heap, (cost, i, versions[i]))

    alive_count = n
    while heap and alive_count >= 3:
        cost, i, ver = heapq.heappop(heap)
        if not alive[i] or ver != versions[i]:
            continue
        if cost > tolerance:
            break
        p = prev_idx[i]
        q = next_idx[i]
        if p < 0 or q >= n:
            continue
        alive[i] = False
        alive_count -= 1
        next_idx[p] = q
        prev_idx[q] = p
        for neighbor in (p, q):
            if 0 < neighbor < n - 1 and alive[neighbor] and neighbor not in protected:
                versions[neighbor] += 1
                ncost = segment_cost(neighbor)
                if ncost is not None:
                    heapq.heappush(heap, (ncost, neighbor, versions[neighbor]))

    return set(i for i in range(n) if alive[i])


def _apply_simplify(targets, time_range, strength, cache):
    if strength <= 0.0:
        return
    numPasses = max(1, int(round(strength * KEYFRAME_REDUCER_FULL_PASSES)))
    for plug in targets:
        cached = sbFinePts.get(plug)
        if not cached:
            continue
        fine_pts, fine_times, candidates = cached
        candidate_values = [v for t, v in candidates]
        value_range = max(candidate_values) - min(candidate_values)
        tolerance_fraction = BASE_TOLERANCE_FRACTION + strength * (MAX_TOLERANCE_FRACTION - BASE_TOLERANCE_FRACTION)
        extrema_fraction = BASE_EXTREMA_FRACTION + strength * (MAX_EXTREMA_FRACTION - BASE_EXTREMA_FRACTION)
        tolerance = max(value_range * tolerance_fraction, 1e-6)
        extrema_eps = max(value_range * extrema_fraction, 1e-6)
        remaining = candidates
        for pass_index in range(numPasses):
            if len(remaining) < 3:
                break
            protected = _find_extrema(remaining, extrema_eps)
            alive = _greedy_reduce(remaining, fine_pts, fine_times, tolerance, protected)
            remaining = [remaining[i] for i in sorted(alive)]
        keep_times_set = set(t for t, v in remaining)
        remove_time_pairs = [(t, t) for t, v in candidates if t not in keep_times_set]
        if not remove_time_pairs:
            continue
        try:
            cmds.cutKey(plug, time=remove_time_pairs, clear=True)
        except:
            for t, tt in remove_time_pairs:
                try:
                    cmds.cutKey(plug, time=(t, t), clear=True)
                except:
                    continue


def _apply_insert(targets, time_range, strength):
    if strength <= 0.0:
        return
    density = int(round(strength * MAX_INSERTS_PER_GAP))
    if density <= 0:
        return
    with_keys = []
    without_keys = []
    all_insert_times = []
    for t in targets:
        existing_times = cmds.keyframe(t, query=True, time=time_range, timeChange=True)
        if not existing_times:
            without_keys.append(t)
            continue
        with_keys.append(t)
        existing_times = sorted(set(existing_times))
        for i in range(len(existing_times) - 1):
            startT = existing_times[i]
            endT = existing_times[i + 1]
            span = endT - startT
            if span <= 0:
                continue
            for step in range(1, density + 1):
                fraction = step / float(density + 1)
                insertTime = round(startT + span * fraction)
                if insertTime <= startT or insertTime >= endT:
                    continue
                all_insert_times.append(insertTime)
    if not all_insert_times:
        return
    all_insert_times = sorted(set(all_insert_times))
    if with_keys:
        cmds.setKeyframe(with_keys, insert=True, time=all_insert_times)
    if without_keys:
        cmds.setKeyframe(without_keys, time=all_insert_times)


def _restore_key_selection():
    try:
        cmds.selectKey(clear=True)
    except:
        pass
    if sbSelection:
        try:
            cmds.select(sbSelection, replace=True)
        except:
            pass
    if sbSelectedKeyTimes:
        range_groups = {}
        for curve, times in sbSelectedKeyTimes.items():
            if not cmds.objExists(curve):
                continue
            range_groups.setdefault((min(times), max(times)), []).append(curve)
        for (lo, hi), curves in range_groups.items():
            try:
                cmds.selectKey(curves, add=True, time=(lo, hi))
            except:
                continue


def _start():
    global sbSelection, sbSelectedKeyTimes, sbPlugs, sbTimeRange, sbCache, sbFinePts

    selected = cmds.ls(selection=True)
    if not selected:
        return False
    sbSelection = selected
    sbTimeRange = _determine_time_range(selected)
    if sbTimeRange is None:
        return False
    sbPlugs = _resolve_plugs(selected)
    if not sbPlugs:
        return False
    sbSelectedKeyTimes = _capture_selected_key_times(sbPlugs)
    sbCache = _build_cache(sbPlugs, sbTimeRange)
    _resolve_curve_caches(sbPlugs)
    sbFinePts = _compute_fine_points_cache(sbPlugs, sbCache)
    return True


def _execute(value):
    try:
        cmds.selectKey(clear=True)
    except:
        pass
    for plug in sbPlugs:
        _restore_curve_from_cache(plug, sbTimeRange)
    if value < 0:
        strength = min(1.0, (-value) / 100.0)
        _apply_simplify(sbPlugs, sbTimeRange, strength, sbCache)
    elif value > 0:
        strength = min(1.0, value / 100.0)
        _apply_insert(sbPlugs, sbTimeRange, strength)
    _restore_key_selection()


def _effective_throttle_ms(base_throttle_ms):
    channel_count = len(sbPlugs) if sbPlugs else 0
    scaled = channel_count * THROTTLE_PER_CHANNEL_MS
    return min(MAX_THROTTLE_MS, max(base_throttle_ms, scaled))


def slider_logic(value, mouse_pressed, last_update_time, update_throttle_ms):
    global sbPushClick

    if value < 0:
        status = "Simplify | Bake: {0} (simplify)".format(value)
    elif value > 0:
        status = "Simplify | Bake: {0} (insert)".format(value)
    else:
        status = "Simplify | Bake: 0"

    if not mouse_pressed:
        return last_update_time, status

    current_time = time.time() * 1000
    effective_throttle = _effective_throttle_ms(update_throttle_ms)
    if current_time - last_update_time < effective_throttle and sbPushClick:
        return last_update_time, status
    last_update_time = current_time

    if not sbPushClick:
        if not _start():
            return last_update_time, status
        slider_utils.safe_undo_chunk_open("Simplify Bake")
        sbPushClick = True

    cmds.waitCursor(state=True)
    cmds.refresh(suspend=True)
    try:
        _execute(value)
    finally:
        cmds.refresh(suspend=False)
        cmds.waitCursor(state=False)

    return last_update_time, status


def reset_slider(slider_widget):
    global sbPushClick, sbSelection, sbSelectedKeyTimes, sbPlugs, sbTimeRange, sbCache, sbCurveNames, sbCurveFns, sbFinePts

    value = slider_widget.value()

    if sbPushClick:
        cmds.waitCursor(state=True)
        cmds.refresh(suspend=True)
        try:
            _execute(value)
        finally:
            cmds.refresh(suspend=False)
            cmds.waitCursor(state=False)
        slider_utils.safe_undo_chunk_close()

    slider_widget.blockSignals(True)
    slider_widget.setValue(0)
    slider_widget.blockSignals(False)

    sbPushClick = False
    sbSelection = []
    sbSelectedKeyTimes = {}
    sbPlugs = []
    sbTimeRange = None
    sbCache = {}
    sbCurveNames = {}
    sbCurveFns = {}
    sbFinePts = {}