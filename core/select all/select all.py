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