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
# 3) RESET (reset keyable attrs ke default, aman)
#    - skip locked/connected
# =========================================================
def reset_selected(*args):
    sel = cmds.ls(sl=True, long=True) or []
    if not sel:
        cmds.warning("Nothing selected.")
        return

    for obj in sel:
        attrs = cmds.listAttr(obj, k=True) or []
        # buang visibility
        attrs = [a for a in attrs if "visibility" not in a.lower()]

        for a in attrs:
            plug = f"{obj}.{a}"
            if not cmds.objExists(plug):
                continue

            # skip kalau tidak settable
            try:
                if not cmds.getAttr(plug, settable=True):
                    continue
            except Exception:
                continue

            # cari default attr kalau ada
            default_val = None
            try:
                dv = cmds.attributeQuery(a, node=obj, listDefault=True)
                if dv:
                    default_val = dv[0]
            except Exception:
                default_val = None

            try:
                if default_val is not None:
                    cmds.setAttr(plug, default_val)
                else:
                    # fallback umum
                    if a in ("scaleX", "scaleY", "scaleZ"):
                        cmds.setAttr(plug, 1)
                    else:
                        cmds.setAttr(plug, 0)
            except Exception:
                # locked/connected/unsupported
                pass