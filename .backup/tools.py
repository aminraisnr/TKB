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
# 1) SELECT ALL
# =========================================================

def select_all_multi(include_no_shape_ctrl=True, only_selectable=True, exclude_groups=True):
    """
    Menyeleksi seluruh kontroler dari semua karakter yang bagian tubuhnya sedang dipilih.
    Mendukung banyak karakter sekaligus (Multi-Namespace).
    """
    # 1. Ambil seleksi awal
    initial_sel = cmds.ls(sl=True, long=True) or []
    
    # Gunakan warning agar tidak muncul pop-up mengganggu saat script baru di-load
    if not initial_sel:
        cmds.warning("Pilih minimal satu objek/mesh dari tiap karakter!")
        return

    all_controls = []
    processed_namespaces = set()

    # 2. Loop melalui setiap objek yang dipilih user
    for node in initial_sel:
        # Cari Namespace dari objek ini
        short_name = node.split("|")[-1]
        ns = short_name.split(":")[0] if ":" in short_name else ""
        
        # Penanda unik untuk membedakan karakter (terutama yang tanpa namespace)
        ns_key = ns if ns else "root_node_" + node
        
        # JANGAN proses ulang jika kita sudah mengambil semua kontroler dari karakter ini
        if ns_key in processed_namespaces:
            continue
        processed_namespaces.add(ns_key)

        # 3. Cari kandidat objek dalam lingkup karakter tersebut
        if ns:
            # Cari semua objek di dalam namespace yang sama
            candidates = cmds.ls(ns + ":*", type="transform", long=True) or []
        else:
            # Jika karakter berada di root (tanpa namespace), ambil seluruh hirarki
            candidates = cmds.listRelatives(node, ad=True, type="transform", f=True) or []
            candidates.append(node)

        # 4. Filter kandidat berdasarkan kriteria kontroler
        for t in candidates:
            # Ambil nama pendek tanpa namespace untuk pengecekan kata kunci
            name_short = t.split("|")[-1].split(":")[-1].upper()
            
            # Filter A: Abaikan Group/Null/Offset
            if exclude_groups:
                if any(x in name_short for x in ["_GRP", "GRP_", "_GROUP", "_ZERO", "_OFFSET", "_SDK", "_SPACE"]):
                    continue

            # Filter B: Hanya ambil yang bisa dipilih (Visible & Not Referenced/Templated)
            if only_selectable:
                try:
                    if not cmds.getAttr(t + ".v"): continue
                    if cmds.getAttr(t + ".overrideEnabled"):
                        if cmds.getAttr(t + ".overrideDisplayType") in (1, 2): continue
                except: pass

            # Filter C: Cek apakah objek ini kontroler (Punya Curve atau Naming 'CTRL')
            shapes = cmds.listRelatives(t, s=True, noIntermediate=True, f=True) or []
            has_curve = any(cmds.nodeType(s) == "nurbsCurve" for s in shapes)
            is_ctrl_name = any(x in name_short for x in ["CTRL", "CTL", "CONTROLLER"])
            
            if has_curve:
                all_controls.append(t)
            elif include_no_shape_ctrl and is_ctrl_name:
                all_controls.append(t)

    # 5. Eksekusi Seleksi Akhir
    if all_controls:
        # Gunakan list(set()) untuk memastikan tidak ada objek yang terduplikasi
        cmds.select(list(set(all_controls)), r=True)
        
        # Berikan feedback di Viewport
        msg = f"✓ Selected {len(all_controls)} controls from {len(processed_namespaces)} character(s)."
        cmds.inViewMessage(amg=f"<hl>{msg}</hl>", pos="topCenter", fade=True)
        print(f"Success: {msg}")
    else:
        cmds.warning("Tidak ditemukan kontroler. Pastikan karakter memiliki 'CTRL' pada namanya atau menggunakan Nurbs Curve.")


# =========================================================
# 2) ALIGN (semua selection align ke LAST selected)
#     - align translate + rotate (world space)
# =========================================================
# TKB/tools.py
import maya.cmds as cmds

