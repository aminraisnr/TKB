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
# 8) Smart Select / Hierarchy Select
# =========================================================
import re
import maya.cmds as cmds


def _is_ctrl_transform(x):
    """Controller = transform yang punya shape nurbsCurve / nurbsSurface / locator. Mesh skip."""
    if not cmds.objExists(x):
        return False

    shapes = cmds.listRelatives(x, shapes=True, noIntermediate=True, fullPath=True) or []
    stypes = {cmds.nodeType(s) for s in shapes}

    if "mesh" in stypes:
        return False

    if ("nurbsCurve" in stypes) or ("nurbsSurface" in stypes) or ("locator" in stypes):
        return True

    short = x.split("|")[-1].split(":")[-1].upper()
    return ("CTRL" in short) or ("CTL" in short)


def _get_namespace_prefix(node):
    leaf = node.split("|")[-1]
    return (leaf.rsplit(":", 1)[0] + ":") if ":" in leaf else ""


def _to_transform_if_shape(node):
    """Kalau yang kepilih shape, naik ke parent transform."""
    if cmds.nodeType(node) in ("mesh", "nurbsCurve", "nurbsSurface", "locator"):
        p = cmds.listRelatives(node, parent=True, fullPath=True) or []
        if p:
            return p[0]
    return node


def select_ctrl_hierarchy(*args):
    """Select semua controller di bawah SEMUA objek yang sedang dipilih."""
    sel = cmds.ls(sl=True, long=True) or []
    if not sel:
        cmds.warning("Select 1 atau lebih controller/root dulu.")
        return

    all_ctrls = []
    
    for each_node in sel:
        node = _to_transform_if_shape(each_node)
        # Ambil hierarki di bawah node ini
        cand = [node] + (cmds.listRelatives(node, ad=True, type="transform", fullPath=True) or [])
        ctrls = [x for x in cand if _is_ctrl_transform(x)]
        all_ctrls.extend(ctrls)

    # Hilangkan duplikat jika ada hierarki yang tumpang tindih
    final_ctrls = sorted(set(all_ctrls))

    if not final_ctrls:
        cmds.warning("Tidak menemukan controller di selection ini.")
        return

    cmds.select(final_ctrls, r=True)
    cmds.inViewMessage(
        amg="✓ Selected <hl>{}</hl> ctrls (multiple hierarchy)".format(len(final_ctrls)),
        pos="topCenter",
        fade=True
    )


def select_ctrl_by_token(*args):
    """
    Limb selector (FK + IK) untuk rig kamu.
    - FK arm:  clavicleTrans_Ctrl + upArm/elbow/wrist_fk_Ctrl  (tanpa fingers)
    - FK fingers: thumb/index/middle/ring/pinky (Base/Mid/Top/Tip)_fk_Ctrl
    - FK leg:  upLeg/knee/ankle/ball_fk_Ctrl  (ball ikut leg)
    - IK arm:  clavicleTrans_Ctrl + arm_ik/shoulder_ik/elbow_pv_Ctrl
    - IK leg:  heel_ik/knee_pv/hip_Ctrl
    """
    sel = cmds.ls(sl=True, long=True) or []
    if not sel:
        cmds.warning("Select 1 controller dulu.")
        return

    node = _to_transform_if_shape(sel[0])
    leaf = node.split("|")[-1]
    short = leaf.split(":")[-1]              # tanpa namespace
    ns_prefix = _get_namespace_prefix(node)

    m = re.match(r'([LR])_', short, re.IGNORECASE)
    if not m:
        cmds.warning("Nama ctrl tidak ada prefix L_ / R_.")
        return
    side = m.group(1).upper()

    # --- FK patterns ---
    # clavicleTrans itu BUKAN fk_Ctrl, jadi dipisah
    pat_arm_fk = re.compile(
        rf'^{side}_(?:clavicleTrans_Ctrl|(?:upArm|elbow|wrist)_fk_Ctrl)$',
        re.IGNORECASE
    )

    pat_fingers_fk = re.compile(
        rf'^{side}_(?:thumb|index|middle|ring|pinky)(?:Base|Mid|Top|Tip)_fk_Ctrl$',
        re.IGNORECASE
    )

    pat_leg_fk = re.compile(
        rf'^{side}_(?:upLeg|knee|ankle|ball)_fk_Ctrl$',
        re.IGNORECASE
    )

    # --- IK patterns ---
    pat_arm_ik = re.compile(
        rf'^{side}_(?:clavicleTrans_Ctrl|arm_ik_Ctrl|shoulder_ik_Ctrl|elbow_pv_Ctrl)$',
        re.IGNORECASE
    )

    pat_leg_ik = re.compile(
        rf'^{side}_(?:heel_ik_Ctrl|knee_pv_Ctrl|hip_Ctrl)$',
        re.IGNORECASE
    )

    # --- tentukan mode dari NAMA selection (anti ketuker) ---
    if pat_fingers_fk.match(short):
        pat = pat_fingers_fk
        label = "fingers FK"
    elif pat_arm_fk.match(short):
        pat = pat_arm_fk
        label = "arm FK"
    elif pat_leg_fk.match(short):
        pat = pat_leg_fk
        label = "leg FK"
    elif pat_arm_ik.match(short):
        pat = pat_arm_ik
        label = "arm IK"
    elif pat_leg_ik.match(short):
        pat = pat_leg_ik
        label = "leg IK"
    else:
        cmds.warning("Ctrl ini belum ke-cover pattern rig kamu: {}".format(short))
        return

    # scan dalam namespace yang sama
    candidates = cmds.ls(ns_prefix + "*", type="transform", long=True) or []
    ctrls = []
    for x in candidates:
        name = x.split("|")[-1].split(":")[-1]
        if pat.match(name) and _is_ctrl_transform(x):
            ctrls.append(x)

    ctrls = sorted(set(ctrls))
    if not ctrls:
        cmds.warning("Tidak ada {} ctrl ketemu untuk side {}.".format(label, side))
        return

    cmds.select(ctrls, r=True)
    cmds.inViewMessage(
        amg="✓ Selected <hl>{}</hl> {} {}".format(len(ctrls), side, label),
        pos="topCenter",
        fade=True
    )


