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
# MOUTH SELECT
# - select mouth / jaw / teeth / tongue ctrls
# - namespace aware & multi-character
# =========================================================
import maya.cmds as cmds

def mouthselect(*args):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Select minimal satu control untuk menentukan namespace.")
        return

    # 1. Kumpulkan semua namespace unik dari objek yang diseleksi
    namespaces = set()
    for obj in sel:
        if ":" in obj:
            # Mengambil seluruh hierarchy namespace (termasuk nested, cth: charA:rig:)
            ns = ":".join(obj.split(":")[:-1]) + ":"
            namespaces.add(ns)
        else:
            # Jika objek tidak memiliki namespace (root level)
            namespaces.add("")

    # 2. Daftar Kontroler Gabungan
    ctrls = [
        # --- Standard / General Rigs ---
        "L_lower_teeth_Ctrl", "lower_teeth_Ctrl", "C_lower_teeth_Ctrl",
        "jaw_rotation_Ctrl", "R_cornerMouth_Ctrl", "upper_lip_Ctrl",
        "lower_lip_Ctrl", "L_upper_teeth_Ctrl", "L_low_lip_01_Ctrl",
        "mouth_master_Ctrl", "jaw_forward_backward_Ctrl", "low_lip_Ctrl",
        "R_up_lip_Ctrl", "tongue_05_Ctrl", "C_upper_teeth_Ctrl",
        "R_nose_Ctrl", "R_low_lip_01_Ctrl", "L_nose_Ctrl", "nose_Ctrl",
        "jaw_translation_Ctrl", "low_teeth_Ctrl", "R_upper_teeth_Ctrl",
        "tongue_02_Ctrl", "R_up_lip_01_Ctrl", "L_cheek_tweak_Ctrl",
        "L_up_lip_Ctrl", "R_lower_teeth_Ctrl", "tongue_rotation_Ctrl",
        "tongue_03_Ctrl", "uvula_01_Ctrl", "L_low_lip_Ctrl",
        "L_up_lip_01_Ctrl", "R_cheek_tweak_Ctrl", "tongue_01_Ctrl",
        "tongue_up_down_Ctrl", "tongue_04_Ctrl", "L_cornerMouth_Ctrl",
        "upper_teeth_Ctrl", "mouth_blend_Ctrl", "uvula_02_Ctrl",
        "up_teeth_Ctrl", "phoneme_blend_Ctrl", "R_low_lip_Ctrl",
        "up_lip_Ctrl", "jaw_Ctrl",

        # --- Tyler Full Mouth Case ---
        "NoseSide_L", "cornerLip_L", "NoseCorner_R", "upperLipC_R",
        "lowerLip_L", "lowerLipA_L", "FrownBulge_L", "Nose_M",
        "Jaw_M", "Lip_L", "NoseUnder_M", "Tongue2_M",
        "lowerLip_R", "Tongue0_M", "ctrlMouth_M", "Cheek_L",
        "upperLip_M", "upperLip_R", "ctrlMouthCorner_R", "upperLipB_L",
        "Nostril_R", "ctrlEmotions_M", "SmilePull_L", "ctrlLips_M",
        "lowerLipC_R", "ctrlPhonemes_M", "lowerTeeth_M", "upperLipB_R",
        "upperLip_L", "SmileBulge_R", "ctrlMouthCorner_L", "CheekBone_L",
        "NoseCorner_L", "lowerLipC_L", "upperLipA_R", "Tongue3_M",
        "upperLipA_L", "SmilePull_R", "Nostril_L", "CheekBone_R",
        "NoseBridge_M", "Tongue1_M", "NoseRegion_M", "LipRegion_M",
        "Lip_R", "upperTeeth_M", "upperLipC_L", "NoseCrease_M",
        "lowerLip_M", "lowerLipB_R", "ctrlARKit_M", "SmileBulge_L",
        "ChinCrease_M", "NoseSide_R", "FrownBulge_R", "cornerLip_R",
        "Cheek_R", "lowerLipB_L", "lowerLipA_R",
        "ctrlNose_L", "ctrlNose_R", "ctrlCheek_R", "ctrlCheek_L",

        # --- Tyler Mouth Secondary (Jnt_ctrl) ---
        "M_Mouth_Sec_Dn_Jnt_ctrl", "L_Mouth_Sec_Up_01_Jnt_ctrl", 
        "L_Mouth_Sec_Jnt_ctrl", "R_Mouth_Sec_Up_01_Jnt_ctrl", 
        "L_Mouth_Sec_Dn_00_Jnt_ctrl", "L_Mouth_Sec_Up_00_Jnt_ctrl", 
        "M_Mouth_Sec_Up_Jnt_ctrl", "R_Mouth_Sec_Dn_00_Jnt_ctrl", 
        "R_Mouth_Sec_Dn_01_Jnt_ctrl", "R_Mouth_Sec_Up_00_Jnt_ctrl", 
        "L_Mouth_Sec_Dn_01_Jnt_ctrl", "R_Mouth_Sec_Jnt_ctrl"
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
        print(f"# Berhasil memilih {len(found)} mouth controls dari {len(namespaces)} karakter/namespace.")
    else:
        cmds.warning("Mouth controls tidak ditemukan pada namespace yang diseleksi.")