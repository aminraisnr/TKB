# =========================================================
# TWEEN SLIDER / TWEEN MACHINE CORE ENGINE (STRICT AXIS FILTER)
# File: tweenSlider.py
# =========================================================

import maya.cmds as cmds

class TweenSlider(object):

    @staticmethod
    def get_selected_anim_curves():
        """
        Mendapatkan animCurve berdasarkan hirarki presisi seleksi pengguna:
        1. Kurva/Keyframe yang dipilih di Graph Editor.
        2. Atribut yang di-highlight di Channel Box.
        3. Objek yang dipilih di Viewport (fallback ke semua kurva objek).
        """
        # 1. Cek seleksi kurva/keyframe langsung dari Graph Editor
        selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
        if selected_curves:
            return list(set(selected_curves))

        # 2. Cek atribut spesifik yang di-highlight di Channel Box
        selected_objs = cmds.ls(selection=True)
        if not selected_objs:
            return []

        channel_box = "mainChannelBox"
        selected_attrs = []
        for flag in ("sma", "ssa", "sha", "soa"):
            try:
                res = cmds.channelBox(channel_box, q=True, **{flag: True})
                if res:
                    selected_attrs.extend(res)
            except Exception:
                pass

        curves = []
        if selected_attrs:
            for obj in selected_objs:
                for attr in selected_attrs:
                    plug = f"{obj}.{attr}"
                    if cmds.objExists(plug):
                        conn = cmds.listConnections(plug, type="animCurve") or []
                        curves.extend(conn)
            if curves:
                return list(set(curves))

        # 3. Fallback: Ambil semua kurva dari objek terpilih
        conn = cmds.listConnections(selected_objs, type="animCurve") or []
        return list(set(conn))

    @staticmethod
    def get_neighbor_cache():
        curves = TweenSlider.get_selected_anim_curves()
        if not curves:
            return {}

        current_time = cmds.currentTime(query=True)
        cache = {}

        for curve in curves:
            key_times = cmds.keyframe(curve, query=True, timeChange=True) or []
            key_vals = cmds.keyframe(curve, query=True, valueChange=True) or []

            if not key_times or not key_vals or len(key_times) != len(key_vals):
                continue

            time_val_pairs = sorted(zip(key_times, key_vals), key=lambda x: x[0])

            prev_val = None
            next_val = None
            init_curr_val = None

            for t, v in time_val_pairs:
                if t < current_time:
                    prev_val = v
                elif t > current_time:
                    if next_val is None:
                        next_val = v
                elif t == current_time:
                    init_curr_val = v

            plugs = cmds.listConnections(curve, plugs=True) or []

            if init_curr_val is None and plugs:
                try:
                    init_curr_val = cmds.getAttr(plugs[0])
                except Exception:
                    init_curr_val = 0.0

            if prev_val is not None or next_val is not None:
                if prev_val is None: prev_val = next_val
                if next_val is None: next_val = prev_val

                cache[curve] = {
                    "prev_val": prev_val,
                    "next_val": next_val,
                    "init_curr_val": init_curr_val,
                    "plugs": plugs
                }

        return cache

    # ---------------------------------------------------------
    # 1. BLEND TO NEIGHBORS (TW / BN & PUSH-PULL)
    # ---------------------------------------------------------
    @classmethod
    def performBlendToNeighbors(cls, percent=50.0, is_realtime=False, cache=None):
        if not cache:
            cache = cls.get_neighbor_cache()
        if not cache:
            return

        current_time = cmds.currentTime(query=True)

        for curve, data in cache.items():
            prev_val = data["prev_val"]
            next_val = data["next_val"]

            target_val = prev_val + ((next_val - prev_val) * (percent / 100.0))
            
            cmds.setKeyframe(curve, time=(current_time, current_time), value=target_val)
            for plug in data["plugs"]:
                try:
                    cmds.setAttr(plug, target_val)
                except Exception:
                    pass

        cmds.refresh(noWait=True)

    # ---------------------------------------------------------
    # 2. EASE IN / EASE OUT
    # ---------------------------------------------------------
    @classmethod
    def performBlendToEase(cls, percent=50.0, is_realtime=False, cache=None):
        if not cache:
            cache = cls.get_neighbor_cache()
        if not cache:
            return

        current_time = cmds.currentTime(query=True)
        t = percent / 100.0
        eased_t = t * t * (3.0 - 2.0 * t) if 0.0 <= t <= 1.0 else t

        for curve, data in cache.items():
            prev_val = data["prev_val"]
            next_val = data["next_val"]

            target_val = prev_val + ((next_val - prev_val) * eased_t)
            cmds.setKeyframe(curve, time=(current_time, current_time), value=target_val)
            for plug in data["plugs"]:
                try:
                    cmds.setAttr(plug, target_val)
                except Exception:
                    pass

        cmds.refresh(noWait=True)

    # ---------------------------------------------------------
    # 3. BLEND TO DEFAULT
    # ---------------------------------------------------------
    @classmethod
    def performBlendToDefault(cls, percent=50.0, is_realtime=False, cache=None):
        if not cache:
            cache = cls.get_neighbor_cache()
        if not cache:
            return

        current_time = cmds.currentTime(query=True)

        for curve, data in cache.items():
            plugs = data["plugs"]
            init_val = data["init_curr_val"] if data["init_curr_val"] is not None else 0.0

            for plug in plugs:
                attr_name = plug.split(".")[-1]
                default_val = 1.0 if "scale" in attr_name.lower() else 0.0
                target_val = init_val + ((default_val - init_val) * (percent / 100.0))
                
                cmds.setKeyframe(curve, time=(current_time, current_time), value=target_val)
                try:
                    cmds.setAttr(plug, target_val)
                except Exception:
                    pass

        cmds.refresh(noWait=True)

    # ---------------------------------------------------------
    # 4. BLEND TO PREVIOUS / NEXT FRAME
    # ---------------------------------------------------------
    @classmethod
    def performBlendToFrame(cls, percent=50.0, target_neighbor="prev", is_realtime=False, cache=None):
        if not cache:
            cache = cls.get_neighbor_cache()
        if not cache:
            return

        current_time = cmds.currentTime(query=True)

        for curve, data in cache.items():
            target_val = data["prev_val"] if target_neighbor == "prev" else data["next_val"]
            init_val = data["init_curr_val"]

            if init_val is None or target_val is None:
                continue

            res_val = init_val + ((target_val - init_val) * (percent / 100.0))
            cmds.setKeyframe(curve, time=(current_time, current_time), value=res_val)
            for plug in data["plugs"]:
                try:
                    cmds.setAttr(plug, res_val)
                except Exception:
                    pass

        cmds.refresh(noWait=True)


# Global Helper Functions
def get_neighbor_cache():
    return TweenSlider.get_neighbor_cache()

def performBlendToNeighbors(percent=50.0, is_realtime=False, cache=None):
    TweenSlider.performBlendToNeighbors(percent, is_realtime=is_realtime, cache=cache)

def performBlendToEase(percent=50.0, is_realtime=False, cache=None):
    TweenSlider.performBlendToEase(percent, is_realtime=is_realtime, cache=cache)

def performBlendToDefault(percent=50.0, is_realtime=False, cache=None):
    TweenSlider.performBlendToDefault(percent, is_realtime=is_realtime, cache=cache)

def performBlendToFrame(percent=50.0, target_neighbor="prev", is_realtime=False, cache=None):
    TweenSlider.performBlendToFrame(percent, target_neighbor=target_neighbor, is_realtime=is_realtime, cache=cache)