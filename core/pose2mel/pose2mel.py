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