def align_to_last(translate=True, rotate=True, scale=False, all_keys=False, *args):
    """
    Meng-align objek-objek yang dipilih ke objek TERAKHIR yang dipilih (target).
    - Jika all_keys=False: Hanya meng-align pada current frame saja.
    - Jika all_keys=True: Hanya meng-align pada frame-frame yang sudah MEMILIKI KEYFRAME (tanpa ter-bake).
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
        # Cek animCurves dari sumber
        anim_curves = cmds.keyframe(sources, query=True, name=True) or []
        
        # LOGIKA MULTI-FRAME (HANYA FRAME BER-KEYFRAME)
        if all_keys and anim_curves:
            # 1. Ambil daftar semua angka frame unik yang sudah ada keyframe-nya
            key_frames = cmds.keyframe(anim_curves, query=True, timeChange=True) or []
            # Hilangkan duplikat frame dan urutkan dari terkecil ke terbesar
            unique_frames = sorted(list(set([int(f) for f in key_frames])))

            current_frame = cmds.currentTime(q=True)

            attrs = []
            if translate: attrs.extend(["tx", "ty", "tz"])
            if rotate: attrs.extend(["rx", "ry", "rz"])
            if scale: attrs.extend(["sx", "sy", "sz"])

            # 2. Iterasi HANYA pada frame-frame yang memiliki keyframe
            for frame in unique_frames:
                cmds.currentTime(frame, edit=True)
                _apply_xform(sources, target, translate, rotate, scale)
                
                # Pasang keyframe khusus pada frame ini saja
                for s in sources:
                    cmds.setKeyframe(s, attribute=attrs)
                    
            cmds.currentTime(current_frame, edit=True)
            
        else:
            # LOGIKA SINGLE FRAME (Frame Aktif Saja)
            _apply_xform(sources, target, translate, rotate, scale)

        cmds.select(sources[0], replace=True)

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


# =========================================================
# 4) NULL (buat empty di posisi selection)
#    - kalau seleksi banyak: buat null per object
# =========================================================
def create_null(*args):
    obj=[str(o) for o in cmds.ls( sl=True,tr=True)]
    for i in obj:
        name=str(i)+"Locator"
        objctrl= cmds.curve(n=name,d=1,p=[(-1,1,1),(-1,1,-1),(1,1,-1),(1,1,1),(-1,1,1),(-1,-1,1),(-1,-1,-1),(-1,1,-1),(-1,1,1),(-1,-1,1),(1,-1,1),(1,1,1),(1,1,-1),(1,-1,-1),(1,-1,1),(1,-1,-1),(-1,-1,-1),],k=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16])
        pos = cmds.xform(str(i), q=True, ws=True, m=True)
        sca = cmds.xform(str(i), q=True, ws=True, s=True)
        #pos = cmds.xform(str(i), q=True, ws=True, translation=True)
        #cmds.move(pos[0], pos[1], pos[2], objctrl)
        cmds.xform(objctrl, ws=True, m=pos)
        cmds.xform(objctrl, ws=True, s=sca)
        cmds.setAttr (objctrl+".overrideEnabled", 1)
        cmds.setAttr(objctrl+".overrideColor", 30)
        cmds.select(objctrl)


# =========================================================
# 5) STEP SNAP (snap keyframes ke grid step)
#    - default step=1 (snap ke frame integer)
# =========================================================
def ss():
    if cmds.window('ss',exists=True):
        cmds.deleteUI('ss',window=True)

    def ssfrwrd(*args):
        krg=cmds.timeControl('timeControl1',q=True,rng=True)
        krglen=len(krg)
        krgns=krg.find(':')
        strtkt=krg[1:krgns]
        strtk=int(strtkt)
        endkt=krg[krgns+1:krglen-1]
        endk=int(endkt)
        endk-=1
        sel=cmds.ls(sl=True)
        sel=sel[0]
        if strtk==endk:
            cmds.error('Start and End range is the same')
        else:
            cmds.currentTime(strtk)
            msel = cmds.xform(sel, ws=True, q=True, ro=True)
            locsel = cmds.xform(sel, ws=True, q=True, t=True)
            cmds.setKeyframe(str(sel))
            while strtk<=endk:
                cmds.xform(sel, ws=True, ro=msel)
                cmds.move(locsel[0], locsel[1], locsel[2], sel)
                cmds.setKeyframe(str(sel))
                strtk+=1
                cmds.currentTime(strtk)
        return ssfrwrd

    def ssreverse(*args):
        krg=cmds.timeControl('timeControl1',q=True,rng=True)
        krglen=len(krg)
        krgns=krg.find(':')
        strtkt=krg[1:krgns]
        strtk=int(strtkt)
        endkt=krg[krgns+1:krglen-1]
        endk=int(endkt)
        endk-=1
        sel=cmds.ls(sl=True)
        sel=sel[0]
        if strtk==endk:
            cmds.error('Start and End range is the same')
        else:
            cmds.currentTime(endk)
            msel = cmds.xform(sel, ws=True, q=True, ro=True)
            locsel = cmds.xform(sel, ws=True, q=True, t=True)
            cmds.setKeyframe(str(sel))
            while endk>=strtk:
                cmds.xform(sel, ws=True, ro=msel)
                cmds.move(locsel[0], locsel[1], locsel[2], sel)
                cmds.setKeyframe(str(sel))
                endk-=1
                cmds.currentTime(endk)
        return ssreverse
    cwin=cmds.window('ss',t='SS 4.0',width=200,s=True)
    cmds.columnLayout(adjustableColumn=True )
    cmds.button(l='SS Forward', c=ssfrwrd,w=200)
    cmds.button(l='SS Reverse', c=ssreverse,w=200)
    cmds.showWindow(cwin)
    cmds.window('ss',e=True, width=200, h=50,  s=True)

# =========================================================
# 6) GPU Cache (membuat proxy)
#    - select ouliner aja 
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

# =========================================================
# 7) POSE2SHELF & POSE2MEL
# =========================================================
import maya.cmds as cmds
import maya.mel as mel

try:
    from PySide2.QtWidgets import QApplication
except ImportError:
    from PySide6.QtWidgets import QApplication


def pose2mel(*args):
    """Mengambil nilai atribut keyable dari objek terpilih 
    dan menyalin perintah setAttr MEL ke Clipboard.
    """
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("Pilih minimal satu objek/control terlebih dahulu!")
        return

    mel_commands = []

    for node in selected:
        keyable_attrs = cmds.listAttr(
            node,
            read=True,
            write=True,
            keyable=True,
            unlocked=True,
            visible=True,
            multi=True,
            scalar=True,
        )
        if not keyable_attrs:
            continue

        for attr in keyable_attrs:
            try:
                val = cmds.getAttr(f"{node}.{attr}")
                if isinstance(val, (int, float)):
                    mel_commands.append(f'catch (`setAttr "{node}.{attr}" {val}`);')
            except Exception:
                continue

    if not mel_commands:
        cmds.warning("Tidak ada atribut keyable yang ditemukan pada objek terpilih.")
        return

    full_text = "\n".join(mel_commands) + "\n"

    # Salin ke Clipboard OS via PySide
    app = QApplication.instance()
    if app:
        clipboard = app.clipboard()
        clipboard.setText(full_text)
        print("// Success: Pose MEL commands copied to Clipboard!\n")
        cmds.inViewMessage(amg="✓ Pose MEL commands <color=yellow>copied to Clipboard</color>!", pos="topCenter", fade=True)
    else:
        cmds.warning("Tidak dapat mengakses QApplication Clipboard.")


def selection2shelf(label="select."):
    """Membuat tombol di Shelf Maya yang menyimpan daftar seleksi objek saat ini."""
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("Nothing is currently selected. No shelf button created, or action taken.")
        return

    safe_shelf_command = ""
    for node in selected:
        safe_shelf_command = f'catch (`select -add "{node}"`);\n' + safe_shelf_command
    safe_shelf_command = "select -cl;\n" + safe_shelf_command

    g_shelf_top_level = mel.eval("$temp =$gShelfTopLevel;")

    if cmds.tabLayout(g_shelf_top_level, exists=True):
        current_shelf = cmds.tabLayout(g_shelf_top_level, query=True, selectTab=True)
        parent_shelf = f"{g_shelf_top_level}|{current_shelf}"

        if not label:
            label = "select."

        # Tambahkan sourceType="mel" agar tombol dibaca sebagai skrip MEL oleh Maya
        cmds.shelfButton(
            parent=parent_shelf,
            enableCommandRepeat=True,
            enable=True,
            width=34,
            height=34,
            manage=True,
            visible=True,
            annotation=label,
            label=label,
            imageOverlayLabel=label,
            image1="aselect.xpm",
            style="iconOnly",
            command=safe_shelf_command,
            sourceType="mel"  # <--- PERBAIKAN DI SINI
        )

        print("\n// Selection commands put into shelf: \n")
        print(safe_shelf_command)
        cmds.inViewMessage(amg="✓ Selection button <color=yellow>created on Shelf</color>!", pos="topCenter", fade=True)
    else:
        cmds.error("You need a visible shelf for this to work! Show your shelf!")


def pose2shelf_ui(*args):
    """Membuat UI antarmuka pilihan (pose2mel ATAU selection2shelf)."""
    win_id = "custButtonWin"

    if cmds.window(win_id, exists=True):
        cmds.deleteUI(win_id)

    window = cmds.window(win_id, title="p2s", widthHeight=(130, 130), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5, columnOffset=["both", 5])

    cmds.text(label="Optional Label:")
    label_field = cmds.textField("_custButtonWin", text="")

    # Tombol 1: Copy pose ke Clipboard
    cmds.button(
        label="pose2mel.",
        height=35,
        annotation="Salin perintah 'setAttr' dari objek terpilih ke Clipboard OS.",
        command=lambda x: pose2mel(),
    )

    cmds.text(label="Or", align="center")

    # Tombol 2: Simpan seleksi ke Shelf Button
    cmds.button(
        label="selection2shelf.",
        height=25,
        annotation="Save Current Selection's Selection Commands as a Shelf Button.",
        command=lambda x: selection2shelf(cmds.textField(label_field, query=True, text=True)),
    )

    cmds.showWindow(window)

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

    
    
    # =========================================================
    # 9) cam to persp
    #    - select outliner
    # =========================================================
def cam_to_persp_self_test(*args):
    cam_ctrl = "rigging_viewtool_camera_df_hig_vr006:Cam_World_Ctrl"
    persp = "persp"

    if not cmds.objExists(cam_ctrl):
        cmds.confirmDialog(
            title="Confirm",
            message="Cam trajectory ctrl tidak ditemukan:\n{}".format(cam_ctrl),
            button=["ok"]
        )
        return

    if not cmds.objExists(persp):
        cmds.confirmDialog(
            title="Confirm",
            message="Camera persp tidak ditemukan.",
            button=["ok"]
        )
        return

    pos = cmds.xform(persp, ws=True, q=True, t=True)
    rot = cmds.xform(persp, ws=True, q=True, ro=True)

    cmds.xform(cam_ctrl, ws=True, t=pos)
    cmds.xform(cam_ctrl, ws=True, ro=rot)

    cmds.setKeyframe(cam_ctrl)

    cmds.inViewMessage(
        amg="✓ <hl>Cam_World_Ctrl</hl> snapped to <hl>persp</hl>",
        pos="topCenter",
        fade=True
    )


    # =========================================================
    # 10) char to cam
    #    - select outliner
    # =========================================================

def char_to_cam_dynamic_test(*args):
    # =========================
    # CAMERA (GLOBAL)
    # =========================
    CAM_CTRL = "rigging_viewtool_camera_df_hig_vr006:Cam_Main_ctrl"

    if not cmds.objExists(CAM_CTRL):
        cmds.confirmDialog(
            title="Confirm",
            message="Camera trajectory ctrl tidak ditemukan:\n{}".format(CAM_CTRL),
            button=["ok"]
        )
        return

    sel = cmds.ls(sl=True, long=True)
    if not sel:
        cmds.confirmDialog(
            title="Confirm",
            message="Select minimal 1 node dari character.",
            button=["ok"]
        )
        return

    for z in sel:
        leaf = z.split("|")[-1]
        if ":" not in leaf:
            cmds.warning("Skip {} (tidak ada namespace)".format(z))
            continue

        ns = leaf.split(":")[0]

        # FIND SUPER & PLACER (dynamic per character)
        super_candidates = cmds.ls(ns + ":*Transform_Ctrl", type="transform") or []
        placer_candidates = cmds.ls(ns + ":*Root_Ctrl", type="transform") or []

        if not super_candidates or not placer_candidates:
            cmds.warning("Skip {} (super/placer ctrl tidak ditemukan)".format(ns))
            continue

        super_ctrl = super_candidates[0]
        placer_ctrl = placer_candidates[0]

        # SNAP SUPER TO CAMERA
        cam_mtx = cmds.xform(CAM_CTRL, ws=True, q=True, m=True)
        cmds.xform(super_ctrl, ws=True, m=cam_mtx)

        # OFFSET VIA PLACER
        cmds.setAttr(placer_ctrl + ".translateZ", -300)
        cmds.setAttr(placer_ctrl + ".translateY", -65)

        offset_mtx = cmds.xform(placer_ctrl, ws=True, q=True, m=True)
        cmds.xform(super_ctrl, ws=True, m=offset_mtx)

        # RESET OFFSET
        cmds.setAttr(placer_ctrl + ".translateZ", 0)
        cmds.setAttr(placer_ctrl + ".translateY", 0)

        # CLEAN ROTATION
        for ax in ("X", "Z"):
            attr = super_ctrl + ".rotate" + ax
            if cmds.objExists(attr):
                cmds.setAttr(attr, 0)

        # KEYFRAME
        cmds.setKeyframe(super_ctrl)

        cmds.inViewMessage(
            amg="✓ <hl>{}</hl> snapped to camera".format(ns),
            pos="topCenter",
            fade=True
        )

# =========================================================
# 10) MATA SELECT
#    - select eye / brow / ear ctrls (namespace aware & multi-character)
# =========================================================
import maya.cmds as cmds

def eyeselect(*args):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Select minimal satu control untuk menentukan namespace.")
        return

    # 1. Kumpulkan semua namespace unik dari objek yang diseleksi
    namespaces = set()
    for obj in sel:
        if ":" in obj:
            # Mengambil semua namespace termasuk nested namespace (cth: charA:rig:)
            ns = ":".join(obj.split(":")[:-1]) + ":"
            namespaces.add(ns)
        else:
            # Jika objek tidak memiliki namespace (root level)
            namespaces.add("")

    # 2. Daftar Kontroler Lengkap (Standard + Full Tyler Case)
    ctrls = [
        # --- Tyler Full Eye & Brow List ---
        "lowerLid4_L", "AimEye_L", "innerLidOuter_R", "upperLid2_R", "Pupil_R", 
        "EyeBrowInner_R", "lowerLid2Outer_R", "lowerLid1Outer_L", "innerLid_R", 
        "upperLid3_L", "outerLid_R", "upperLid2Outer_R", "upperLid3Outer_L", 
        "lowerLidOuter_R", "upperLid4Outer_L", "EyeRegion_R", "lowerLid1_L", 
        "upperLidOuter_L", "lowerLid4_R", "lowerLid_R", "Eye_L", "upperLid4Outer_R", 
        "EyeBrowMid1_R", "upperLid1_R", "upperLid3Outer_R", "lowerLid3_L", 
        "EyeBrowInner_L", "upperLid3_R", "R_eyeMover_Ctrl", "upperLid1_L", 
        "lowerLid2_L", "lowerLid_L", "lowerLid4Outer_R", "upperLid2_L", 
        "EyeBrowMid1_L", "outerLidOuter_L", "lowerLid3Outer_R", "AimEye_R", 
        "lowerLidOuter_L", "upperLid_R", "EyeBrowOuter_R", "EyeBrowOuter_L", 
        "innerLid_L", "Eye_R", "EyeBrowRegion_R", "Nose_ctrl", "lowerLid2Outer_L", 
        "lowerLid1_R", "EyeBrowCenter_M", "upperLidOuter_R", "lowerLid2_R", 
        "outerLidOuter_R", "L_EyeLigth_Jnt_ctrl", "upperLid1Outer_L", "AimEye_M", 
        "Iris_R", "L_eyeMover_Ctrl", "R_EyeLigth_All_ctrl", "upperLid4_L", 
        "lowerLid4Outer_L", "EyeBrowRegion_L", "L_EyeLigth_All_ctrl", "lowerLid3_R", 
        "EyeRegion_L", "upperLid4_R", "upperLid_L", "innerLidOuter_L", "Pupil_L", 
        "upperLid2Outer_L", "Iris_L", "R_EyeLigth_Jnt_ctrl", "lowerLid1Outer_R", 
        "EyeBrowMid2_L", "EyeBrowMid2_R", "lowerLid3Outer_L", "upperLid1Outer_R", 
        "outerLid_L", "ctrlBrow_L", "ctrlBrow_R", "ctrlEye_L", "ctrlEye_R",

        # --- Standard Rigs (Daftar Lama) ---
        "L_eyeLidCornerInn_Ctrl", "R_eye_fk_Ctrl", "L_ear_Ctrl", "R_brow_02_Ctrl", 
        "L_eyeLidCornerOut_Ctrl", "R_brow_04_Ctrl", "L_brow_angry_Ctrl", 
        "L_eyeLidUp_Ctrl", "R_ear_Ctrl", "L_brow_01_Ctrl", "L_eye_fk_Ctrl", 
        "L_upperlash_Tweak_03_Ctrl", "R_brow_01_Ctrl", "L_brow_master_Ctrl", 
        "R_upperlash_Tweak_01_Ctrl", "R_brow_03_Ctrl", "L_brow_02_Ctrl", 
        "L_specular_master_Ctrl", "R_brow_up_down_sad_Ctrl", "R_eyeLidLow_Ctrl", 
        "L_brow_up_down_sad_Ctrl", "R_brow_master_Ctrl", "R_lowerlash_Tweak_01_Ctrl", 
        "L_upperlash_Tweak_02_Ctrl", "L_eyeLidLow_Ctrl", "L_eyeMover_Ctrl", 
        "R_upperlash_Tweak_03_Ctrl", "L_lowerlash_Tweak_01_Ctrl", "brow_blend_Ctrl", 
        "R_eyeMover_Ctrl", "L_upperlash_Tweak_01_Ctrl", "L_brow_03_Ctrl", 
        "R_lowerlash_Tweak_03_Ctrl", "L_lowerlash_Tweak_03_Ctrl", "R_lowerlash_Tweak_02_Ctrl", 
        "R_eyeLidCornerInn_Ctrl", "L_specular_Ctrl", "R_brow_angry_Ctrl", 
        "R_specular_Ctrl", "L_lowerlash_Tweak_02_Ctrl", "L_brow_04_Ctrl", 
        "R_specular_master_Ctrl", "R_eyeLidUp_Ctrl", "R_upperlash_Tweak_02_Ctrl", 
        "eye_blend_Ctrl", "R_eyeLidCornerOut_Ctrl", "global_blend_Ctrl", 
        "eyeMaster_Ctrl", "R_eye_Ctrl", "L_eye_Ctrl"
    ]

    # 3. Filter objek untuk SEMUA namespace yang ditemukan
    found = []
    for ns in namespaces:
        for c in ctrls:
            full_path = ns + c
            if cmds.objExists(full_path):
                found.append(full_path)

    # 4. Eksekusi Seleksi
    if found:
        cmds.select(found, r=True)
        print(f"# Berhasil memilih {len(found)} eye controls dari {len(namespaces)} karakter/namespace.")
    else:
        cmds.warning("Eye controls tidak ditemukan pada namespace yang diseleksi.")

# =========================================================
# MOUTH SELECT
# - select mouth / jaw / teeth / tongue ctrls
# - namespace aware & multi-character
# =========================================================
import maya.cmds as cmds

def mouthselect(*args):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Select minimal satu control untuk menentukan namespace.")
        return

    # 1. Kumpulkan semua namespace unik dari objek yang diseleksi
    namespaces = set()
    for obj in sel:
        if ":" in obj:
            # Mengambil seluruh hierarchy namespace (termasuk nested, cth: charA:rig:)
            ns = ":".join(obj.split(":")[:-1]) + ":"
            namespaces.add(ns)
        else:
            # Jika objek tidak memiliki namespace (root level)
            namespaces.add("")

    # 2. Daftar Kontroler Gabungan
    ctrls = [
        # --- Standard / General Rigs ---
        "L_lower_teeth_Ctrl", "lower_teeth_Ctrl", "C_lower_teeth_Ctrl",
        "jaw_rotation_Ctrl", "R_cornerMouth_Ctrl", "upper_lip_Ctrl",
        "lower_lip_Ctrl", "L_upper_teeth_Ctrl", "L_low_lip_01_Ctrl",
        "mouth_master_Ctrl", "jaw_forward_backward_Ctrl", "low_lip_Ctrl",
        "R_up_lip_Ctrl", "tongue_05_Ctrl", "C_upper_teeth_Ctrl",
        "R_nose_Ctrl", "R_low_lip_01_Ctrl", "L_nose_Ctrl", "nose_Ctrl",
        "jaw_translation_Ctrl", "low_teeth_Ctrl", "R_upper_teeth_Ctrl",
        "tongue_02_Ctrl", "R_up_lip_01_Ctrl", "L_cheek_tweak_Ctrl",
        "L_up_lip_Ctrl", "R_lower_teeth_Ctrl", "tongue_rotation_Ctrl",
        "tongue_03_Ctrl", "uvula_01_Ctrl", "L_low_lip_Ctrl",
        "L_up_lip_01_Ctrl", "R_cheek_tweak_Ctrl", "tongue_01_Ctrl",
        "tongue_up_down_Ctrl", "tongue_04_Ctrl", "L_cornerMouth_Ctrl",
        "upper_teeth_Ctrl", "mouth_blend_Ctrl", "uvula_02_Ctrl",
        "up_teeth_Ctrl", "phoneme_blend_Ctrl", "R_low_lip_Ctrl",
        "up_lip_Ctrl", "jaw_Ctrl",

        # --- Tyler Full Mouth Case ---
        "NoseSide_L", "cornerLip_L", "NoseCorner_R", "upperLipC_R",
        "lowerLip_L", "lowerLipA_L", "FrownBulge_L", "Nose_M",
        "Jaw_M", "Lip_L", "NoseUnder_M", "Tongue2_M",
        "lowerLip_R", "Tongue0_M", "ctrlMouth_M", "Cheek_L",
        "upperLip_M", "upperLip_R", "ctrlMouthCorner_R", "upperLipB_L",
        "Nostril_R", "ctrlEmotions_M", "SmilePull_L", "ctrlLips_M",
        "lowerLipC_R", "ctrlPhonemes_M", "lowerTeeth_M", "upperLipB_R",
        "upperLip_L", "SmileBulge_R", "ctrlMouthCorner_L", "CheekBone_L",
        "NoseCorner_L", "lowerLipC_L", "upperLipA_R", "Tongue3_M",
        "upperLipA_L", "SmilePull_R", "Nostril_L", "CheekBone_R",
        "NoseBridge_M", "Tongue1_M", "NoseRegion_M", "LipRegion_M",
        "Lip_R", "upperTeeth_M", "upperLipC_L", "NoseCrease_M",
        "lowerLip_M", "lowerLipB_R", "ctrlARKit_M", "SmileBulge_L",
        "ChinCrease_M", "NoseSide_R", "FrownBulge_R", "cornerLip_R",
        "Cheek_R", "lowerLipB_L", "lowerLipA_R",
        "ctrlNose_L", "ctrlNose_R", "ctrlCheek_R", "ctrlCheek_L",

        # --- Tyler Mouth Secondary (Jnt_ctrl) ---
        "M_Mouth_Sec_Dn_Jnt_ctrl", "L_Mouth_Sec_Up_01_Jnt_ctrl", 
        "L_Mouth_Sec_Jnt_ctrl", "R_Mouth_Sec_Up_01_Jnt_ctrl", 
        "L_Mouth_Sec_Dn_00_Jnt_ctrl", "L_Mouth_Sec_Up_00_Jnt_ctrl", 
        "M_Mouth_Sec_Up_Jnt_ctrl", "R_Mouth_Sec_Dn_00_Jnt_ctrl", 
        "R_Mouth_Sec_Dn_01_Jnt_ctrl", "R_Mouth_Sec_Up_00_Jnt_ctrl", 
        "L_Mouth_Sec_Dn_01_Jnt_ctrl", "R_Mouth_Sec_Jnt_ctrl"
    ]

    # 3. Filter objek untuk SEMUA namespace yang ditemukan
    found = []
    for ns in namespaces:
        for c in ctrls:
            full_path = ns + c
            if cmds.objExists(full_path):
                found.append(full_path)

    # 4. Eksekusi Seleksi
    if found:
        cmds.select(found, r=True)
        print(f"# Berhasil memilih {len(found)} mouth controls dari {len(namespaces)} karakter/namespace.")
    else:
        cmds.warning("Mouth controls tidak ditemukan pada namespace yang diseleksi.")
        
# =========================================================
# TweenMachine
# =========================================================
def tweenmachine_start(*args):
    """
    Run tweenMachine (support import tweenMachine.start()).
    Fallback: from TKB import tweenMachine
    """
    try:
        import tweenMachine
        # reload biar kalau kamu edit tweenMachine.py, Maya kebaca
        try:
            from importlib import reload
            reload(tweenMachine)
        except Exception:
            pass

        if hasattr(tweenMachine, "start"):
            tweenMachine.start()
            return

        cmds.warning("tweenMachine imported tapi tidak ada function: start()")
        return

    except Exception:
        pass

    # fallback kalau tweenMachine.py ada di dalam package TKB
    try:
        from TKB import tweenMachine
        try:
            from importlib import reload
            reload(tweenMachine)
        except Exception:
            pass

        if hasattr(tweenMachine, "start"):
            tweenMachine.start()
            return

        cmds.warning("TKB.tweenMachine imported tapi tidak ada function: start()")

    except Exception as e:
        cmds.warning("TKB: gagal jalanin tweenMachine -> {}".format(e))


# =========================================================
# Copy Anim
# =========================================================
def run_paie_original(*args):
    # Mendapatkan path folder tempat tools.py berada
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Daftarkan folder ke sistem pencarian Python
    if script_dir not in sys.path:
        sys.path.append(script_dir)
        
    try:
        import PAIE
        from importlib import reload
        reload(PAIE) 
        PAIE.GUI()
        print("# PAIE Berhasil Dimuat.")
    except Exception as e:
        cmds.warning("Gagal memanggil PAIE asli: {}".format(e))
        traceback.print_exc()
        
# =========================================================
# Mirror
# =========================================================

# TKB/tools.py

def apply_mirror_simple(*args):
    """
    Versi sederhana Mirror Pose untuk TKB.
    Mendukung penukaran atribut L_ ke R_ dan sebaliknya.
    """
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Pilih kontroler yang ingin di-mirror!")
        return

    for obj in sel:
        # Tentukan target lawan
        target = None
        if "L_" in obj: target = obj.replace("L_", "R_")
        elif "R_" in obj: target = obj.replace("R_", "L_")
        elif "_L" in obj: target = obj.replace("_L", "_R")
        elif "_R" in obj: target = obj.replace("_R", "_L")
        
        if not target or not cmds.objExists(target):
            # Jika objek tengah (Center), kita mirror nilainya sendiri (misal Rotate Y dan Z)
            mirror_logic(obj, obj, is_center=True)
            continue
            
        # Jika ada lawan, tukar nilainya
        mirror_logic(obj, target, is_center=False)

    cmds.inViewMessage(amg="Mirror Applied!", pos="topCenter", fade=True)

def mirror_logic(source, target, is_center=False):
    """Logika pembalikan nilai atribut"""
    # Atribut yang biasanya perlu dibalik nilainya (Invert)
    # Sesuaikan dengan standar rig kamu (biasanya Translate X dan Rotate Y/Z)
    invert_attrs = ["translateX", "rotateY", "rotateZ"] if not is_center else ["rotateY", "rotateZ"]
    
    attrs = cmds.listAttr(source, k=True) or []
    for attr in attrs:
        if not cmds.attributeQuery(attr, node=target, exists=True): continue
        
        try:
            val = cmds.getAttr(f"{source}.{attr}")
            # Jika masuk dalam daftar invert, kalikan -1
            if any(x in attr for x in invert_attrs):
                val *= -1
            
            cmds.setAttr(f"{target}.{attr}", val)
        except:
            pass
            
# =========================================================
# TweenMachine V2
# =========================================================
def tween_logic(percentage, *args):
    sel = cmds.ls(sl=True)
    if not sel: return
    
    curr = cmds.currentTime(q=True)
    factor = (percentage + 100) / 200.0 

    for obj in sel:
        attrs = cmds.listAttr(obj, k=True, w=True) or []
        for attr in attrs:
            atf = "{}.{}".format(obj, attr)
            pk = cmds.findKeyframe(atf, which="previous", time=(curr, curr))
            nk = cmds.findKeyframe(atf, which="next", time=(curr, curr))
            
            if pk is None or nk is None or pk == nk: continue 

            v1 = cmds.getAttr(atf, time=pk)
            v2 = cmds.getAttr(atf, time=nk)
            nv = v1 + (v2 - v1) * factor
            
            try:
                cmds.setAttr(atf, nv)
                cmds.setKeyframe(atf, time=curr)
            except: pass
            
# =========================================================
# refresh_evaluation_mode
# =========================================================
def refresh_evaluation_mode(*args):
    """
    Siklus Kilat Penyembuh Bug Viewport: Parallel -> Off -> Parallel.
    Menggunakan perintah murni mode string agar kompetibel dengan Maya 2022.
    """
    try:
        # 1. Reset memori Viewport 2.0 (OGS) untuk ngerontokin mesh/rig patah
        mel.eval("ogs -reset;")
        
        # 2. Siklus kilat: Matikan (off) lalu kembalikan ke Parallel
        # Ini padanan Python dari: evaluationManager -mode "off";
        mc.evaluationManager(mode="off")
        
        # Ini padanan Python dari: evaluationManager -mode parallel;
        mc.evaluationManager(mode="parallel")
        
        print("// TKB: Viewport Reset & Cycle Completed (Off -> Parallel).")
        
        # 3. Notifikasi kuning di tengah Viewport Maya
        mc.inViewMessage(amg='Viewport & Parallel Graph <color=yellow>Successfully Refreshed</color>!', pos='topCenter', fade=True)
        
    except Exception as e:
        mc.warning("TKB: Gagal refresh evaluation mode -> {}".format(e))
        
# =========================================================
# IK-FK
# =========================================================
# TKB/tools.py
import maya.cmds as cmds
import maya.api.OpenMaya as om

def get_pole_vector_pos(hip_pos, knee_pos, ankle_pos, offset=35.0):
    """Menghitung posisi ideal Pole Vector menggunakan proyeksi Vektor Matematika."""
    b_hip = om.MVector(hip_pos)
    b_knee = om.MVector(knee_pos)
    b_ankle = om.MVector(ankle_pos)
    
    hip_to_ankle = b_ankle - b_hip
    hip_to_knee = b_knee - b_hip
    
    line_dir = hip_to_ankle.normal()
    projection = line_dir * (hip_to_knee * line_dir)
    
    mid_point = b_hip + projection
    pv_dir = b_knee - mid_point
    
    final_pv = b_knee + (pv_dir.normal() * offset)
    return [final_pv.x, final_pv.y, final_pv.z]

def match_transform_api(source_name, target_name, pos=True, rot=True):
    """Menyelaraskan transformasi menggunakan OpenMaya World Space Quaternion murni."""
    if not cmds.objExists(source_name) or not cmds.objExists(target_name):
        return
    sel = om.MSelectionList()
    sel.add(source_name)
    sel.add(target_name)
    
    source_path = sel.getDagPath(0)
    target_path = sel.getDagPath(1)
    
    source_matrix = source_path.inclusiveMatrix()
    matrix_trans = om.MTransformationMatrix(source_matrix)
    target_fn = om.MFnTransform(target_path)
    
    if pos:
        target_fn.setTranslation(matrix_trans.translation(om.MSpace.kWorld), om.MSpace.kWorld)
    if rot:
        world_rot = matrix_trans.rotation(asQuaternion=True)
        target_fn.setRotation(world_rot, om.MSpace.kWorld)

def SwitchIKFK(*args):
    """
    IK/FK Switcher Universal Multi-Rig (Mendukung Rig MD & Rig TR ZooHive Engine).
    Sistem Precision Driver Matching berbasis World Space Locator Joint Alignment.
    """
    selected_objects = cmds.ls(selection=True)

    if not selected_objects:
        cmds.warning("TKB: Pilih salah satu kontroler kaki atau tangan terlebih dahulu!")
        return

    current_select = selected_objects[0]
    namespace = current_select.rsplit(":", 1)[0] + ":" if ":" in current_select else ""
    obj_name = current_select.rsplit(":", 1)[-1]
    
    # Deteksi Tipe Rig
    is_tr_rig = any(x in obj_name.lower() for x in ["_ctrl", "arm_", "leg_", "shldr_", "wrist_"])

    if is_tr_rig:
        # ==========================================
        # RIG TR (ZooHive / TR Rig Engine)
        # ==========================================
        side_code = "R" if ("_R_" in obj_name or "_r_" in obj_name.lower()) else "L"
        body_part = "Leg" if any(x in obj_name.lower() for x in ["leg", "foot", "hip", "knee", "ankle"]) else "Arm"
        
        if body_part == "Arm":
            settings_node = f"{namespace}arm_{side_code}_controlPanel_settings"
            ik_ctrl = f"{namespace}arm_{side_code}_wrist_ik_Ctrl"
            pole_vector = f"{namespace}arm_{side_code}_elbowPv_pv_Ctrl"
            fk_controls = [
                f"{namespace}arm_{side_code}_shldr_fk_Ctrl",
                f"{namespace}arm_{side_code}_elbow_fk_Ctrl",
                f"{namespace}arm_{side_code}_wrist_fk_Ctrl"
            ]
            result_joints = [
                f"{namespace}arm_{side_code}_shldr_jnt",
                f"{namespace}arm_{side_code}_elbow_jnt",
                f"{namespace}arm_{side_code}_wrist_jnt"
            ]
            loc_target = f"{namespace}LOC_arm_{side_code}_wrist_jnt"
            fk_extra = None
        else:
            settings_node = f"{namespace}leg_{side_code}_controlPanel_settings"
            ik_ctrl = f"{namespace}leg_{side_code}_ankle_ik_Ctrl"
            pole_vector = f"{namespace}leg_{side_code}_kneePv_pv_Ctrl"
            fk_controls = [
                f"{namespace}leg_{side_code}_hip_fk_Ctrl",
                f"{namespace}leg_{side_code}_knee_fk_Ctrl",
                f"{namespace}leg_{side_code}_ankle_fk_Ctrl"
            ]
            result_joints = [
                f"{namespace}leg_{side_code}_hip_jnt",
                f"{namespace}leg_{side_code}_knee_jnt",
                f"{namespace}leg_{side_code}_ankle_jnt"
            ]
            loc_target = f"{namespace}LOC_leg_{side_code}_ankle_jnt"
            fk_extra = f"{namespace}leg_{side_code}_ball_fk_Ctrl"

        # Fallback pencarian node settings
        if not cmds.objExists(settings_node) and cmds.attributeQuery("ikfk", node=current_select, exists=True):
            conn = cmds.listConnections(f"{current_select}.ikfk", plugs=True) or []
            if conn: settings_node = conn[0].split(".")[0]

        if not cmds.objExists(settings_node):
            cmds.warning(f"TKB: Control Panel Settings '{settings_node}' tidak ditemukan!")
            return

        full_attr = f"{settings_node}.ikfk"
        current_val = cmds.getAttr(full_attr)
        is_currently_ik = current_val > 0.5

        # --- TR RIG: IK -> FK ---
        if is_currently_ik:
            # Pindahkan setiap FK Ctrl ke World Space Joint Result asli
            for fk_c, res_j in zip(fk_controls, result_joints):
                if cmds.objExists(fk_c) and cmds.objExists(res_j):
                    match_transform_api(res_j, fk_c, pos=False, rot=True)
            
            # Switch Blend ke FK (0.0)
            cmds.setAttr(full_attr, 0.0)
            
            select_list = [c for c in fk_controls if cmds.objExists(c)]
            if fk_extra and cmds.objExists(fk_extra): select_list.append(fk_extra)
            cmds.select(select_list, replace=True)
            print(f"// TKB: [{namespace}] Switched TR {body_part}_{side_code} to FK.")

        # --- TR RIG: FK -> IK ---
        else:
            fk_target = fk_controls[2]
            res_target = result_joints[2]
            
            # Pilih jangkar posisi paling presisi (LOC Joint > Result Joint > FK Target)
            if cmds.objExists(loc_target):
                target_pos_node = loc_target
            elif cmds.objExists(res_target):
                target_pos_node = res_target
            else:
                target_pos_node = fk_target

            if cmds.objExists(ik_ctrl) and cmds.objExists(target_pos_node):
                # 1. Ambillah koordinat World Space murni dari jangkar posisi & rotasi FK
                target_pos = cmds.xform(target_pos_node, query=True, worldSpace=True, translation=True)
                target_rot = cmds.xform(fk_target, query=True, worldSpace=True, rotation=True)
                
                # 2. Hitung Proyeksi Pole Vector berdasarkan posisi sendi hasil deformasi
                if all(cmds.objExists(j) for j in result_joints[:3]):
                    p1 = cmds.xform(result_joints[0], query=True, worldSpace=True, translation=True)
                    p2 = cmds.xform(result_joints[1], query=True, worldSpace=True, translation=True)
                    p3 = cmds.xform(result_joints[2], query=True, worldSpace=True, translation=True)
                    pv_pos = get_pole_vector_pos(p1, p2, p3, offset=35.0)
                else:
                    pv_pos = None

                # 3. Ubah atribut ikfk ke IK (1.0)
                cmds.setAttr(full_attr, 1.0)
                
                # 4. Tembakkan koordinat murni ke IK Control & Pole Vector
                cmds.xform(ik_ctrl, worldSpace=True, translation=target_pos)
                cmds.xform(ik_ctrl, worldSpace=True, rotation=target_rot)
                
                if pole_vector and cmds.objExists(pole_vector) and pv_pos:
                    cmds.xform(pole_vector, worldSpace=True, translation=pv_pos)

            select_ik = [c for c in [ik_ctrl, pole_vector] if cmds.objExists(c)]
            cmds.select(select_ik, replace=True)
            print(f"// TKB: [{namespace}] Switched TR {body_part}_{side_code} to IK.")

    else:
        # ==========================================
        # RIG MD (Stella/Bloom MD Engine)
        # ==========================================
        side = "_R" if ("_R" in obj_name or obj_name.endswith("_R")) else "_L"
        body_part = "Leg" if any(x in obj_name for x in ["Leg", "Hip", "Knee", "Ankle", "Toes"]) else "Arm"
        
        if body_part == "Leg":
            switch_ctrl = f"{namespace}FKIKLeg{side}"
            ik_ctrl = f"{namespace}IKLeg{side}"
            pole_vector = f"{namespace}PoleLeg{side}"
            fk_controls = [f"{namespace}FKHip{side}", f"{namespace}FKKnee{side}", f"{namespace}FKAnkle{side}"]
            fk_extra = f"{namespace}FKToes{side}"
            result_joints = [f"{namespace}Hip{side}", f"{namespace}Knee{side}", f"{namespace}Ankle{side}"]
        else:
            switch_ctrl = f"{namespace}FKIKArm{side}"
            ik_ctrl = f"{namespace}IKArm{side}"
            pole_vector = f"{namespace}PoleArm{side}"
            fk_controls = [f"{namespace}FKShoulder{side}", f"{namespace}FKElbow{side}", f"{namespace}FKWrist{side}"]
            fk_extra = None
            result_joints = [f"{namespace}Shoulder{side}", f"{namespace}Elbow{side}", f"{namespace}Wrist{side}"]

        full_attr = f"{switch_ctrl}.FKIKBlend"
        if not cmds.objExists(switch_ctrl):
            cmds.warning(f"TKB: Control '{switch_ctrl}' tidak ditemukan!")
            return

        current_val = cmds.getAttr(full_attr)
        
        if current_val > 5.0:
            if body_part == "Arm":
                for fk_c, res_j in zip(fk_controls, result_joints):
                    match_transform_api(res_j, fk_c, pos=False, rot=True)
            else:
                for fk_c, res_j in zip(fk_controls, result_joints):
                    if cmds.objExists(fk_c) and cmds.objExists(res_j):
                        cmds.matchTransform(fk_c, res_j, pos=False, rot=True)
            
            cmds.setAttr(full_attr, 0)
            select_list = [c for c in fk_controls if cmds.objExists(c)]
            if fk_extra and cmds.objExists(fk_extra): select_list.append(fk_extra)
            cmds.select(select_list, replace=True)
            print(f"// TKB: [{namespace}] Switched MD {body_part}{side} to FK.")
        else:
            fk_target = fk_controls[2]
            res_target = result_joints[2]
            
            if cmds.objExists(ik_ctrl) and cmds.objExists(fk_target):
                target_world_pos = cmds.xform(res_target, query=True, worldSpace=True, translation=True)
                target_world_rot = cmds.xform(fk_target, query=True, worldSpace=True, rotation=True)
                
                p_hip = cmds.xform(result_joints[0], query=True, worldSpace=True, translation=True)
                p_knee = cmds.xform(result_joints[1], query=True, worldSpace=True, translation=True)
                p_ankle = cmds.xform(result_joints[2], query=True, worldSpace=True, translation=True)
                ideal_pv_pos = get_pole_vector_pos(p_hip, p_knee, p_ankle, offset=35.0)

                cmds.setAttr(full_attr, 10)
                cmds.xform(ik_ctrl, worldSpace=True, translation=target_world_pos)
                cmds.xform(ik_ctrl, worldSpace=True, rotation=target_world_rot)

                if cmds.objExists(pole_vector):
                    cmds.xform(pole_vector, worldSpace=True, translation=ideal_pv_pos)
            
            cmds.select([ik_ctrl, pole_vector], replace=True)
            print(f"// TKB: [{namespace}] Switched MD {body_part}{side} to IK.")
            
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

# =========================================================
# Bacth Parent
# =========================================================

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

# =========================================================
# 13) SETUP & TWEAK IMAGE PLANE ACTIVE CAMERA
# =========================================================
def setup_image_plane_active_cam(*args):
    """
    Membuat/menghubungkan Image Plane (Image/Movie) ke kamera aktif/terpilih
    dan membuka UI kontrol cepat untuk Alpha Gain & Depth.
    """
    cam = None

    # 1. Cek apakah user sedang memilih kamera di Outliner terlebih dahulu
    sel = cmds.ls(sl=True, type="transform") or []
    for node in sel:
        shapes = cmds.listRelatives(node, shapes=True, type="camera") or []
        if shapes:
            cam = node
            break

    # 2. Jika tidak ada kamera yang diseleksi, deteksi kamera dari Viewport aktif
    if not cam:
        active_panel = cmds.getPanel(withFocus=True)
        if not active_panel or "modelPanel" not in active_panel:
            panels = cmds.getPanel(type="modelPanel") or []
            if panels:
                active_panel = panels[0]

        if active_panel:
            cam = cmds.modelPanel(active_panel, q=True, camera=True)

    # Fallback khusus untuk kamera outliner kamu jika tidak terdeteksi otomatis
    if not cam or not cmds.objExists(cam):
        target_default = "mm2_210_11_187_cam"
        if cmds.objExists(target_default):
            cam = target_default
        else:
            cmds.warning("Gagal mendeteksi kamera! Pilih kamera di Outliner terlebih dahulu.")
            return

    # 3. File Dialog (Mendukung Image & Video/Movie)
    file_path = cmds.fileDialog2(
        fileFilter="Image & Movie Files (*.png *.jpg *.jpeg *.tif *.tiff *.mov *.mp4 *.avi);;All Files (*.*)",
        dialogStyle=2,
        fileMode=1,
        caption=f"Pilih Image/Movie untuk Kamera: {cam}"
    )

    if not file_path:
        return

    selected_file = file_path[0]

    # 4. Buat Image Plane
    try:
        img_plane_nodes = cmds.imagePlane(camera=cam, fileName=selected_file)
        if not img_plane_nodes:
            return
            
        img_node = img_plane_nodes[0]
        cmds.setAttr(f"{img_node}.displayOnlyIfCurrent", 1)

        # Cek jika file berupa movie/video sekuens
        ext = os.path.splitext(selected_file)[-1].lower()
        if ext in [".mov", ".mp4", ".avi"]:
            try:
                cmds.setAttr(f"{img_node}.useFrameExtension", 1)
            except Exception:
                pass

        clean_cam_name = cam.split("|")[-1].split(":")[-1]
        cmds.inViewMessage(
            amg=f"✓ Image Plane dipasang di <hl>{clean_cam_name}</hl>",
            pos="topCenter",
            fade=True
        )

        # Buka UI Pop-up Kontrol Cepat untuk Alpha Gain
        open_image_plane_tweak_ui(img_node)

    except Exception as e:
        cmds.warning(f"Gagal memasang Image Plane: {e}")


def open_image_plane_tweak_ui(img_node):
    """Membuat window mini untuk mengatur Alpha Gain & Depth Image Plane secara real-time."""
    win_id = "TKB_ImagePlaneTweakWin"
    if cmds.window(win_id, exists=True):
        cmds.deleteUI(win_id)

    if not cmds.objExists(img_node):
        return

    window = cmds.window(win_id, title="Image Plane Control", widthHeight=(260, 95), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnOffset=["both", 8])

    clean_node_name = img_node.split("|")[-1]
    cmds.text(label=f"Target: {clean_node_name}", align="center", fn="boldLabelFont")

    # Slider Alpha Gain
    curr_alpha = cmds.getAttr(f"{img_node}.alphaGain")
    
    def _update_alpha(val):
        if cmds.objExists(img_node):
            cmds.setAttr(f"{img_node}.alphaGain", val)

    cmds.floatSliderGrp(
        label="Alpha Gain: ", 
        field=True, 
        minValue=0.0, 
        maxValue=1.0, 
        value=curr_alpha,
        step=0.01,
        columnWidth3=[75, 45, 110],
        dc=_update_alpha,
        cc=_update_alpha
    )

    # Depth Options (In Front / Behind Model)
    curr_depth = cmds.getAttr(f"{img_node}.depth")
    
    def _update_depth(depth_mode):
        if cmds.objExists(img_node):
            cmds.setAttr(f"{img_node}.depth", depth_mode)

    cmds.rowLayout(numberOfColumns=3, columnWidth3=[75, 80, 80])
    cmds.text(label="Depth: ")
    cmds.radioCollection()
    cmds.radioButton(label="In Front", select=(curr_depth == 0), cc=lambda x: _update_depth(0) if x else None)
    cmds.radioButton(label="Behind", select=(curr_depth != 0), cc=lambda x: _update_depth(1) if x else None)

    cmds.showWindow(window)
    
# =========================================================
# 14) MOTION TRAIL
# =========================================================
# =========================================================
# 14) MOTION TRAIL
# =========================================================
def create_motion_trail():
    """
    Membuat Motion Trail pada objek yang dipilih untuk seluruh Playback Range.
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

    # 2. Fallback: Gunakan Motion Trail resmi Maya untuk seluruh Time Slider Range
    start_frame = cmds.playbackOptions(q=True, minTime=True)
    end_frame = cmds.playbackOptions(q=True, maxTime=True)

    for obj in selection:
        # Hapus Motion Trail lama pada objek ini jika ada (mencegah tumpuk)
        existing_trails = cmds.listConnections(obj, type="motionTrail") or []
        if existing_trails:
            cmds.delete(existing_trails)

        # Buat Motion Trail baru dari startFrame hingga endFrame
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


