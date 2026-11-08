# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets
    from shiboken2 import wrapInstance

from tkb.ui.main_window import TKBToolbarWidget, WSC_ID

GLOBAL_TKB_WIDGET = None


def build_tkb_ui(*args):
    """Membuat dan menempelkan TKBToolbarWidget ke Maya WorkspaceControl."""
    global GLOBAL_TKB_WIDGET
    wsc_ptr = omui.MQtUtil.findControl(WSC_ID)
    if not wsc_ptr:
        return
    
    wsc_widget = wrapInstance(int(wsc_ptr), QtWidgets.QWidget)
    if wsc_widget.layout():
        old_layout = wsc_widget.layout()
        QtWidgets.QWidget().setLayout(old_layout)
        
    layout = QtWidgets.QVBoxLayout(wsc_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    
    GLOBAL_TKB_WIDGET = TKBToolbarWidget(parent=wsc_widget)
    layout.addWidget(GLOBAL_TKB_WIDGET)


def UI():
    """Fungsi utama untuk membuat WorkspaceControl di Maya."""
    if cmds.workspaceControl(WSC_ID, exists=True):
        cmds.deleteUI(WSC_ID)
        
    cmds.workspaceControl(
        WSC_ID,
        label="AMINNN TOOLS COY",
        retain=False,
        dockToMainWindow=("bottom", 1),
        initialHeight=38,
        # SUDAH DIPERBAIKI: Menggunakan huruf kecil 'tkb.main'
        uiScript="import tkb.main as tkb_main; tkb_main.build_tkb_ui()"
    )
    build_tkb_ui()
    cmds.workspaceControl(WSC_ID, e=True, restore=True)


def show():
    UI()


def show_ui():
    UI()