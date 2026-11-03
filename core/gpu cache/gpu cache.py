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
# 6) GPU Cache (membuat proxy)
#    - select outliner aja 
# =========================================================
def create_gpu_cache(*args):
    import os
    import maya.cmds as cmds

    # SAFE GPU CACHE DIRECTORY (cross OS)
    gc_dir = cmds.internalVar(userTmpDir=True)
    gc_dir = os.path.join(gc_dir, "gpu_cache").replace("\\", "/")
    if not os.path.exists(gc_dir):
        os.makedirs(gc_dir)

    sel = cmds.ls(sl=True, long=True, type="transform") or []
    if not sel:
        cmds.warning("No transform selected for GPU cache.")
        return

    ct = cmds.currentTime(q=True)

    if not cmds.objExists("gpu_caches"):
        cmds.group(em=True, name="gpu_caches")

    created_nodes = []

    for obj in sel:
        # pakai short name agar aman
        short = obj.split("|")[-1]
        name_safe = short.replace(":", "_")

        # export gpuCache (Maya akan bikin file di directory)
        cmds.gpuCache(
            obj,
            startTime=ct,
            endTime=ct,
            optimize=True,
            writeMaterials=True,
            directory=gc_dir,
            fileName=name_safe
        )

        cache_file = os.path.join(gc_dir, name_safe + ".abc").replace("\\", "/")

        # bikin node transform unik (biar gak bentrok)
        node = cmds.createNode("transform", name=name_safe + "_gc#")
        shape = cmds.createNode("gpuCache", name=node + "Shape", parent=node)
        cmds.setAttr(shape + ".cacheFileName", cache_file, type="string")

        cmds.parent(node, "gpu_caches")
        created_nodes.append(node)

    # optional shader debug
    if not cmds.objExists("dup_shader"):
        shader = cmds.shadingNode("blinn", n="dup_shader", asShader=True)
        cmds.setAttr(shader + ".color", 1, 0, 0)

    if created_nodes:
        cmds.select(created_nodes, r=True)
        cmds.hyperShade(assign="dup_shader")

    cmds.refresh()
    cmds.inViewMessage(
        amg="✓ GPU Cache created",
        pos="topCenter",
        fade=True
    )