def smart_select(*args):
    """
    Smart select yang mendukung banyak objek sekaligus.
    """
    sel = cmds.ls(sl=True, long=True) or []
    if not sel:
        cmds.warning("Select 1 atau lebih controller dulu.")
        return

    final_to_select = []

    # Regex patterns
    body_pat = re.compile(r'^(cog|hip|spine(?:Low|Mid|High)?)_Ctrl$', re.IGNORECASE)
    head_pat = re.compile(r'^(neck|head)_Ctrl$', re.IGNORECASE)

    for each_node in sel:
        node = _to_transform_if_shape(each_node)
        leaf = node.split("|")[-1]
        short = leaf.split(":")[-1]
        ns_prefix = _get_namespace_prefix(node)

        # CASE 1: BODY
        if body_pat.match(short):
            candidates = cmds.ls(ns_prefix + "*", type="transform", long=True) or []
            final_to_select.extend([x for x in candidates if body_pat.match(x.split("|")[-1].split(":")[-1]) and _is_ctrl_transform(x)])

        # CASE 2: HEAD
        elif head_pat.match(short):
            candidates = cmds.ls(ns_prefix + "*", type="transform", long=True) or []
            final_to_select.extend([x for x in candidates if head_pat.match(x.split("|")[-1].split(":")[-1]) and _is_ctrl_transform(x)])

        # CASE 3: LIMB (FK/IK/PV/hip)
        elif (re.match(r'([LR])_', short, re.IGNORECASE) and 
             (re.search(r'_(fk|ik|pv)_Ctrl$', short, re.IGNORECASE) or 
              re.search(r'_(hip|clavicleTrans)_Ctrl$', short, re.IGNORECASE))):
            
            # Kita panggil fungsi select_by_token tapi ambil return-nya (modifikasi diperlukan di fungsi aslinya)
            # Untuk simplifikasi di sini, kita kumpulkan manual atau panggil fungsinya dengan seleksi sementara
            cmds.select(node, r=True)
            select_ctrl_by_token()
            final_to_select.extend(cmds.ls(sl=True, long=True))

        # CASE 4: FALLBACK (Hierarchy)
        else:
            cand = [node] + (cmds.listRelatives(node, ad=True, type="transform", fullPath=True) or [])
            final_to_select.extend([x for x in cand if _is_ctrl_transform(x)])

    # Final eksekusi
    if final_to_select:
        final_to_select = sorted(set(final_to_select))
        cmds.select(final_to_select, r=True)
        cmds.inViewMessage(amg="✓ Smart Selected <hl>{}</hl> objects".format(len(final_to_select)), pos="topCenter", fade=True)

    