def remove_motion_trail():
    """
    Menghapus Motion Trail pada objek yang dipilih.
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

    # Fallback hapus node motionTrail pada objek terpilih
    deleted = False
    for obj in selection:
        # Cari node motionTrail atau shape-nya
        history_trails = cmds.listHistory(obj, type="motionTrail") or []
        conn_trails = cmds.listConnections(obj, type="motionTrail") or []
        all_obj_trails = list(set(history_trails + conn_trails))
        
        if all_obj_trails:
            cmds.delete(all_obj_trails)
            deleted = True

    if deleted:
        cmds.inViewMessage(amg="✓ Motion Trail Objek Terpilih Dihapus", pos="topCenter", fade=True)
    else:
        cmds.warning("Tidak ditemukan Motion Trail pada objek yang dipilih.")

    return deleted


def clear_all_trails():
    """
    Menghapus seluruh node Motion Trail di scene.
    """
    # Cari node animBot ATAU node bawaan Maya (motionTrail, motionTrailShape, snapshot)
    trails = (
        cmds.ls(type="animBotMotionTrail") or [] +
        cmds.ls(type="motionTrail") or [] +
        cmds.ls(type="motionTrailShape") or []
    )
    trails = list(set(trails))

    if trails:
        cmds.delete(trails)
        cmds.inViewMessage(amg="✓ Semua Motion Trail Dihapus", pos="topCenter", fade=True)
        return True
    else:
        cmds.warning("Tidak ditemukan Motion Trail di dalam scene.")
        return False