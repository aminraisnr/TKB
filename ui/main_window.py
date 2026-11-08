# -*- coding: utf-8 -*-
# tkb/ui/main_window.py
import os
import sys
import importlib
import importlib.util
import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance

from .styles import ANIMBOT_STYLE
from .widgets.tween_slider import AnimBotTweenSliderWidget

WSC_ID = "TKB_HorizontalWSC"
GLOBAL_TKB_WIDGET = None


class TKBToolbarWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TKBToolbarWidget, self).__init__(parent)
        self.setObjectName("TKB_MainWidget")
        self.setStyleSheet(ANIMBOT_STYLE)
        
        # Path folder utama 'tkb'
        self.TKB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.icon_path = os.path.join(self.TKB_DIR, "icons").replace("\\", "/")
        self._tween_module = None
        
        self._init_ui()

    def _get_tween_module(self):
        if self._tween_module is None:
            folder_path = os.path.join(self.TKB_DIR, "core", "tween machine").replace("\\", "/")
            if folder_path not in sys.path:
                sys.path.insert(0, folder_path)
            
            target_file = "tweenSlider.py" if os.path.exists(os.path.join(folder_path, "tweenSlider.py")) else "tweenSlider313.py"
            file_path = os.path.join(folder_path, target_file).replace("\\", "/")
            
            module_name = "tkb_core_tween_machine"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            self._tween_module = mod
        return self._tween_module

    def _get_tween_cache(self):
        mod = self._get_tween_module()
        if mod and hasattr(mod, "get_neighbor_cache"):
            return mod.get_neighbor_cache()
        return {}

    def _on_tween_slider_drag(self, val, mode, cache=None):
        mod = self._get_tween_module()
        if not mod:
            return

        func_map = {
            "blend_neighbors": "performBlendToNeighbors",
            "ease": "performBlendToEase",
            "default": "performBlendToDefault",
            "prev_frame": "performBlendToFrame",
            "next_frame": "performBlendToFrame"
        }
        func_name = func_map.get(mode, "performBlendToNeighbors")
        if hasattr(mod, func_name):
            func = getattr(mod, func_name)
            kwargs = {"percent": val, "is_realtime": True, "cache": cache}
            if mode == "prev_frame":
                kwargs["target_neighbor"] = "prev"
            elif mode == "next_frame":
                kwargs["target_neighbor"] = "next"
            func(**kwargs)

    def _run_core_script(self, folder_name, main_file=None, func_name=None, *args, **kwargs):
        def wrapper():
            try:
                folder_path = os.path.join(self.TKB_DIR, "core", folder_name).replace("\\", "/")
                if folder_path not in sys.path:
                    sys.path.insert(0, folder_path)
                
                target_file = main_file
                if not target_file:
                    if os.path.exists(os.path.join(folder_path, "tweenSlider.py")):
                        target_file = "tweenSlider.py"
                    elif os.path.exists(os.path.join(folder_path, "tweenSlider313.py")):
                        target_file = "tweenSlider313.py"
                    elif os.path.exists(os.path.join(folder_path, f"{folder_name}.py")):
                        target_file = f"{folder_name}.py"

                if not target_file:
                    return

                file_path = os.path.join(folder_path, target_file).replace("\\", "/")
                module_name = f"tkb_core_{folder_name.replace(' ', '_')}"
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

                if func_name and hasattr(mod, func_name):
                    func = getattr(mod, func_name)
                    return func(*args, **kwargs)

                for f in ["run", "show", "main", "start", "performBlendToNeighbors"]:
                    if hasattr(mod, f):
                        return getattr(mod, f)(*args, **kwargs)
            except Exception as e:
                cmds.warning(f"TKB: Gagal menjalankan {folder_name} -> {e}")
        return wrapper

    def _trigger_nudge_keys(self, direction):
        try:
            val_text = self.nudge_input.text()
            amount = float(val_text) if val_text else 1.0
        except ValueError:
            amount = 1.0
        nudge_amount = -amount if direction == "left" else amount
        self._run_core_script("nudge keys", main_file="nudge_keys.py", func_name="nudge_keys_by_amount", amount=nudge_amount)()

    def _create_nudge_widget(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        btn_left = QtWidgets.QToolButton()
        btn_left.setText("<")
        btn_left.setToolTip("Nudge Keys Backward (Mundur)")
        btn_left.setFixedSize(22, 28)
        btn_left.clicked.connect(lambda: self._trigger_nudge_keys("left"))

        self.nudge_input = QtWidgets.QLineEdit()
        self.nudge_input.setObjectName("NudgeAmountField")
        self.nudge_input.setText("10")
        self.nudge_input.setAlignment(QtCore.Qt.AlignCenter)
        self.nudge_input.setToolTip("Masukkan Jumlah Frame Pergeseran Keyframe")
        self.nudge_input.setFixedSize(32, 28)
        self.nudge_input.setValidator(QtGui.QDoubleValidator())

        btn_right = QtWidgets.QToolButton()
        btn_right.setText(">")
        btn_right.setToolTip("Nudge Keys Forward (Maju)")
        btn_right.setFixedSize(22, 28)
        btn_right.clicked.connect(lambda: self._trigger_nudge_keys("right"))

        layout.addWidget(btn_left)
        layout.addWidget(self.nudge_input)
        layout.addWidget(btn_right)
        container.setFixedWidth(80)
        return container

    def _run_overlap_helper(self):
        try:
            oh_base_path = os.path.join(self.TKB_DIR, "core", "overlap").replace("\\", "/")
            if oh_base_path not in sys.path:
                sys.path.insert(0, oh_base_path)

            for m in list(sys.modules.keys()):
                if m == "uiFile" or m.startswith("uiFile."):
                    del sys.modules[m]

            import uiFile
            importlib.reload(uiFile)

            if hasattr(uiFile, "show_ui"):
                uiFile.show_ui()
            elif hasattr(uiFile, "ui"):
                if hasattr(uiFile, "maya_main_window"):
                    uiFile.ui(uiFile.maya_main_window())
                else:
                    uiFile.ui()
        except Exception as e:
            cmds.warning(f"TKB: Gagal menjalankan OverlapHelper -> {e}")

    def _get_icon(self, fname):
        p = os.path.join(self.icon_path, fname).replace("\\", "/")
        if os.path.exists(p) and fname:
            return QtGui.QIcon(p)
        return QtGui.QIcon()

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
        menu.addAction("Align All (Current Frame)", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=True, all_keys=False))
        menu.addAction("Align Position Only", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=False, all_keys=False))
        menu.addAction("Align Rotation Only", self._run_core_script("align", func_name="align_to_last", translate=False, rotate=True, all_keys=False))
        menu.addSeparator()
        menu.addAction("Align All Keys (Multi-Frame)", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=True, all_keys=True))
        menu.addAction("Align Position All Keys", self._run_core_script("align", func_name="align_to_last", translate=True, rotate=False, all_keys=True))
        menu.addAction("Align Rotation All Keys", self._run_core_script("align", func_name="align_to_last", translate=False, rotate=True, all_keys=True))

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
        btn.setToolTip("MOTION TRAIL")
        btn.setFixedSize(28, 28)
        btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        btn.clicked.connect(self._run_core_script("motion trail", func_name="create_motion_trail"))

        menu = QtWidgets.QMenu(btn)
        menu.addAction("Create Motion Trail", self._run_core_script("motion trail", func_name="create_motion_trail"))
        menu.addAction("Remove Selected Trail", self._run_core_script("motion trail", func_name="remove_motion_trail"))
        menu.addSeparator()
        menu.addAction("Clear All Trails", self._run_core_script("motion trail", func_name="clear_all_trails"))

        btn.setMenu(menu)
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: menu.exec_(b.mapToGlobal(pos)))
        return btn

    def _create_ikfk_btn(self):
        btn = QtWidgets.QToolButton()
        icon = self._get_icon("ikfk.png")
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QtCore.QSize(22, 22))
        else:
            btn.setText("IKFK")
            
        btn.setToolTip("IK/FK Matcher (Klik kiri untuk UI / Klik kanan untuk Quick Match)")
        btn.setFixedSize(28, 28)
        
        btn.clicked.connect(self._run_core_script("match ikfk", main_file="ikfk_matcher.py", func_name="show_ui"))

        menu = QtWidgets.QMenu(btn)
        menu.addAction("Show IK/FK Matcher UI", self._run_core_script("match ikfk", main_file="ikfk_matcher.py", func_name="show_ui"))
        menu.addSeparator()
        menu.addAction("Match IK -> FK (Selection)", self._run_core_script("match ikfk", main_file="ikfk_matcher.py", func_name="match_ik_to_fk_selected"))
        menu.addAction("Match FK -> IK (Selection)", self._run_core_script("match ikfk", main_file="ikfk_matcher.py", func_name="match_fk_to_ik_selected"))

        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: menu.exec_(b.mapToGlobal(pos)))
        return btn

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
        main_layout.addWidget(self._create_btn("cam.png", "CAM>PERSP", self._run_core_script("cam to persp", func_name="cam_to_persp_self_test")))
        main_layout.addWidget(self._create_btn("charcam.png", "CHAR>CAM", self._run_core_script("char to cam", func_name="char_to_cam_dynamic_test")))
        main_layout.addWidget(self._create_btn("grid.png", "MAYA COMP GRIDS", self._run_core_script("grids", main_file="comp_grids_launcher.py", func_name="show"), text="CG"))
        main_layout.addWidget(self._create_separator())

        # --- GRUP 2: Transform & Utility ---
        self.tween_slider = AnimBotTweenSliderWidget(
            callback=self._on_tween_slider_drag,
            cache_func=self._get_tween_cache
        )
        self.tween_slider.setToolTip("Tween Slider (Klik Kanan untuk Mengganti Mode)")
        main_layout.addWidget(self.tween_slider)
        main_layout.addWidget(self._create_align_btn())
        main_layout.addWidget(self._create_ikfk_btn())
        main_layout.addWidget(self._create_motion_trail_btn())
        main_layout.addWidget(self._create_btn("reset.png", "RESET", self._run_core_script("reset", func_name="reset_selected")))
        main_layout.addWidget(self._create_btn("null.png", "NULL", self._run_core_script("null", func_name="create_null")))
        main_layout.addWidget(self._create_btn("step_snap.png", "SS", self._run_core_script("step snap", func_name="ss")))
        main_layout.addWidget(self._create_btn("Remove.png", "RemoveTangent", self._run_core_script("remove parent", func_name="remove_all_constraints_from_selection")))
        main_layout.addWidget(self._create_btn("bacth.png", "anaknya dulu baru ibu", self._run_core_script("bacth parent", func_name="batch_parent_constraint_rigs")))
        main_layout.addWidget(self._create_btn("gpu.png", "GPU CACHE", self._run_core_script("gpu cache", func_name="create_gpu_cache")))
        main_layout.addWidget(self._create_nudge_widget())
        main_layout.addWidget(self._create_separator())

        # --- GRUP 3: Selection Sets ---
        main_layout.addWidget(self._create_btn("select_all.png", "SELECT ALL", self._run_core_script("select all", func_name="select_all_multi")))
        main_layout.addWidget(self._create_btn("hier.png", "CTRL SELECT", self._run_core_script("smart select", func_name="smart_select")))
        main_layout.addWidget(self._create_btn("Mata.png", "MATA SELECT", self._run_core_script("select eyes", func_name="eyeselect")))
        main_layout.addWidget(self._create_btn("Mulut.png", "MULUT SELECT", self._run_core_script("select mouth", func_name="mouthselect")))
        main_layout.addWidget(self._create_separator())

        # --- GRUP 4: Script & Engine ---
        main_layout.addWidget(self._create_btn("paie.png", "PAIE SYSTEM", self._run_core_script("copy anim")))
        main_layout.addWidget(self._create_btn("pose2shelf.png", "pose2shelf", self._run_core_script("pose2mel", func_name="pose2shelf_ui")))
        main_layout.addWidget(self._create_btn("OverlapHelperIcon.png", "OVERLAP HELPER", self._run_overlap_helper))
        main_layout.addWidget(self._create_btn("refresh.png", "REFRESH EVAL", self._run_core_script("refresh", func_name="refresh_evaluation_mode")))