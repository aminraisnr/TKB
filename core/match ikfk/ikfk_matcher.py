# -*- coding: utf-8 -*-
# tkb/core/match ikfk/ikfk_matcher.py
import maya.cmds as cmds
import maya.api.OpenMaya as om

def get_namespace_and_side(sel_node):
    """Mendapatkan namespace dan sisi (L/R) dari kontroler yang dipilih."""
    short_name = sel_node.split("|")[-1]
    ns = short_name.rsplit(":", 1)[0] + ":" if ":" in short_name else ""
    clean_name = short_name.split(":")[-1]
    
    side = "L" if clean_name.endswith("_L") else "R" if clean_name.endswith("_R") else None
    return ns, side

def match_ik_to_fk_selected():
    """Snap IK Controller & Pole Vector ke posisi FK saat ini."""
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Pilih salah satu kontroler FK/IK karakter terlebih dahulu!")
        return

    for node in sel:
        ns, side = get_namespace_and_side(node)
        if not side:
            continue
        
        # Mapping kontroler DigiGirl
        fk_wrist = f"{ns}FKWrist_{side}"
        fk_elbow = f"{ns}FKElbow_{side}"
        fk_shoulder = f"{ns}FKShoulder_{side}"
        ik_ctrl = f"{ns}IKHand_{side}"
        pv_ctrl = f"{ns}IKElbow_{side}"
        blend_attr = f"{ns}ArmUI_{side}.FKIKBlend"

        if not cmds.objExists(fk_wrist) or not cmds.objExists(ik_ctrl):
            # Fallback jika penamaan IK Hand berupa IKIKHand / IKHandCtrl
            ik_ctrl = f"{ns}IKWrist_{side}"

        if not cmds.objExists(fk_wrist) or not cmds.objExists(ik_ctrl):
            cmds.warning(f"Tidak menemukan pasangan kontroler IK/FK untuk {node}")
            continue

        # 1. Snap IK Wrist ke FK Wrist
        wrist_mat = cmds.xform(fk_wrist, q=True, ws=True, matrix=True)
        cmds.xform(ik_ctrl, ws=True, matrix=wrist_mat)

        # 2. Hitung posisi Pole Vector
        pos_s = om.MVector(cmds.xform(fk_shoulder, q=True, ws=True, t=True))
        pos_e = om.MVector(cmds.xform(fk_elbow, q=True, ws=True, t=True))
        pos_w = om.MVector(cmds.xform(fk_wrist, q=True, ws=True, t=True))

        line_sw = (pos_w - pos_s).normal()
        v_se = pos_e - pos_s
        proj_pt = pos_s + line_sw * (v_se * line_sw)
        pv_dir = (pos_e - proj_pt).normal()
        pv_pos = pos_e + (pv_dir * 15.0)

        if cmds.objExists(pv_ctrl):
            cmds.xform(pv_ctrl, ws=True, t=[pv_pos.x, pv_pos.y, pv_pos.z])

        # 3. Switch Blend Attribute ke IK
        if cmds.objExists(blend_attr):
            cmds.setAttr(blend_attr, 1.0)

        cmds.inViewMessage(amg=f"<hl>✓ Matched IK to FK ({side})</hl>", pos="topCenter", fade=True)

def match_fk_to_ik_selected():
    """Snap FK Controllers ke posisi IK saat ini."""
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Pilih salah satu kontroler FK/IK karakter terlebih dahulu!")
        return

    for node in sel:
        ns, side = get_namespace_and_side(node)
        if not side:
            continue

        # Driver Joints / IK Joints DigiGirl
        drv_shoulder = f"{ns}ArmDriverShoulder_{side}"
        drv_elbow = f"{ns}ArmDriverElbow_{side}"
        drv_wrist = f"{ns}ArmDriverWrist_{side}"

        fk_shoulder = f"{ns}FKShoulder_{side}"
        fk_elbow = f"{ns}FKElbow_{side}"
        fk_wrist = f"{ns}FKWrist_{side}"
        blend_attr = f"{ns}ArmUI_{side}.FKIKBlend"

        # Snap Rotasi FK ke Joint Driver
        pairs = [(fk_shoulder, drv_shoulder), (fk_elbow, drv_elbow), (fk_wrist, drv_wrist)]
        matched = False
        for fk, drv in pairs:
            if cmds.objExists(fk) and cmds.objExists(drv):
                rot = cmds.xform(drv, q=True, ws=True, ro=True)
                cmds.xform(fk, ws=True, ro=rot)
                matched = True

        if matched:
            if cmds.objExists(blend_attr):
                cmds.setAttr(blend_attr, 0.0)
            cmds.inViewMessage(amg=f"<hl>✓ Matched FK to IK ({side})</hl>", pos="topCenter", fade=True)
        else:
            cmds.warning(f"Gagal mencocokkan FK untuk {side}")

def show_ui():
    """Menampilkan pesan / window sederhana untuk IKFK Matcher."""
    cmds.confirmDialog(
        title="IK/FK Matcher",
        message="Pilih bagian tangan/kaki DigiGirl di viewport, lalu klik kanan tombol IKFK pada toolbar untuk Snap!",
        button=["OK"]
    )