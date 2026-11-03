# TKB/ui.py
import os
import sys
import importlib
import maya.cmds as cmds

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui

WSC_ID = "TKB_HorizontalWSC"

GLOBAL_TKB_WIDGET = None

ANIMBOT_STYLE = """
QWidget#TKB_MainWidget {
    background-color: #212328;
    border-radius: 6px;
}

QToolButton {
    background-color: #2b2e35;
    color: #e0e0e0;
    border: 1px solid #1a1c20;
    border-radius: 5px;
    padding: 3px;
    font-size: 11px;
    font-weight: bold;
}

QToolButton:hover {
    background-color: #3b404b;
    border: 1px solid #00b4d8;
}

QToolButton:pressed {
    background-color: #0081a7;
    border: 1px solid #00b4d8;
    color: #ffffff;
}

/* Sembunyikan panah bawaan InstantPopup */
QToolButton::menu-indicator {
    image: none;
    width: 0px;
}

QMenu {
    background-color: #212328;
    color: #e0e0e0;
    border: 1px solid #00b4d8;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 4px 16px;
    border-radius: 3px;
    font-size: 11px;
}

QMenu::item:selected {
    background-color: #0081a7;
    color: #ffffff;
}

QFrame[frameShape="4"], QFrame[frameShape="5"] {
    background-color: #383c46;
    border: none;
    width: 1px;
    margin: 3px 2px;
}

QToolTip {
    background-color: #1a1c20;
    color: #00b4d8;
    border: 1px solid #00b4d8;
    border-radius: 3px;
    padding: 4px;
    font-size: 10px;
}
"""

class TKBToolbarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TKBToolbarWidget, self).__init__(parent)
        self.setObjectName("TKB_MainWidget")
        self.setStyleSheet(ANIMBOT_STYLE)
        
        self.TKB_DIR = os.path.dirname(__file__)
        self.icon_path = os.path.join(self.TKB_DIR, "icons").replace("\\", "/")
        
        self.ttools = self._import_tools()
        self._init_ui()

    def _import_tools(self):
        try:
            from TKB import tools as ttools
            return ttools
        except Exception as e:
            cmds.warning("TKB: Gagal import tools.py -> {}".format(e))
            return None

    def _get_icon(self, fname):
        p = os.path.join(self.icon_path, fname).replace("\\", "/")
        if os.path.exists(p) and fname:
            return QtGui.QIcon(p)
        
        cg_icon = os.path.join(self.TKB_DIR, "maya_comp_grids", fname).replace("\\", "/")
        if os.path.exists(cg_icon) and fname:
            return QtGui.QIcon(cg_icon)
            
        return QtGui.QIcon()

    def _get_func(self, name):
        if self.ttools is None:
            return lambda *args, **kwargs: cmds.warning("TKB: Tools tidak tersedia.")
        func = getattr(self.ttools, name, None)
        if func is None:
            return lambda *args, **kwargs: cmds.warning("TKB: Fungsi '{}' tidak ditemukan di tools.py".format(name))
        return func

    def _run_align(self, translate=True, rotate=True, all_keys=False):
        func = self._get_func("align_to_last")
        try:
            func(translate=translate, rotate=rotate, all_keys=all_keys)
        except TypeError:
            func()

    def _create_align_btn(self):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon("mix.png")
        
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText("ALIGN")
            
        btn.setToolTip("ALIGN (Klik kiri/kanan untuk opsi)")
        btn.setFixedSize(28, 28)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        
        menu = QtWidgets.QMenu(btn)
        menu.addAction("Align All (Current Frame)", lambda: self._run_align(translate=True, rotate=True, all_keys=False))
        menu.addAction("Align Position Only", lambda: self._run_align(translate=True, rotate=False, all_keys=False))
        menu.addAction("Align Rotation Only", lambda: self._run_align(translate=False, rotate=True, all_keys=False))
        
        menu.addSeparator()
        
        menu.addAction("⚡ Align All Keys (Multi-Frame)", lambda: self._run_align(translate=True, rotate=True, all_keys=True))
        menu.addAction("⚡ Align Position All Keys", lambda: self._run_align(translate=True, rotate=False, all_keys=True))
        menu.addAction("⚡ Align Rotation All Keys", lambda: self._run_align(translate=False, rotate=True, all_keys=True))
        
        btn.setMenu(menu)
        
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: menu.exec_(b.mapToGlobal(pos)))
        
        return btn

    def _create_motion_trail_btn(self):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon("motion_trail.png")
        
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText("MT")
            
        btn.setToolTip("MOTION TRAIL (Klik kiri untuk Create, Klik kanan untuk opsi)")
        btn.setFixedSize(28, 28)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        
        # Klik kiri menjalankan langsung fungsi create_motion_trail
        btn.clicked.connect(self._get_func("create_motion_trail"))
        
        menu = QtWidgets.QMenu(btn)
        menu.addAction("Create Motion Trail", self._get_func("create_motion_trail"))
        menu.addAction("Remove Selected Trail", self._get_func("remove_motion_trail"))
        menu.addSeparator()
        menu.addAction("Clear All Trails", self._get_func("clear_all_trails"))
        
        btn.setMenu(menu)
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: menu.exec_(b.mapToGlobal(pos)))
        
        return btn

    def _run_comp_grids(self):
        try:
            cg_path = os.path.join(self.TKB_DIR, "maya_comp_grids").replace("\\", "/")
            if not os.path.exists(cg_path):
                cmds.warning("TKB: Folder maya_comp_grids tidak ditemukan di: {}".format(cg_path))
                return
            if cg_path not in sys.path:
                sys.path.insert(0, cg_path)

            for m in list(sys.modules.keys()):
                if m.startswith('maya_comp_grids') or m == 'comp_grids_launcher':
                    sys.modules.pop(m, None)

            import comp_grids_launcher
            importlib.reload(comp_grids_launcher)
            comp_grids_launcher.show()
        except Exception as e:
            cmds.warning("TKB: Gagal menjalankan maya_comp_grids -> {}".format(e))

    def _run_overlap_helper(self):
        try:
            sys.path = [p for p in sys.path if "other/OverlapHelper" not in p.replace("\\", "/")]
            oh_base_path = os.path.join(self.TKB_DIR, "OverlapHelper").replace("\\", "/")
            py_ver = "{}{}".format(sys.version_info[0], sys.version_info[1])
            oh_version_path = os.path.join(oh_base_path, py_ver).replace("\\", "/")
            
            if not os.path.exists(oh_version_path):
                available_folders = [f for f in os.listdir(oh_base_path) if os.path.isdir(os.path.join(oh_base_path, f))]
                available_folders.sort(key=lambda x: [int(s) if s.isdigit() else s for s in os.path.split(x)], reverse=True)
                if available_folders:
                    py_ver = available_folders[0]
                    oh_version_path = os.path.join(oh_base_path, py_ver).replace("\\", "/")
                else:
                    cmds.warning("TKB: Folder OverlapHelper tidak ditemukan di: {}".format(oh_base_path))
                    return

            if oh_version_path not in sys.path: sys.path.insert(0, oh_version_path)
            if oh_base_path not in sys.path: sys.path.insert(0, oh_base_path)

            for m in list(sys.modules.keys()):
                if m == "uiFile" or m.startswith("uiFile."):
                    del sys.modules[m]

            importlib.import_module("uiFile")
        except Exception as e:
            cmds.warning("TKB: Gagal menjalankan OverlapHelper -> {}".format(e))

    def _create_btn(self, icon_file, tooltip, func, text=""):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon(icon_file)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText(text if text else tooltip[:3].upper())
            
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        btn.clicked.connect(func)
        return btn

    def _create_separator(self):
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        return sep

    def _init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(6, 3, 6, 3)
        main_layout.setSpacing(4)
        main_layout.setAlignment(QtCore.Qt.AlignCenter)

        # --- GRUP 1: Camera Tools ---
        main_layout.addWidget(self._create_btn("cam.png", "CAM>PERSP", self._get_func("cam_to_persp_self_test")))
        main_layout.addWidget(self._create_btn("charcam.png", "CHAR>CAM", self._get_func("char_to_cam_dynamic_test")))
        main_layout.addWidget(self._create_btn("grid.png", "MAYA COMP GRIDS", self._run_comp_grids, text="CG"))

        main_layout.addWidget(self._create_separator())

        # --- GRUP 2: Transform & Utility ---
        main_layout.addWidget(self._create_align_btn())
        main_layout.addWidget(self._create_btn("reset.png", "RESET", self._get_func("reset_selected")))
        main_layout.addWidget(self._create_btn("null.png", "NULL", self._get_func("create_null")))
        main_layout.addWidget(self._create_btn("step_snap.png", "SS", self._get_func("ss")))
        main_layout.addWidget(self._create_btn("Remove.png", "RemoveTangent", self._get_func("remove_all_constraints_from_selection")))
        main_layout.addWidget(self._create_btn("bacth.png", "anaknya dulu baru ibu", self._get_func("batch_parent_constraint_rigs")))
        main_layout.addWidget(self._create_btn("gpu.png", "GPU CACHE", self._get_func("create_gpu_cache")))

        main_layout.addWidget(self._create_separator())

        # --- GRUP 3: Selection Sets ---
        main_layout.addWidget(self._create_btn("select_all.png", "SELECT ALL", self._get_func("select_all_multi")))
        main_layout.addWidget(self._create_btn("hier.png", "CTRL SELECT", self._get_func("smart_select")))
        main_layout.addWidget(self._create_btn("Mata.png", "MATA SELECT", self._get_func("eyeselect")))
        main_layout.addWidget(self._create_btn("Mulut.png", "MULUT SELECT", self._get_func("mouthselect")))

        main_layout.addWidget(self._create_separator())

        # --- GRUP 4: Script & Engine ---
        main_layout.addWidget(self._create_btn("tweenMachine.png", "TWEENMACHINE", self._get_func("tweenmachine_start")))
        main_layout.addWidget(self._create_btn("paie.png", "PAIE SYSTEM", self._get_func("run_paie_original")))
        main_layout.addWidget(self._create_btn("pose2shelf.png", "pose2shelf", self._get_func("pose2shelf_ui")))
        main_layout.addWidget(self._create_btn("OverlapHelperIcon.png", "OVERLAP HELPER", self._run_overlap_helper))
        main_layout.addWidget(self._create_motion_trail_btn())
        main_layout.addWidget(self._create_btn("refresh.png", "REFRESH EVAL", self._get_func("refresh_evaluation_mode")))


def build_tkb_ui(*args):
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
    if cmds.workspaceControl(WSC_ID, exists=True):
        cmds.deleteUI(WSC_ID)

    cmds.workspaceControl(
        WSC_ID,
        label="AMINNN TOOLS COY",
        retain=False,
        dockToMainWindow=("bottom", 1),
        initialHeight=38,
        uiScript="import TKB.ui as tkb_ui; tkb_ui.build_tkb_ui()"
    )

    build_tkb_ui()
    cmds.workspaceControl(WSC_ID, e=True, restore=True)

def show():
    UI()