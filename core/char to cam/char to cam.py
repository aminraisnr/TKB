import os
import re
import sys
import maya.cmds as cmds  # <--- Ganti 'mc' menjadi 'cmds'
import maya.cmds as mc    # (opsional) simpan ini jika ada fungsi yang pakai mc
import maya.mel as mel
import traceback

def char_to_cam_dynamic_test(*args):
    CAM_CTRL = "rigging_viewtool_camera_df_hig_vr006:Cam_Main_ctrl"
    CAM_CTRL = "CineCameraActor:world_ctl"

    if not cmds.objExists(CAM_CTRL):
        cmds.confirmDialog(
            title="Confirm",
            message="Camera trajectory ctrl tidak ditemukan:\n{}".format(CAM_CTRL),
            button=["ok"]
        )
        return

    sel = cmds.ls(sl=True, long=True)
    if not sel:
        cmds.confirmDialog(
            title="Confirm",
            message="Select minimal 1 node dari character.",
            button=["ok"]
        )
        return

    for z in sel:
        leaf = z.split("|")[-1]
        if ":" not in leaf:
            cmds.warning("Skip {} (tidak ada namespace)".format(z))
            continue

        ns = leaf.split(":")[0]

        # FIND SUPER & PLACER (dynamic per character)
        super_candidates = cmds.ls(ns + ":*MainExtra2", type="transform") or []
        placer_candidates = (
        cmds.ls(ns + ":*Root_Ctrl", type="transform") or 
        cmds.ls(ns + ":*MainExtra1", type="transform") or 
        []
        )

        if not super_candidates or not placer_candidates:
            cmds.warning("Skip {} (super/placer ctrl tidak ditemukan)".format(ns))
            continue

        super_ctrl = super_candidates[0]
        placer_ctrl = placer_candidates[0]

        # SNAP SUPER TO CAMERA
        cam_mtx = cmds.xform(CAM_CTRL, ws=True, q=True, m=True)
        cmds.xform(super_ctrl, ws=True, m=cam_mtx)

        # OFFSET VIA PLACER
        cmds.setAttr(placer_ctrl + ".translateZ", -300)
        cmds.setAttr(placer_ctrl + ".translateY", -65)

        offset_mtx = cmds.xform(placer_ctrl, ws=True, q=True, m=True)
        cmds.xform(super_ctrl, ws=True, m=offset_mtx)

        # RESET OFFSET
        cmds.setAttr(placer_ctrl + ".translateZ", 0)
        cmds.setAttr(placer_ctrl + ".translateY", 0)

        # CLEAN ROTATION
        for ax in ("X", "Z"):
            attr = super_ctrl + ".rotate" + ax
            if cmds.objExists(attr):
                cmds.setAttr(attr, 0)

        # KEYFRAME
        cmds.setKeyframe(super_ctrl)

        cmds.inViewMessage(
            amg="✓ <hl>{}</hl> snapped to camera".format(ns),
            pos="topCenter",
            fade=True
        )