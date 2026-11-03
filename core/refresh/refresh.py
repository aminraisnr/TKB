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
# refresh_evaluation_mode
# =========================================================
def refresh_evaluation_mode(*args):
    """
    Siklus Kilat Penyembuh Bug Viewport: Parallel -> Off -> Parallel.
    Menggunakan perintah murni mode string agar kompetibel dengan Maya 2022.
    """
    try:
        # 1. Reset memori Viewport 2.0 (OGS) untuk ngerontokin mesh/rig patah
        mel.eval("ogs -reset;")
        
        # 2. Siklus kilat: Matikan (off) lalu kembalikan ke Parallel
        # Ini padanan Python dari: evaluationManager -mode "off";
        mc.evaluationManager(mode="off")
        
        # Ini padanan Python dari: evaluationManager -mode parallel;
        mc.evaluationManager(mode="parallel")
        
        print("// TKB: Viewport Reset & Cycle Completed (Off -> Parallel).")
        
        # 3. Notifikasi kuning di tengah Viewport Maya
        mc.inViewMessage(amg='Viewport & Parallel Graph <color=yellow>Successfully Refreshed</color>!', pos='topCenter', fade=True)
        
    except Exception as e:
        mc.warning("TKB: Gagal refresh evaluation mode -> {}".format(e))