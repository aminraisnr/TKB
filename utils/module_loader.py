# -*- coding: utf-8 -*-
import os
import sys
import importlib.util
import maya.cmds as cmds

def run_core_script(base_dir, folder_name, main_file=None, func_name=None, *args, **kwargs):
    """Utility untuk meload dan mengeksekusi skrip dari folder core."""
    def wrapper():
        try:
            folder_path = os.path.join(base_dir, "core", folder_name).replace("\\", "/")
            if folder_path not in sys.path:
                sys.path.insert(0, folder_path)
            
            # ... (logika dynamic import milik Anda)
        except Exception as e:
            cmds.warning(f"TKB: Gagal menjalankan {folder_name} -> {e}")
    return wrapper