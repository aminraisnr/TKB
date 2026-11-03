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
# 14) MOTION TRAIL (FIXED LISTHISTORY TYPE FLAG ERROR)
# =========================================================
def create_motion_trail():
    """
    Membuat Motion Trail pada objek yang dipilih untuk seluruh Playback Range.
    Menghapus MotionTrailHandle lama pada objek agar tidak menumpuk di Outliner.
    """
    selection = cmds.ls(selection=True)
    if not selection:
        cmds.warning("Pilih minimal satu objek untuk membuat Motion Trail.")
        return False

    # 1. Coba panggil modul internal animBot jika tersedia
    try:
        import animBot.motionTrail.motionTrailDrawing as mt
        mt.MotionTrail.createMotionTrail_click()
        return True
    except Exception:
        pass

    # 2. Fallback: Gunakan Motion Trail bawaan Maya
    start_frame = cmds.playbackOptions(q=True, minTime=True)
    end_frame = cmds.playbackOptions(q=True, maxTime=True)

    for obj in selection:
        # Cari dan hapus Motion Trail & Handle lama yang terhubung ke objek ini
        _delete_obj_motion_trails(obj)

        # Buat Motion Trail baru
        cmds.snapshot(
            obj,
            motionTrail=True,
            startTime=start_frame,
            endTime=end_frame,
            increment=1
        )

    cmds.inViewMessage(
        amg=f"✓ Motion Trail Dibuat ({int(start_frame)} - {int(end_frame)})",
        pos="topCenter",
        fade=True
    )
    return True


def _get_obj_motion_trails(obj):
    """
    Helper function aman untuk mendapatkan daftar node motionTrail pada objek.
    """
    history = cmds.listHistory(obj) or []
    history_trails = [node for node in history if cmds.nodeType(node) == "motionTrail"]
    conn_trails = cmds.listConnections(obj, type="motionTrail") or []
    return list(set(history_trails + conn_trails))


def _delete_obj_motion_trails(obj):
    """
    Helper function untuk menghapus node motionTrail beserta Handle transform-nya dari objek.
    """
    all_obj_trails = _get_obj_motion_trails(obj)

    nodes_to_delete = set()
    for tr in all_obj_trails:
        nodes_to_delete.add(tr)
        # Cari node transform (handle) yang terhubung ke motionTrail
        handles = cmds.listConnections(tr, type="transform") or []
        for h in handles:
            if "motionTrail" in h:
                nodes_to_delete.add(h)
        
        # Cari parent dari motionTrailShape jika ada
        shapes = cmds.listConnections(tr, type="motionTrailShape") or []
        for s in shapes:
            nodes_to_delete.add(s)
            parents = cmds.listRelatives(s, parent=True) or []
            nodes_to_delete.update(parents)

    if nodes_to_delete:
        cmds.delete(list(nodes_to_delete))


def remove_motion_trail():
    """
    Menghapus Motion Trail beserta Handle-nya pada objek yang dipilih.
    """
    selection = cmds.ls(selection=True)
    if not selection:
        cmds.warning("Pilih objek yang memiliki Motion Trail untuk dihapus.")
        return False

    # Panggil animBot jika ada
    try:
        import animBot.motionTrail.motionTrailDrawing as mt
        mt.MotionTrail.removeMotionTrail_click()
        return True
    except Exception:
        pass

    deleted = False
    for obj in selection:
        trails = _get_obj_motion_trails(obj)
        if trails:
            _delete_obj_motion_trails(obj)
            deleted = True

    if deleted:
        cmds.inViewMessage(amg="✓ Motion Trail Objek Terpilih Dihapus", pos="topCenter", fade=True)
    else:
        cmds.warning("Tidak ditemukan Motion Trail pada objek yang dipilih.")

    return deleted


def clear_all_trails():
    """
    Menghapus seluruh node Motion Trail dan MotionTrailHandle di scene.
    """
    # 1. Cari node animBot jika ada
    anim_bot_trails = cmds.ls(type="animBotMotionTrail") or []
    if anim_bot_trails:
        cmds.delete(anim_bot_trails)

    # 2. Cari semua node motionTrail & motionTrailShape bawaan Maya
    all_trails = cmds.ls(type="motionTrail") or []
    all_shapes = cmds.ls(type="motionTrailShape") or []

    # 3. Cari transform handle dengan filter aman
    all_transforms = cmds.ls(type="transform") or []
    all_handles = [t for t in all_transforms if "motionTrail" in t and "Handle" in t]

    nodes_to_delete = list(set(all_handles + all_trails + all_shapes))

    if nodes_to_delete:
        cmds.delete(nodes_to_delete)
        cmds.inViewMessage(amg="✓ Semua Motion Trail Dihapus", pos="topCenter", fade=True)
        return True
    else:
        cmds.warning("Tidak ditemukan Motion Trail di dalam scene.")
        return False