# -*- coding: utf-8 -*-
import maya.cmds as cmds

class AdvancedTweener(object):
    def __init__(self):
        self.stored_states = {}

    def capture_initial_state(self):
        """Menyimpan nilai awal sebelum slider digeser untuk performa cepat tanpa lag."""
        self.stored_states.clear()
        selected_objects = cmds.ls(sl=True)
        if not selected_objects:
            return False
            
        current_time = cmds.currentTime(query=True)
        
        for obj in selected_objects:
            anim_attributes = cmds.listAnimatable(obj)
            if not anim_attributes:
                continue
                
            for attr in anim_attributes:
                keyframes = cmds.keyframe(attr, query=True, timeChange=True)
                if not keyframes or len(keyframes) < 2:
                    continue
                    
                prev_keys = [k for k in keyframes if k < current_time]
                next_keys = [k for k in keyframes if k > current_time]
                
                if not prev_keys or not next_keys:
                    continue 
                    
                prev_key = max(prev_keys)
                next_key = min(next_keys)
                
                val_prev = cmds.keyframe(attr, time=(prev_key,), query=True, valueChange=True)[0]
                val_next = cmds.keyframe(attr, time=(next_key,), query=True, valueChange=True)[0]
                
                has_current_key = current_time in keyframes
                val_current = cmds.keyframe(attr, time=(current_time,), query=True, valueChange=True)[0] if has_current_key else cmds.getAttr(attr)
                
                self.stored_states[attr] = {
                    "prev_val": val_prev,
                    "next_val": val_next,
                    "initial_val": val_current,
                    "has_key": has_current_key
                }
        return bool(self.stored_states)

    def apply_tween(self, percentage):
        """Menghitung nilai interpolasi linear (Lerp) termasuk Overshoot (-150% s/d 150%)."""
        if not self.stored_states:
            return
            
        bias = (percentage + 100) / 200.0
        
        for attr, data in self.stored_states.items():
            v_prev = data["prev_val"]
            v_next = data["next_val"]
            
            # Rumus Lerp pendukung Overshoot
            new_value = v_prev + (v_next - v_prev) * bias
            cmds.setAttr(attr, new_value)

    def bake_keyframe(self):
        """Mengunci nilai akhir ke dalam timeline Maya saat slider dilepas."""
        if not self.stored_states:
            return
            
        current_time = cmds.currentTime(query=True)
        
        # Membuka blok Undo di Maya
        cmds.undoInfo(openChunk=True, chunkName="MintoolsTweenBake")
        try:
            for attr in self.stored_states.keys():
                cmds.setKeyframe(attr, time=(current_time,))
        finally:
            cmds.undoInfo(closeChunk=True)
            self.stored_states.clear()
