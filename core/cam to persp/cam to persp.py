# ==========================
# GLOBAL IMPORTS (WAJIB)
# ==========================
import os
import re
import sys
import maya.cmds as cmds  # <--- Ganti 'mc' menjadi 'cmds'
import maya.cmds as mc    # (opsional) simpan ini jika ada fungsi yang pakai mc
import maya.mel as mel
import traceback

    # =========================================================
    # 9) cam to persp
    #    - select outliner
    # =========================================================
def cam_to_persp_self_test(*args):
    cam_ctrl = "rigging_viewtool_camera_df_hig_vr006:Cam_World_Ctrl"
    cam_ctrl = "CineCameraActor:world_ctl"
    persp = "persp"

    if not cmds.objExists(cam_ctrl):
        cmds.confirmDialog(
            title="Confirm",
            message="Cam trajectory ctrl tidak ditemukan:\n{}".format(cam_ctrl),
            button=["ok"]
        )
        return

    if not cmds.objExists(persp):
        cmds.confirmDialog(
            title="Confirm",
            message="Camera persp tidak ditemukan.",
            button=["ok"]
        )
        return

    pos = cmds.xform(persp, ws=True, q=True, t=True)
    rot = cmds.xform(persp, ws=True, q=True, ro=True)

    cmds.xform(cam_ctrl, ws=True, t=pos)
    cmds.xform(cam_ctrl, ws=True, ro=rot)

    cmds.setKeyframe(cam_ctrl)

    cmds.inViewMessage(
        amg="✓ <hl>Cam_World_Ctrl</hl> snapped to <hl>persp</hl>",
        pos="topCenter",
        fade=True
    )