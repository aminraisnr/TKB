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
# Bacth Parent
# =========================================================

def batch_parent_constraint_rigs(maintain_offset=True, *args): # Tambahkan *args agar aman dipanggil UI
    """
    Menghubungkan banyak rig/controller referenced menggunakan Parent Constraint.
    
    Cara Pakai:
    1. Pilih semua Child controllers (yang mau mengikuti pergerakan).
    2. Terakhir, pilih Parent controller (objek induk penggeraknya).
    3. Jalankan fungsi ini.
    """
    sel = cmds.ls(selection=True)
    
    if len(sel) < 2:
        cmds.confirmDialog(
            title="Warning",
            message="Pilih minimal 2 objek!\n\n(Pilih semua Child/Rig yang mau di-follow, lalu pilih Parent paling terakhir)",
            button=["OK"]
        )
        return
    
    # Objek terakhir adalah Master Parent
    parent_obj = sel[-1]
    # Objek-objek sebelumnya adalah Children
    children_objs = sel[:-1]
    
    success_count = 0
    
    for child in children_objs:
        try:
            # Gunakan Parent Constraint untuk menggerakkan objek reference
            cmds.parentConstraint(parent_obj, child, maintainOffset=maintain_offset)
            success_count += 1
        except Exception as e:
            cmds.warning(f"Gagal constraint {child} ke {parent_obj}: {str(e)}")
            
    clean_parent_name = parent_obj.split(":")[-1]
    cmds.inViewMessage(
        amg=f"✓ Constrained <hl>{success_count}</hl> referenced objects to <hl>{clean_parent_name}</hl>",
        pos="topCenter",
        fade=True
    )

# Beri komentar (#) di sini agar tidak langsung jalan saat script di-import:
# batch_parent_constraint_rigs(maintain_offset=True)