# -*- coding: utf-8 -*-
"""
Maya Launcher Script untuk Mintools (TKB)
Salin kode di bawah ini ke Script Editor Python Maya kamu.
"""
import sys
import maya.cmds as cmds

# Pastikan lokasi folder tempat kamu menaruh 'TKB' terdaftar di sistem internal Maya
# Ganti path di bawah ini jika kamu menaruh folder TKB di lokasi kustom
# contoh: sys.path.append("C:/Users/NamaKamu/Documents/maya/scripts")

try:
    import TKB
    from importlib import reload
    
    # Lakukan reload paksa agar setiap perubahan kode di komputer langsung terbaca oleh Maya
    reload(TKB.core.tweener)
    reload(TKB.ui)
    reload(TKB)
    
    # Jalankan Window
    TKB.show_ui()
    print("Mintools: Tween Machine berhasil dimuat.")
    
except Exception as e:
    cmds.error("Gagal memuat Mintools: {}".format(str(e)))
