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
# 10) MATA SELECT
#    - select eye / brow / ear ctrls (namespace aware & multi-character)
# =========================================================
import maya.cmds as cmds

def eyeselect(*args):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Select minimal satu control untuk menentukan namespace.")
        return

    # 1. Kumpulkan semua namespace unik dari objek yang diseleksi
    namespaces = set()
    for obj in sel:
        if ":" in obj:
            # Mengambil semua namespace termasuk nested namespace (cth: charA:rig:)
            ns = ":".join(obj.split(":")[:-1]) + ":"
            namespaces.add(ns)
        else:
            # Jika objek tidak memiliki namespace (root level)
            namespaces.add("")

    # 2. Daftar Kontroler Lengkap (Standard + Full Tyler Case)
    ctrls = [
        # --- Tyler Full Eye & Brow List ---
        "lowerLid4_L", "AimEye_L", "innerLidOuter_R", "upperLid2_R", "Pupil_R", 
        "EyeBrowInner_R", "lowerLid2Outer_R", "lowerLid1Outer_L", "innerLid_R", 
        "upperLid3_L", "outerLid_R", "upperLid2Outer_R", "upperLid3Outer_L", 
        "lowerLidOuter_R", "upperLid4Outer_L", "EyeRegion_R", "lowerLid1_L", 
        "upperLidOuter_L", "lowerLid4_R", "lowerLid_R", "Eye_L", "upperLid4Outer_R", 
        "EyeBrowMid1_R", "upperLid1_R", "upperLid3Outer_R", "lowerLid3_L", 
        "EyeBrowInner_L", "upperLid3_R", "R_eyeMover_Ctrl", "upperLid1_L", 
        "lowerLid2_L", "lowerLid_L", "lowerLid4Outer_R", "upperLid2_L", 
        "EyeBrowMid1_L", "outerLidOuter_L", "lowerLid3Outer_R", "AimEye_R", 
        "lowerLidOuter_L", "upperLid_R", "EyeBrowOuter_R", "EyeBrowOuter_L", 
        "innerLid_L", "Eye_R", "EyeBrowRegion_R", "Nose_ctrl", "lowerLid2Outer_L", 
        "lowerLid1_R", "EyeBrowCenter_M", "upperLidOuter_R", "lowerLid2_R", 
        "outerLidOuter_R", "L_EyeLigth_Jnt_ctrl", "upperLid1Outer_L", "AimEye_M", 
        "Iris_R", "L_eyeMover_Ctrl", "R_EyeLigth_All_ctrl", "upperLid4_L", 
        "lowerLid4Outer_L", "EyeBrowRegion_L", "L_EyeLigth_All_ctrl", "lowerLid3_R", 
        "EyeRegion_L", "upperLid4_R", "upperLid_L", "innerLidOuter_L", "Pupil_L", 
        "upperLid2Outer_L", "Iris_L", "R_EyeLigth_Jnt_ctrl", "lowerLid1Outer_R", 
        "EyeBrowMid2_L", "EyeBrowMid2_R", "lowerLid3Outer_L", "upperLid1Outer_R", 
        "outerLid_L", "ctrlBrow_L", "ctrlBrow_R", "ctrlEye_L", "ctrlEye_R",

        # --- Standard Rigs (Daftar Lama) ---
        "L_eyeLidCornerInn_Ctrl", "R_eye_fk_Ctrl", "L_ear_Ctrl", "R_brow_02_Ctrl", 
        "L_eyeLidCornerOut_Ctrl", "R_brow_04_Ctrl", "L_brow_angry_Ctrl", 
        "L_eyeLidUp_Ctrl", "R_ear_Ctrl", "L_brow_01_Ctrl", "L_eye_fk_Ctrl", 
        "L_upperlash_Tweak_03_Ctrl", "R_brow_01_Ctrl", "L_brow_master_Ctrl", 
        "R_upperlash_Tweak_01_Ctrl", "R_brow_03_Ctrl", "L_brow_02_Ctrl", 
        "L_specular_master_Ctrl", "R_brow_up_down_sad_Ctrl", "R_eyeLidLow_Ctrl", 
        "L_brow_up_down_sad_Ctrl", "R_brow_master_Ctrl", "R_lowerlash_Tweak_01_Ctrl", 
        "L_upperlash_Tweak_02_Ctrl", "L_eyeLidLow_Ctrl", "L_eyeMover_Ctrl", 
        "R_upperlash_Tweak_03_Ctrl", "L_lowerlash_Tweak_01_Ctrl", "brow_blend_Ctrl", 
        "R_eyeMover_Ctrl", "L_upperlash_Tweak_01_Ctrl", "L_brow_03_Ctrl", 
        "R_lowerlash_Tweak_03_Ctrl", "L_lowerlash_Tweak_03_Ctrl", "R_lowerlash_Tweak_02_Ctrl", 
        "R_eyeLidCornerInn_Ctrl", "L_specular_Ctrl", "R_brow_angry_Ctrl", 
        "R_specular_Ctrl", "L_lowerlash_Tweak_02_Ctrl", "L_brow_04_Ctrl", 
        "R_specular_master_Ctrl", "R_eyeLidUp_Ctrl", "R_upperlash_Tweak_02_Ctrl", 
        "eye_blend_Ctrl", "R_eyeLidCornerOut_Ctrl", "global_blend_Ctrl", 
        "eyeMaster_Ctrl", "R_eye_Ctrl", "L_eye_Ctrl"
    ]

    # 3. Filter objek untuk SEMUA namespace yang ditemukan
    found = []
    for ns in namespaces:
        for c in ctrls:
            full_path = ns + c
            if cmds.objExists(full_path):
                found.append(full_path)

    # 4. Eksekusi Seleksi
    if found:
        cmds.select(found, r=True)
        print(f"# Berhasil memilih {len(found)} eye controls dari {len(namespaces)} karakter/namespace.")
    else:
        cmds.warning("Eye controls tidak ditemukan pada namespace yang diseleksi.")