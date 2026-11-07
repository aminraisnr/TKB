# -*- coding: utf-8 -*-
"""
Maya Launcher Script untuk Mintools (TKB)
Salin kode di bawah ini ke Script Editor Python Maya kamu.
"""
import sys
import importlib
import maya.cmds as cmds

# Pastikan lokasi folder tempat kamu menaruh 'TKB' terdaftar di sistem internal Maya
# Ganti path di bawah ini jika kamu menaruh folder TKB di lokasi kustom
# contoh: sys.path.append("C:/Users/NamaKamu/Documents/maya/scripts")

try:
    import TKB
    import TKB.ui
    
    # Reload modul UI; modul tween dimuat oleh UI saat widget dibuat.
    importlib.reload(TKB.ui)
    importlib.reload(TKB)
    
    # Jalankan Window
    TKB.show_ui()
    print("TKB berhasil dimuat.")
    
except Exception as e:
    cmds.error("Gagal memuat Mintools: {}".format(str(e)))
