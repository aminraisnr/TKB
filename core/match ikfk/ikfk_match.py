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
        
        fk_wrist = f"{ns}FKWrist_{side}"
        fk_elbow = f"{ns}FKElbow_{side}"
        fk_shoulder = f"{ns}FKShoulder_{side}"
        
        # Opsi kandidat nama IK Control
        ik_ctrl = f"{ns}IKHand_{side}"
        if not cmds.objExists(ik_ctrl):
            ik_ctrl = f"{ns}IKWrist_{side}"
        if not cmds.objExists(ik_ctrl):
            ik_ctrl = f"{ns}IKArm_{side}"

        pv_ctrl = f"{ns}IKElbow_{side}"
        if not cmds.objExists(pv_ctrl):
            pv_ctrl = f"{ns}IKPoleVector_{side}"

        ui_ctrl = f"{ns}FKIKArm_{side}"
        blend_attr = f"{ui_ctrl}.FKIKBlend"

        if not cmds.objExists(fk_wrist) or not cmds.objExists(ik_ctrl):
            cmds.warning(f"Tidak menemukan pasangan kontroler IK/FK untuk {node}")
            continue

        # 1. Snap IK Hand ke FK Wrist (World Matrix)
        wrist_mat = cmds.xform(fk_wrist, q=True, ws=True, matrix=True)
        cmds.xform(ik_ctrl, ws=True, matrix=wrist_mat)

        # 2. Hitung & Snap posisi Pole Vector
        if cmds.objExists(pv_ctrl) and cmds.objExists(fk_shoulder) and cmds.objExists(fk_elbow):
            pos_s = om.MVector(cmds.xform(fk_shoulder, q=True, ws=True, t=True))
            pos_e = om.MVector(cmds.xform(fk_elbow, q=True, ws=True, t=True))
            pos_w = om.MVector(cmds.xform(fk_wrist, q=True, ws=True, t=True))

            line_sw = (pos_w - pos_s).normal()
            v_se = pos_e - pos_s
            proj_pt = pos_s + line_sw * (v_se * line_sw)
            pv_dir = (pos_e - proj_pt).normal()
            pv_pos = pos_e + (pv_dir * 15.0)

            cmds.xform(pv_ctrl, ws=True, t=[pv_pos.x, pv_pos.y, pv_pos.z])

        # 3. Switch Blend Attribute ke IK (Nilai 10)
        if cmds.objExists(blend_attr):
            cmds.setAttr(blend_attr, 10.0)

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

        fk_shoulder = f"{ns}FKShoulder_{side}"
        fk_elbow = f"{ns}FKElbow_{side}"
        fk_wrist = f"{ns}FKWrist_{side}"
        ui_ctrl = f"{ns}FKIKArm_{side}"
        blend_attr = f"{ui_ctrl}.FKIKBlend"

        # Cari joint deformasi/driver tempat IK menempel saat ini
        drv_candidates = [
            (fk_shoulder, [f"{ns}ArmDriverShoulder_{side}", f"{ns}ArmShoulder_JNT_{side}", f"{ns}Shoulder_JNT_{side}"]),
            (fk_elbow, [f"{ns}ArmDriverElbow_{side}", f"{ns}ArmElbow_JNT_{side}", f"{ns}Elbow_JNT_{side}"]),
            (fk_wrist, [f"{ns}ArmDriverWrist_{side}", f"{ns}ArmWrist_JNT_{side}", f"{ns}Wrist_JNT_{side}"])
        ]

        matched = False
        for fk_ctrl, target_list in drv_candidates:
            if not cmds.objExists(fk_ctrl):
                continue
            
            target_jnt = None
            for candidate in target_list:
                if cmds.objExists(candidate):
                    target_jnt = candidate
                    break
            
            # Jika tidak ada joint driver terdaftar, cari joint di namespace yang paling cocok
            if not target_jnt:
                match_type = "Shoulder" if "Shoulder" in fk_ctrl else "Elbow" if "Elbow" in fk_ctrl else "Wrist"
                found = [j for j in cmds.ls(f"{ns}*", type="joint") if match_type in j and side in j]
                if found:
                    target_jnt = found[0]

            if target_jnt:
                rot = cmds.xform(target_jnt, q=True, ws=True, ro=True)
                cmds.xform(fk_ctrl, ws=True, ro=rot)
                matched = True

        if matched:
            # Switch Blend Attribute ke FK (Nilai 0)
            if cmds.objExists(blend_attr):
                cmds.setAttr(blend_attr, 0.0)
            cmds.inViewMessage(amg=f"<hl>✓ Matched FK to IK ({side})</hl>", pos="topCenter", fade=True)
        else:
            cmds.warning(f"Gagal mencocokkan FK untuk {side}. Tidak menemukan joint driver/deformasi yang sesuai.")

def show_ui():
    """Menampilkan Dialog Petunjuk Penggunaan IKFK Matcher."""
    cmds.confirmDialog(
        title="IK/FK Matcher",
        message="Pilih kontroler tangan DigiGirl (misal FKShoulder_L atau FKIKArm_L), lalu klik kanan tombol IKFK pada toolbar untuk Snap!",
        button=["OK"]
    )