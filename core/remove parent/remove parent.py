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
# Remove Parent
# =========================================================
def remove_all_constraints_from_selection(*args): # Tambahkan *args agar aman saat dipanggil UI
    selected_nodes = cmds.ls(selection=True, long=True)
    if not selected_nodes:
        cmds.warning("Pilih minimal satu child control/object terlebih dahulu!")
        return

    removed_count = 0
    for node in selected_nodes:
        child_constraints = cmds.listRelatives(node, type='constraint', fullPath=True) or []
        connected_constraints = cmds.listConnections(node, type='constraint') or []
        all_constraints = list(set(child_constraints + connected_constraints))
        
        if all_constraints:
            for constraint in all_constraints:
                if cmds.objExists(constraint):
                    cmds.delete(constraint)
                    removed_count += 1
                    print(f"Berhasil menghapus constraint: {constraint}")

    print(f"\nSelesai! Total {removed_count} constraint berhasil dihapus.")

# Hapus atau beri komentar (#) pada baris ini agar tidak auto-run saat import:
# remove_all_constraints_from_selection()