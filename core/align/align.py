# ==========================
# GLOBAL IMPORTS (WAJIB)
# ==========================
import os
import re
import sys
import maya.cmds as cmds
import maya.mel as mel
import traceback

# =========================================================
# 2) ALIGN (semua selection align ke LAST selected)
# =========================================================
def align_to_last(translate=True, rotate=True, scale=False, all_keys=False, *args):
    """
    Meng-align objek-objek yang dipilih ke objek TERAKHIR yang dipilih (target).
    - Jika all_keys=False: Hanya meng-align pada current frame saja.
    - Jika all_keys=True: Meng-align pada semua frame yang memiliki keyframe di objek sumber MAUPUN target.
    """
    sel = cmds.ls(sl=True, long=True) or []
    
    if len(sel) < 2:
        cmds.warning("Pilih minimal 2 objek: Objek yang ingin di-align, lalu Objek Target (terakhir).")
        return

    sources = sel[:-1]
    target = sel[-1]

    if not cmds.ls(target, type="transform"):
        cmds.warning("Objek target (terakhir) harus berupa Transform Node.")
        return

    cmds.undoInfo(openChunk=True, chunkName="AlignToLast")
    
    try:
        attrs = []
        if translate: attrs.extend(["tx", "ty", "tz"])
        if rotate: attrs.extend(["rx", "ry", "rz"])
        if scale: attrs.extend(["sx", "sy", "sz"])

        # LOGIKA MULTI-FRAME (ALL KEYS)
        if all_keys:
            # 1. Cari animCurves dari sumber DAN target agar pergerakan target di tiap frame ikut ter-update
            all_objs = sources + [target]
            anim_curves = cmds.keyframe(all_objs, query=True, name=True) or []
            
            # Jika tidak ada keyframe sama sekali, jalankan single frame
            if not anim_curves:
                _apply_xform(sources, target, translate, rotate, scale)
                for s in sources:
                    cmds.setKeyframe(s, attribute=attrs)
            else:
                # 2. Ambil seluruh daftar frame unik
                key_frames = cmds.keyframe(anim_curves, query=True, timeChange=True) or []
                unique_frames = sorted(list(set([int(round(f)) for f in key_frames])))

                current_frame = cmds.currentTime(q=True)

                # 3. Loop pada setiap frame yang memiliki keyframe
                for frame in unique_frames:
                    cmds.currentTime(frame, edit=True)
                    # Evaluasi scene di frame ini secara aman
                    cmds.dgeval(sources + [target])
                    
                    # Align posisi/rotasi ke target
                    _apply_xform(sources, target, translate, rotate, scale)
                    
                    # Set keyframe pada objek sumber di frame tersebut
                    for s in sources:
                        cmds.setKeyframe(s, attribute=attrs)

                # Kembalikan time slider ke frame awal
                cmds.currentTime(current_frame, edit=True)
            
        else:
            # LOGIKA SINGLE FRAME (Frame Aktif Saja)
            _apply_xform(sources, target, translate, rotate, scale)
            for s in sources:
                cmds.setKeyframe(s, attribute=attrs)

        cmds.select(sources, replace=True)

    except Exception as e:
        cmds.warning(f"Gagal melakukan align: {e}")
        
    finally:
        cmds.undoInfo(closeChunk=True)


def _apply_xform(sources, target, translate, rotate, scale):
    """Helper internal untuk eksekusi xform World Space."""
    t_pos = cmds.xform(target, q=True, ws=True, t=True)
    t_rot = cmds.xform(target, q=True, ws=True, ro=True)
    t_scl = cmds.xform(target, q=True, r=True, s=True)

    for s in sources:
        try:
            if translate:
                cmds.xform(s, ws=True, t=t_pos)
            if rotate:
                cmds.xform(s, ws=True, ro=t_rot)
            if scale:
                cmds.xform(s, r=True, s=t_scl)
        except Exception:
            pass